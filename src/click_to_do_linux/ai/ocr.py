"""High-speed OCR Engine with automatic HiDPI coordinate scaling."""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image


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

    def detect(self, image: Image.Image, scale_factor: float = 1.0) -> List[TextBox]:
        """Runs OCR on physical image and normalizes bounding boxes to logical UI coordinates."""
        img_np = np.array(image)
        try:
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
