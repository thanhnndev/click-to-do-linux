"""Entity detector for QR Codes, URLs, Emails with HiDPI coordinate mapping."""

import re
import subprocess
from dataclasses import dataclass
from typing import List, Tuple
from urllib.parse import quote_plus
import cv2
import numpy as np
from PIL import Image


@dataclass
class QREntity:
    text: str
    rect: Tuple[int, int, int, int]  # Logical x, y, w, h
    is_url: bool


URL_REGEX = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
    re.IGNORECASE,
)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


class EntityDetector:
    @staticmethod
    def detect_qr_codes(image: Image.Image, scale_factor: float = 1.0) -> List[QREntity]:
        entities = []
        inv_scale = 1.0 / scale_factor if scale_factor > 0 else 1.0
        try:
            cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            detector = cv2.QRCodeDetector()
            retval, decoded_info, points, _ = detector.detectAndDecodeMulti(cv_img)
            if retval and points is not None:
                for text, pts in zip(decoded_info, points):
                    if not text:
                        continue
                    xs = [p[0] * inv_scale for p in pts]
                    ys = [p[1] * inv_scale for p in pts]
                    min_x, max_x = int(min(xs)), int(max(xs))
                    min_y, max_y = int(min(ys)), int(max(ys))
                    rect = (min_x, min_y, max(10, max_x - min_x), max(10, max_y - min_y))
                    is_url = bool(URL_REGEX.match(text) or text.startswith("www."))
                    entities.append(QREntity(text=text, rect=rect, is_url=is_url))
        except Exception:
            pass
        return entities

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        return URL_REGEX.findall(text)

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        return EMAIL_REGEX.findall(text)

    @staticmethod
    def open_url(url: str) -> bool:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    @staticmethod
    def open_email(email: str) -> bool:
        try:
            subprocess.Popen(["xdg-open", f"mailto:{email}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    @staticmethod
    def search_web(query: str, engine: str = "google") -> bool:
        engines = {
            "google": "https://www.google.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
            "bing": "https://www.bing.com/search?q=",
        }
        base = engines.get(engine.lower(), engines["google"])
        return EntityDetector.open_url(base + quote_plus(query.strip()))
