"""Entity detector for QR Codes, URLs, Emails with HiDPI coordinate mapping."""

import re
import subprocess
from dataclasses import dataclass
from typing import List, Tuple
from urllib.parse import quote_plus, urlsplit
import ipaddress
import cv2
import numpy as np
from PIL import Image


@dataclass
class QREntity:
    text: str
    rect: Tuple[int, int, int, int]  # Logical x, y, w, h
    is_url: bool


URL_REGEX = re.compile(
    r"(?<![\w@.])(?:https?://[^\s<>\"']+|www\.[^\s<>\"']+|"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63}(?::[0-9]+)?(?:[/\?#][^\s<>\"']*)?)",
    re.IGNORECASE,
)


def merge_text_lines(text: str) -> str:
    """Remove visual line wrapping while retaining spaces between words."""
    return " ".join(text.split())


@dataclass(frozen=True)
class LinkEntity:
    """One complete URL with hit areas for each visible OCR fragment."""

    text: str
    rects: tuple[Tuple[int, int, int, int], ...]

    @property
    def rect(self):
        x = min(r[0] for r in self.rects)
        y = min(r[1] for r in self.rects)
        right = max(r[0] + r[2] for r in self.rects)
        bottom = max(r[1] + r[3] for r in self.rects)
        return x, y, right - x, bottom - y

    def contains_point(self, x, y):
        return any(rx - 2 <= x <= rx + rw + 2 and ry - 2 <= y <= ry + rh + 2
                   for rx, ry, rw, rh in self.rects)


def _clean_url(url):
    url = url.rstrip(".,;:!?")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        while url.endswith(closing) and url.count(closing) > url.count(opening):
            url = url[:-1]
    return url


_URL_PREFIXES = ("https://", "http://", "www.")
_TOKEN_REGEX = re.compile(r"[^\s<>\"']+")
_URL_FRAGMENT = re.compile(r"[\w~%+/#?&=.:,@!$;()*_{}\[\]-]+")


def _url_seeds(text):
    """Seed full URLs and unfinished prefixes; a line need not be a valid URL."""
    for token in _TOKEN_REGEX.finditer(text):
        start = token.start()
        value = token.group()
        while value.startswith(("(", "[", "{")):
            start += 1
            value = value[1:]
        matches = list(URL_REGEX.finditer(value))
        if matches:
            for match in matches:
                yield start + match.start(), start + match.end(), match.group()
        elif value and (any(prefix.startswith(value.lower()) for prefix in _URL_PREFIXES)
                        or re.fullmatch(r"[a-zA-Z0-9-]+\.", value)):
            yield start, start + len(value), value


def _url_parts(value):
    try:
        return urlsplit(value if value.lower().startswith(("https://", "http://")) else "https://" + value)
    except ValueError:
        return None


def _valid_url(value):
    """Validate only after assembly, without guessing or requesting the URL."""
    if not value or any(c.isspace() for c in value):
        return False
    parts = _url_parts(value)
    if parts is None or not parts.hostname or parts.scheme not in ("http", "https"):
        return False
    try:
        _ = parts.port  # Reject malformed ports.
        host = parts.hostname.encode("idna").decode("ascii")
        try:
            ipaddress.ip_address(host)
            return True
        except ValueError:
            pass
        if host == "localhost":
            return value.lower().startswith(("https://", "http://"))
        labels = host.split(".")
        return (len(labels) >= 2 and 2 <= len(labels[-1]) <= 63
                and not labels[-1].isdigit()
                and all(re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                        for label in labels))
    except (ValueError, UnicodeError):
        return False


def _can_continue(raw, token, *, trailing_prose=False, explicit_space=False):
    """Separate layout continuation from final URL validity.

    A URL can wrap inside any component, even 'https://'. Explicit new URL
    prefixes and prose boundaries stop a run; a dot alone does not stop it.
    """
    if not _URL_FRAGMENT.fullmatch(token):
        return False
    if any(prefix.startswith(raw.lower()) for prefix in _URL_PREFIXES):
        combined = (raw + token).lower()
        return any(prefix.startswith(combined) or combined.startswith(prefix) for prefix in _URL_PREFIXES)
    if token.lower().startswith(_URL_PREFIXES):
        # A redirect/query value can itself be a URL. Else it starts a new link.
        parts = _url_parts(raw)
        return bool(parts and parts.query and raw.endswith("="))
    structural = any(c in token for c in "/.?&#=%")
    if trailing_prose and not structural:
        return False
    if explicit_space and not (raw.endswith(tuple(":/.?&#=%-")) or token.startswith(tuple(":/.?&#=%"))):
        return False
    parts = _url_parts(raw)
    # A capitalized plain word after a hostname or sentence-ending punctuation
    # is likely a heading. Keep it out of the URL instead of joining prose.
    if (len(token) > 1 and token.isalpha() and token.istitle() and _valid_url(_clean_url(raw))
            and (not parts.path or raw.endswith(tuple(".,;!")))):
        return False
    return True


def _next_fragment(boxes, current_index, end, origin_xs, visited):
    current = boxes[current_index]
    # OCR sometimes inserts spaces around URL punctuation inside one line box.
    next_token = _TOKEN_REGEX.search(current.text, end)
    if next_token:
        return (current_index, next_token.start(), next_token.end(), next_token.group(),
                bool(current.text[end:next_token.start()]))
    x, y, w, h = current.rect
    same_row = []
    next_row = []
    for i, other in enumerate(boxes):
        if i in visited:
            continue
        nx, ny, nw, nh = other.rect
        if not 0.65 <= nh / max(h, 1) <= 1.5:
            continue
        if abs((ny + nh / 2) - (y + h / 2)) <= 0.35 * max(h, nh):
            if -2 <= nx - (x + w) <= 0.8 * max(h, nh):
                same_row.append((nx, i, other))
        elif (0.65 * h <= ny - y <= 2.0 * max(h, nh)
              and min(abs(nx - origin_x) for origin_x in origin_xs) <= max(h, nh) * 1.5):
            next_row.append((ny, i, other))
    candidates = same_row or next_row
    if not candidates:
        return None
    _, i, other = min(candidates)
    token = _TOKEN_REGEX.search(other.text)
    if token:
        return i, token.start(), token.end(), token.group(), False
    return None


def _span_rect(box, start, end):
    # OCR supplies line boxes, not glyph boxes. Estimate the URL's portion so
    # adjacent prose and multiple URLs on one line remain independently usable.
    x, y, w, h = box.rect
    unit = w / max(1, len(box.text))
    left = round(x + start * unit)
    return left, y, max(1, round(x + end * unit) - left), h


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
    def detect_links(boxes) -> List[LinkEntity]:
        """Assemble spatial OCR fragments first, then validate complete URLs.

        Source spans stay attached to the assembled URL for independent hit
        testing. No network requests, TLD lists or filename-extension lists are
        needed, and punctuation is trimmed only after reconstruction.
        """
        ordered = sorted(boxes, key=lambda b: (b.rect[1], b.rect[0]))
        consumed = set()
        entities = []
        for index, box in enumerate(ordered):
            for start, end, seed in _url_seeds(box.text):
                if any(i == index and a <= start < b for i, a, b in consumed):
                    continue
                raw = seed
                spans = [(index, start, end)]
                current_index = index
                visited = {index}
                origins = (box.rect[0], _span_rect(box, start, end)[0])
                best = None
                while True:
                    # Keep the last complete candidate if later OCR fragments
                    # cannot form a URL (e.g. an unrelated malformed port).
                    candidate = _clean_url(raw)
                    if _valid_url(candidate):
                        best = candidate, tuple(spans)
                    following = _next_fragment(ordered, current_index, end, origins, visited)
                    if following is None:
                        break
                    i, begin, finish, token, explicit_space = following
                    if any(j == i and a <= begin < b for j, a, b in consumed):
                        break
                    trailing_prose = bool(ordered[i].text[finish:].strip())
                    if not _can_continue(raw, token, trailing_prose=trailing_prose, explicit_space=explicit_space):
                        break
                    raw += token
                    spans.append((i, begin, finish))
                    visited.add(i)
                    current_index, end = i, finish
                if best is not None:
                    url, matched_spans = best
                    rects = tuple(_span_rect(ordered[i], a, b) for i, a, b in matched_spans)
                    entities.append(LinkEntity(url, rects))
                    consumed.update(matched_spans)
        return entities

    @staticmethod
    def extract_urls(text: str) -> List[str]:
        return list(dict.fromkeys(_clean_url(match.group()) for match in URL_REGEX.finditer(text)))

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        return EMAIL_REGEX.findall(text)

    @staticmethod
    def open_url(url: str) -> bool:
        if not url.lower().startswith(("http://", "https://")):
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
