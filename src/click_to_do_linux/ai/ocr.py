"""OCR Engine using RapidOCR with ONNX Runtime acceleration."""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image


@dataclass
class TextBox:
    text: str
    confidence: float
    box: List[List[float]]  # 4 corner points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
    rect: Tuple[int, int, int, int]  # x, y, width, height

    def contains_point(self, px: float, py: float) -> bool:
        x, y, w, h = self.rect
        return x <= px <= x + w and y <= py <= y + h

    def intersects_rect(self, rx: float, ry: float, rw: float, rh: float) -> bool:
        x, y, w, h = self.rect
        return not (x + w < rx or x > rx + rw or y + h < ry or y > ry + rh)


class OCREngine:
    """Manages OCR inference on screen snapshots."""

    _instance: Optional["OCREngine"] = None

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        # Initialize RapidOCR with default fast ONNX models
        self.engine = RapidOCR()

    @classmethod
    def get_instance(cls) -> "OCREngine":
        if cls._instance is None:
            cls._instance = OCREngine()
        return cls._instance

    def detect(self, image: Image.Image) -> List[TextBox]:
        """Runs OCR on the given PIL Image and returns a list of TextBox objects."""
        img_np = np.array(image)
        try:
            results, elapse = self.engine(img_np)
            if not results:
                return []

            boxes: List[TextBox] = []
            for item in results:
                # item: [box_points, text, confidence]
                box_pts, text, conf = item
                xs = [p[0] for p in box_pts]
                ys = [p[1] for p in box_pts]
                min_x = int(min(xs))
                min_y = int(min(ys))
                max_x = int(max(xs))
                max_y = int(max(ys))
                w = max(1, max_x - min_x)
                h = max(1, max_y - min_y)

                boxes.append(
                    TextBox(
                        text=text.strip(),
                        confidence=float(conf),
                        box=box_pts,
                        rect=(min_x, min_y, w, h),
                    )
                )

            # Sort boxes in top-to-bottom, left-to-right reading order
            boxes.sort(key=lambda b: (b.rect[1] // 15, b.rect[0]))
            return boxes
        except Exception as e:
            print(f"[OCREngine] Error during OCR detection: {e}")
            return []

    @staticmethod
    def get_text_in_selection(boxes: List[TextBox], rx: int, ry: int, rw: int, rh: int) -> str:
        """Extracts and formats text within a user selection rectangle."""
        matched = [b for b in boxes if b.intersects_rect(rx, ry, rw, rh)]
        if not matched:
            return ""

        # Sort matching boxes in reading order
        matched.sort(key=lambda b: (b.rect[1] // 15, b.rect[0]))
        return "\n".join(b.text for b in matched)

    @staticmethod
    def find_box_at(boxes: List[TextBox], px: int, py: int) -> Optional[TextBox]:
        """Finds the text box under a specific coordinate."""
        for b in boxes:
            if b.contains_point(px, py):
                return b
        return None
