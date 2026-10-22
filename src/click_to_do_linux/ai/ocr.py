"""High-speed OCR Engine with automatic HiDPI coordinate scaling."""

import os
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
import requests
from PIL import Image, ImageOps

TESSDATA_BASE_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main"
TESS_LANGS = ("vie", "eng")


def get_tessdata_dir() -> Path:
    d = Path.home() / ".local" / "share" / "click-to-do" / "tessdata"
    d.mkdir(parents=True, exist_ok=True)
    return d


def tesseract_ready() -> bool:
    """True when the tesseract binary and Vietnamese + English data are available."""
    if not shutil.which("tesseract"):
        return False
    d = get_tessdata_dir()
    return all((d / f"{lang}.traineddata").exists() for lang in TESS_LANGS)


def download_tessdata() -> None:
    """Fetches the compact Vietnamese/English Tesseract models (~4.6 MB) to the user data dir."""
    d = get_tessdata_dir()
    for lang in TESS_LANGS:
        dest = d / f"{lang}.traineddata"
        if dest.exists():
            continue
        r = requests.get(f"{TESSDATA_BASE_URL}/{lang}.traineddata", timeout=60)
        r.raise_for_status()
        tmp = dest.with_suffix(".part")
        tmp.write_bytes(r.content)
        tmp.replace(dest)


@dataclass
class TextBox:
    text: str
    confidence: float
    # Coordinates in LOGICAL screen pixels (matched 1:1 with Qt mouse events)
    rect: Tuple[int, int, int, int]  # x, y, w, h

    def contains_point(self, px: float, py: float) -> bool:
        x, y, w, h = self.rect
        return (x - 2) <= px <= (x + w + 2) and (y - 2) <= py <= (y + h + 2)

    def intersects_rect(self, rx: float, ry: float, rw: float, rh: float) -> bool:
        x, y, w, h = self.rect
        return not (x + w < rx or x > rx + rw or y + h < ry or y > ry + rh)


