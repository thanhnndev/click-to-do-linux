"""Image segmentation and background manipulation module (Cutout, Blur, Erase)."""

from typing import Optional
import numpy as np
from PIL import Image, ImageFilter


class SegmentationEngine:
    """Provides subject isolation, background removal, and blur."""

    _session = None

    @classmethod
    def _get_session(cls):
        if cls._session is None:
            try:
                import rembg
                # Default session uses ONNX Runtime with available accelerator
                cls._session = rembg.new_session("isnet-general-use")
            except Exception as e:
                print(f"[SegmentationEngine] Error initializing rembg session: {e}")
                import rembg
                cls._session = rembg.new_session()
        return cls._session

    @classmethod
    def remove_background(cls, image: Image.Image) -> Optional[Image.Image]:
        """Removes the background from the image, returning a transparent RGBA image."""
        try:
            import rembg
            session = cls._get_session()
            output = rembg.remove(image, session=session)
            return output
        except Exception as e:
            print(f"[SegmentationEngine] Background removal failed: {e}")
            return None

    @classmethod
    def blur_background(cls, image: Image.Image, blur_radius: int = 15) -> Optional[Image.Image]:
        """Blurs the background while keeping the detected subject sharp."""
        try:
            # 1. Get transparent cutout of subject
            cutout = cls.remove_background(image)
            if cutout is None:
                return image.filter(ImageFilter.GaussianBlur(blur_radius))

            # 2. Blur the original image
            blurred_bg = image.convert("RGBA").filter(ImageFilter.GaussianBlur(blur_radius))

            # 3. Alpha composite the sharp cutout over the blurred background
            combined = Image.alpha_composite(blurred_bg, cutout.convert("RGBA"))
            return combined.convert("RGB")
        except Exception as e:
            print(f"[SegmentationEngine] Background blur failed: {e}")
            return None

    @classmethod
    def crop_region(cls, image: Image.Image, rect: tuple[int, int, int, int]) -> Image.Image:
        """Crops an (x, y, w, h) region from the image safely."""
        x, y, w, h = rect
        x = max(0, min(image.width - 1, x))
        y = max(0, min(image.height - 1, y))
        x2 = max(x + 1, min(image.width, x + w))
        y2 = max(y + 1, min(image.height, y + h))
        return image.crop((x, y, x2, y2))
