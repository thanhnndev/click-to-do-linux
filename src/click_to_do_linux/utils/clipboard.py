"""Clipboard manager with native Wayland (wl-copy) and Qt clipboard support."""

import io
import shutil
import subprocess
from typing import Optional
from PIL import Image
from PyQt6.QtGui import QClipboard, QGuiApplication, QImage, QPixmap


class ClipboardManager:
    """Copies text and images to clipboard seamlessly on Wayland and X11."""

    @staticmethod
    def copy_text(text: str) -> bool:
        if not text:
            return False

        # Try wl-copy on Wayland
        if shutil.which("wl-copy"):
            try:
                proc = subprocess.Popen(["wl-copy", "--type", "text/plain"], stdin=subprocess.PIPE)
                proc.communicate(input=text.encode("utf-8"))
                return proc.returncode == 0
            except Exception as e:
                print(f"[Clipboard] wl-copy text error: {e}")

        # Fallback to Qt clipboard
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text, QClipboard.Mode.Clipboard)
            return True

        return False

    @staticmethod
    def copy_image(image: Image.Image) -> bool:
        if not image:
            return False

        # Convert PIL Image to PNG bytes
        bio = io.BytesIO()
        image.save(bio, format="PNG")
        png_data = bio.getvalue()

        # Try wl-copy on Wayland
        if shutil.which("wl-copy"):
            try:
                proc = subprocess.Popen(["wl-copy", "--type", "image/png"], stdin=subprocess.PIPE)
                proc.communicate(input=png_data)
                return proc.returncode == 0
            except Exception as e:
                print(f"[Clipboard] wl-copy image error: {e}")

        # Fallback to Qt clipboard
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            qimg = QImage()
            qimg.loadFromData(png_data, "PNG")
            clipboard.setImage(qimg, QClipboard.Mode.Clipboard)
            return True

        return False
