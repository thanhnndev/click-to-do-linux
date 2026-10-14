"""Subject cutout, background blur, and privacy pixelation/redaction engine."""

from typing import Optional
from PIL import Image, ImageFilter
from ..config import load_config


class SegmentationEngine:
    _session = None
    _current_model = None

    @classmethod
    def get_session(cls, model_name: Optional[str] = None):
        if model_name is None:
            model_name = load_config().bg_removal_model
        if cls._session is None or cls._current_model != model_name:
            import rembg
            cls._session = rembg.new_session(model_name)
            cls._current_model = model_name
        return cls._session

    @classmethod
    def remove_background(cls, image: Image.Image) -> Optional[Image.Image]:
        try:
            import rembg
            session = cls.get_session()
            return rembg.remove(image, session=session)
        except Exception as e:
            print(f"[SegmentationEngine] Cutout error: {e}")
            return None

    @classmethod
    def blur_background(cls, image: Image.Image, blur_radius: int = 16) -> Optional[Image.Image]:
        try:
            cutout = cls.remove_background(image)
            if cutout is None:
                return image.filter(ImageFilter.GaussianBlur(blur_radius))
            blurred_bg = image.convert("RGBA").filter(ImageFilter.GaussianBlur(blur_radius))
            return Image.alpha_composite(blurred_bg, cutout.convert("RGBA")).convert("RGB")
        except Exception as e:
            print(f"[SegmentationEngine] Blur error: {e}")
            return None

    @classmethod
    def pixelate_image(cls, image: Image.Image, pixel_size: int = 14) -> Image.Image:
        """Pixelates/redacts sensitive region."""
        w, h = image.size
        small_w = max(1, w // pixel_size)
        small_h = max(1, h // pixel_size)
        small = image.resize((small_w, small_h), Image.Resampling.BILINEAR)
        return small.resize((w, h), Image.Resampling.NEAREST)

    @classmethod
    def crop_logical_region(
        cls, image: Image.Image, logical_rect: tuple[int, int, int, int], scale: float
    ) -> Image.Image:
        lx, ly, lw, lh = logical_rect
        x1 = max(0, int(lx * scale))
        y1 = max(0, int(ly * scale))
        x2 = min(image.width, int((lx + lw) * scale))
        y2 = min(image.height, int((ly + lh) * scale))
        return image.crop((x1, y1, max(x1 + 1, x2), max(y1 + 1, y2)))
