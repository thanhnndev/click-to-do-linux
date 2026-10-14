"""High-speed OCR Engine with automatic HiDPI coordinate scaling."""

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
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

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.engine = RapidOCR()

    @classmethod
    def get_instance(cls) -> "OCREngine":
        if cls._instance is None:
            cls._instance = OCREngine()
        return cls._instance

    @classmethod
    def warmup(cls):
        """Pre-loads ONNX session into RAM so first capture has 0 cold-start."""
        inst = cls.get_instance()
        dummy = np.zeros((64, 64, 3), dtype=np.uint8)
        try:
            inst.engine(dummy)
        except Exception:
            pass

    @staticmethod
    def _tesseract_line(crop: Image.Image) -> str:
        """Reads one text line with Tesseract (vie+eng) so Vietnamese diacritics are preserved."""
        w, h = crop.size
        if h < 48:  # small UI text: upscale for the LSTM recognizer
            k = 48 / h
            crop = crop.resize((max(1, int(w * k)), 48), Image.Resampling.LANCZOS)
        crop = ImageOps.expand(crop.convert("L"), border=10, fill=255 if np.asarray(crop.convert("L")).mean() > 127 else 0)
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            crop.save(tmp.name)
            env = dict(os.environ, TESSDATA_PREFIX=str(get_tessdata_dir()), OMP_THREAD_LIMIT="1")
            out = subprocess.run(
                ["tesseract", tmp.name, "-", "-l", "vie+eng", "--psm", "7", "--dpi", "150"],
                capture_output=True, text=True, env=env, timeout=10,
            )
        return " ".join(out.stdout.split())

    def _detect_hybrid(self, image: Image.Image, img_np: np.ndarray):
        """RapidOCR finds text lines; Tesseract reads them. Returns [(pts, text, conf)] or None."""
        det, _ = self.engine(img_np, use_det=True, use_cls=False, use_rec=False)
        if not det:
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

    def detect(self, image: Image.Image, scale_factor: float = 1.0) -> List[TextBox]:
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
                results, _ = self.engine(img_np)
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
