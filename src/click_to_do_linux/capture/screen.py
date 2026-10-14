"""High-performance screen capture module for Wayland and X11."""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from PyQt6.QtGui import QImage, QPixmap


@dataclass
class CapturedScreen:
    image: Image.Image
    pixmap: QPixmap
    width: int
    height: int
    temp_path: Optional[str] = None


class ScreenCapture:
    """Captures the active desktop screen with lowest possible latency."""

    @staticmethod
    def capture() -> Optional[CapturedScreen]:
        # Try grim first on Wayland
        if shutil.which("grim"):
            captured = ScreenCapture._capture_with_grim()
            if captured:
                return captured

        # Fallback to Qt grabWindow
        return ScreenCapture._capture_with_qt()

    @staticmethod
    def _capture_with_grim() -> Optional[CapturedScreen]:
        # Use /dev/shm (shared memory) for instantaneous in-memory file write
        shm_dir = Path("/dev/shm")
        if shm_dir.is_dir() and os.access(shm_dir, os.W_OK):
            target_path = str(shm_dir / f"click_to_do_{os.getpid()}.png")
        else:
            target_path = os.path.join(tempfile.gettempdir(), f"click_to_do_{os.getpid()}.png")

        try:
            # -t png for lossless quality
            cmd = ["grim", "-t", "png", target_path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            
            if not os.path.exists(target_path):
                return None

            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtGui import QGuiApplication
            if not QGuiApplication.instance():
                _app = QApplication(["click-to-do"])

            pil_img = Image.open(target_path).convert("RGB")
            pixmap = QPixmap(target_path)
            w, h = pil_img.size

            return CapturedScreen(
                image=pil_img,
                pixmap=pixmap,
                width=w,
                height=h,
                temp_path=target_path
            )
        except Exception as e:
            print(f"[ScreenCapture] grim capture error: {e}")
            if os.path.exists(target_path):
                try:
                    os.unlink(target_path)
                except Exception:
                    pass
            return None

    @staticmethod
    def _capture_with_qt() -> Optional[CapturedScreen]:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QGuiApplication

        app = QApplication.instance()
        if not app:
            app = QApplication(["click-to-do"])

        screen = QGuiApplication.primaryScreen()
        if not screen:
            return None

        pixmap = screen.grabWindow(0)
        qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
        w, h = qimg.width(), qimg.height()
        
        ptr = qimg.bits()
        ptr.setsize(h * w * 3)
        pil_img = Image.frombuffer("RGB", (w, h), bytes(ptr), "raw", "RGB", 0, 1)

        return CapturedScreen(
            image=pil_img,
            pixmap=pixmap,
            width=w,
            height=h,
            temp_path=None
        )
