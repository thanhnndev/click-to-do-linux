"""Zero-disk PPM pipe capture synchronized 1:1 with Niri output and Qt geometry."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple
from PIL import Image
from PyQt6.QtGui import QGuiApplication, QImage, QPixmap, QScreen


@dataclass
class CapturedScreen:
    image: Image.Image
    pixmap: QPixmap
    physical_w: int
    physical_h: int
    logical_w: int
    logical_h: int
    scale_factor: float
    qt_screen: Optional[QScreen] = None
    output_name: str = ""


class ScreenCapture:
    @staticmethod
    def _get_niri_focused_output() -> Tuple[Optional[str], float, int, int]:
        if not shutil.which("niri"):
            return None, 1.0, 0, 0
        try:
            res = subprocess.run(
                ["niri", "msg", "-j", "focused-output"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=0.25,
                check=True,
            )
            data = json.loads(res.stdout.decode("utf-8"))
            name = data.get("name")
            logical = data.get("logical", {})
            scale = float(logical.get("scale", 1.0))
            lw = int(logical.get("width", 0))
            lh = int(logical.get("height", 0))
            return name, scale, lw, lh
        except Exception:
            return None, 1.0, 0, 0

    @staticmethod
    def _find_matching_qt_screen(output_name: Optional[str]) -> Optional[QScreen]:
        screens = QGuiApplication.screens()
        if output_name:
            for s in screens:
                if s.name() == output_name:
                    return s
        return QGuiApplication.primaryScreen()

    @staticmethod
    def capture() -> Optional[CapturedScreen]:
        output_name, niri_scale, niri_lw, niri_lh = ScreenCapture._get_niri_focused_output()
        qt_screen = ScreenCapture._find_matching_qt_screen(output_name)

        cmd = ["grim", "-t", "ppm"]
        if output_name:
            cmd.extend(["-o", output_name])
        cmd.append("-")

        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            qimg = QImage.fromData(proc.stdout, "PPM")
            if qimg.isNull():
                return None

            phys_w, phys_h = qimg.width(), qimg.height()

            # Use Qt's exact screen geometry if available so drawing & mouse events never drift
            if qt_screen:
                geom = qt_screen.geometry()
                logical_w, logical_h = geom.width(), geom.height()
                scale = phys_w / float(logical_w) if logical_w > 0 else qt_screen.devicePixelRatio()
            elif niri_lw > 0 and niri_lh > 0:
                logical_w, logical_h = niri_lw, niri_lh
                scale = niri_scale
            else:
                scale = niri_scale if niri_scale > 0 else 1.0
                logical_w = int(round(phys_w / scale))
                logical_h = int(round(phys_h / scale))

            pixmap = QPixmap.fromImage(qimg)
            pixmap.setDevicePixelRatio(scale)

            qimg_rgb = qimg.convertToFormat(QImage.Format.Format_RGB888)
            ptr = qimg_rgb.constBits()
            ptr.setsize(phys_h * qimg_rgb.bytesPerLine())
            pil_img = Image.frombuffer(
                "RGB", (phys_w, phys_h), bytes(ptr), "raw", "RGB", qimg_rgb.bytesPerLine(), 1
            )

            return CapturedScreen(
                image=pil_img,
                pixmap=pixmap,
                physical_w=phys_w,
                physical_h=phys_h,
                logical_w=logical_w,
                logical_h=logical_h,
                scale_factor=scale,
                qt_screen=qt_screen,
                output_name=output_name or "",
            )
        except Exception as e:
            print(f"[ScreenCapture] Error: {e}")
            return None