class OCREngine:
    """Singleton RapidOCR engine kept warm in Daemon memory."""

    _instance: Optional["OCREngine"] = None
    _instance_lock = threading.Lock()

    def __init__(self):
        from rapidocr import RapidOCR

        self._inference_lock = threading.RLock()
        self.engine = RapidOCR()
        self._npu = None

    @classmethod
    def get_instance(cls) -> "OCREngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = OCREngine()
        return cls._instance

    @classmethod
    def warmup(cls):
        """Pre-loads ONNX session into RAM so first capture has 0 cold-start."""
        inst = cls.get_instance()
        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        with inst._inference_lock:
            try:
                inst.engine(dummy, use_det=True, use_cls=False, use_rec=False)
            except Exception:
                pass
            inst._maybe_attach_npu()

    def _maybe_attach_npu(self) -> None:
        """Routes text detection to the NPU when enabled; the CPU session stays as fallback."""
        from ..config import load_config

        cfg = load_config()
        if cfg.ocr_det_backend != "npu" or self._npu is not None:
            return
        try:
            from pathlib import Path

            from . import npu_det

            rdir = Path(cfg.ryzenai_dir)
            det = self.engine.text_det
            if not npu_det.available(rdir) or det is None:
                return
            model = str(Path(self.engine.text_det.session.session._model_path))
            cache = Path.home() / ".cache" / "click-to-do" / "npu"
            self._npu = npu_det.NPUDetector(rdir, model, cache)
            det.session = npu_det.NPUSession(det.session, self._npu)
        except Exception as e:
            print(f"[OCREngine] NPU detection unavailable: {e}")

    @staticmethod
    def _tesseract_line(crop: Image.Image, *, url_mode: bool = False) -> str:
        """Reads one text line with Tesseract (vie+eng) so Vietnamese diacritics are preserved."""
        w, h = crop.size
        if h < 48:  # small UI text: upscale for the LSTM recognizer
            k = 48 / h
            crop = crop.resize((max(1, int(w * k)), 48), Image.Resampling.LANCZOS)
        crop = ImageOps.expand(crop.convert("L"), border=10, fill=255 if np.asarray(crop.convert("L")).mean() > 127 else 0)
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            crop.save(tmp.name)
            env = dict(os.environ, TESSDATA_PREFIX=str(get_tessdata_dir()), OMP_THREAD_LIMIT="1")
            command = ["tesseract", tmp.name, "-", "-l", "eng" if url_mode else "vie+eng",
                       "--psm", "7", "--dpi", "150"]
            if url_mode:
                command += ["-c", "load_system_dawg=0", "-c", "load_freq_dawg=0"]
            out = subprocess.run(
                command,
                capture_output=True, text=True, env=env, timeout=10,
            )
        return " ".join(out.stdout.split())

    @staticmethod
    def refine_links(image: Image.Image, links, scale_factor: float = 1.0):
        """Re-read detected URL fragments in English on the analysis worker.

        Bilingual prose OCR can confuse I/l/1 in case-sensitive paths. Accept
        only those narrow character differences; preserve the original URL if
        the second pass disagrees about its structure or cannot read a crop.
        """
        from .entities import EntityDetector

        if not links or not tesseract_ready():
            return links
        scale = scale_factor if scale_factor > 0 else 1.0
        confusables = str.maketrans({"I": "l", "1": "l", "|": "l"})

        def read_link(link):
            try:
                parts = []
                for x, y, w, h in link.rects:
                    crop = image.crop((max(0, int(x * scale) - 3), max(0, int(y * scale) - 3),
                                       min(image.width, int((x + w) * scale) + 3),
                                       min(image.height, int((y + h) * scale) + 3)))
                    part = OCREngine._tesseract_line(crop, url_mode=True)
                    if not part or any(char.isspace() for char in part):
                        return link
                    parts.append(part)
                urls = EntityDetector.extract_urls("".join(parts))
                if len(urls) == 1 and urls[0].translate(confusables) == link.text.translate(confusables):
                    return replace(link, text=urls[0])
            except (OSError, subprocess.TimeoutExpired, ValueError):
                pass
            return link

        with ThreadPoolExecutor(max_workers=min(4, len(links))) as pool:
            return list(pool.map(read_link, links))

    def _detect_hybrid(self, image: Image.Image, img_np: np.ndarray):
        """RapidOCR finds text lines; Tesseract reads them. Returns [(pts, text, conf)] or None."""
        with self._inference_lock:
            out = self.engine(img_np, use_det=True, use_cls=False, use_rec=False)
        det = out.boxes
        if det is None or len(det) == 0:
            return []
        crops = []
        for pts in det:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            pad = 3
            box = (
                max(0, int(min(xs)) - pad), max(0, int(min(ys)) - pad),
                min(image.width, int(max(xs)) + pad), min(image.height, int(max(ys)) + pad),
            )
            crops.append((pts, image.crop(box)))
        with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as pool:
            texts = list(pool.map(lambda c: self._tesseract_line(c[1]), crops))
        return [(pts, t, 0.9) for (pts, _), t in zip(crops, texts)]

    def detect(self, image: Image.Image, scale_factor: float = 1.0, *, raise_errors: bool = False) -> List[TextBox]:
        """Runs OCR on physical image and normalizes bounding boxes to logical UI coordinates."""
        img_np = np.array(image)
        try:
            results = None
            if tesseract_ready():
                try:
                    results = self._detect_hybrid(image.convert("RGB"), img_np)
                except Exception as e:
                    print(f"[OCREngine] Tesseract path failed, falling back to RapidOCR: {e}")
            if results is None:
                with self._inference_lock:
                    out = self.engine(img_np, use_det=True, use_cls=False, use_rec=True)
                if out.boxes is None or out.txts is None:
                    return []
                results = list(zip(out.boxes.tolist(), out.txts, out.scores))
            if not results:
                return []

            boxes: List[TextBox] = []
            inv_scale = 1.0 / scale_factor if scale_factor > 0 else 1.0

            for item in results:
                box_pts, text, conf = item
                if float(conf) < 0.45 or not text.strip():
                    continue
                xs = [p[0] * inv_scale for p in box_pts]
                ys = [p[1] * inv_scale for p in box_pts]
                min_x = int(min(xs))
                min_y = int(min(ys))
                max_x = int(max(xs))
                max_y = int(max(ys))
                w = max(4, max_x - min_x)
                h = max(4, max_y - min_y)

                boxes.append(
                    TextBox(
                        text=text.strip(),
                        confidence=float(conf),
                        rect=(min_x, min_y, w, h),
                    )
                )

            boxes.sort(key=lambda b: (b.rect[1] // 14, b.rect[0]))
            return boxes
        except Exception as e:
            print(f"[OCREngine] Detection error: {e}")
            if raise_errors:
                raise
            return []

    @staticmethod
    def get_text_in_selection(boxes: List[TextBox], rx: int, ry: int, rw: int, rh: int) -> str:
        matched = [b for b in boxes if b.intersects_rect(rx, ry, rw, rh)]
        if not matched:
            return ""
        matched.sort(key=lambda b: (b.rect[1] // 14, b.rect[0]))
        return "\n".join(b.text for b in matched)

    @staticmethod
    def find_box_at(boxes: List[TextBox], px: int, py: int) -> Optional[TextBox]:
        for b in boxes:
            if b.contains_point(px, py):
                return b
        return None
