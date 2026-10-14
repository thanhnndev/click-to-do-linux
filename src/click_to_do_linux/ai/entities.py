"""Entity detector for QR Codes, URLs, Emails, Colors, and Structured Tables."""

import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image


@dataclass
class QREntity:
    text: str
    rect: Tuple[int, int, int, int]  # x, y, w, h
    is_url: bool


URL_REGEX = re.compile(
    r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)",
    re.IGNORECASE,
)
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
HEX_COLOR_REGEX = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")


class EntityDetector:
    """Detects smart entities in visual snapshots or text."""

    @staticmethod
    def detect_qr_codes(image: Image.Image) -> List[QREntity]:
        """Detects QR codes and their coordinates using OpenCV."""
        entities = []
        try:
            cv_img = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            detector = cv2.QRCodeDetector()
            retval, decoded_info, points, _ = detector.detectAndDecodeMulti(cv_img)
            
            if retval and points is not None:
                for text, pts in zip(decoded_info, points):
                    if not text:
                        continue
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    min_x, max_x = int(min(xs)), int(max(xs))
                    min_y, max_y = int(min(ys)), int(max(ys))
                    rect = (min_x, min_y, max(1, max_x - min_x), max(1, max_y - min_y))
                    is_url = bool(URL_REGEX.match(text) or text.startswith("www."))
                    entities.append(QREntity(text=text, rect=rect, is_url=is_url))
        except Exception as e:
            print(f"[EntityDetector] QR detection error: {e}")
        return entities

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        return URL_REGEX.findall(text)

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        return EMAIL_REGEX.findall(text)

    @staticmethod
    def extract_hex_colors(text: str) -> List[str]:
        return HEX_COLOR_REGEX.findall(text)

    @staticmethod
    def open_url(url: str) -> bool:
        """Opens URL in system default browser via xdg-open."""
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url
        try:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[EntityDetector] Failed to open URL {url}: {e}")
            return False

    @staticmethod
    def open_email(email: str) -> bool:
        try:
            subprocess.Popen(["xdg-open", f"mailto:{email}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[EntityDetector] Failed to open mailto {email}: {e}")
            return False

    @staticmethod
    def search_web(query: str, engine: str = "google") -> bool:
        from urllib.parse import quote_plus
        engines = {
            "google": "https://www.google.com/search?q=",
            "duckduckgo": "https://duckduckgo.com/?q=",
            "bing": "https://www.bing.com/search?q=",
            "kagi": "https://kagi.com/search?q=",
        }
        base_url = engines.get(engine.lower(), engines["google"])
        url = base_url + quote_plus(query.strip())
        return EntityDetector.open_url(url)

    @staticmethod
    def visual_search_google_lens(image_path: str) -> bool:
        """Opens Google Lens search in the browser."""
        # For local images, we can open Google Lens or an image search provider
        url = "https://images.google.com/"
        return EntityDetector.open_url(url)
