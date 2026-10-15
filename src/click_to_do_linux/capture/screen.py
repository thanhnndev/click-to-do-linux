"""Zero-disk PPM capture targeted to the compositor's focused output."""

import json
import os
import shutil
import socket
import struct
import subprocess
from dataclasses import dataclass
from typing import Optional, Tuple
from PIL import Image
from PyQt6.QtGui import QCursor, QGuiApplication, QImage, QPixmap, QScreen
from ..compositor import detect as detect_compositor


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
    def _run_json_command(cmd: list[str]):
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=0.25,
            check=True,
        )
        return json.loads(res.stdout.decode("utf-8"))

    @staticmethod
    def _get_wayfire_focused_output() -> Tuple[Optional[str], float, int, int]:
        socket_path = os.environ.get("WAYFIRE_SOCKET")
        if not socket_path:
            return None, 1.0, 0, 0
        try:
            request = json.dumps({
                "method": "window-rules/get-focused-output",
                "data": {},
            }).encode("utf-8")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.settimeout(0.25)
                conn.connect(socket_path)
                conn.sendall(struct.pack("<I", len(request)) + request)

                header = ScreenCapture._recv_exact(conn, 4)
                reply_size = struct.unpack("<I", header)[0]
                reply = json.loads(ScreenCapture._recv_exact(conn, reply_size).decode("utf-8"))
            output = reply.get("info", reply)
            geometry = output.get("geometry", {})
            return (
                output.get("name"),
                float(output.get("scale", 1.0)),
                int(geometry.get("width", output.get("width", 0))),
                int(geometry.get("height", output.get("height", 0))),
            )
        except Exception:
            return None, 1.0, 0, 0

    @staticmethod
    def _recv_exact(conn: socket.socket, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = conn.recv(size - len(chunks))
            if not chunk:
                raise ConnectionError("Wayfire IPC closed before sending a complete reply")
            chunks.extend(chunk)
        return bytes(chunks)

    @staticmethod
    def _get_umbriel_focused_output() -> Tuple[Optional[str], float, int, int]:
        if not shutil.which("umbriel"):
            return None, 1.0, 0, 0
        try:
            outputs = ScreenCapture._run_json_command(["umbriel", "outputs", "--json"])
            focused = next(
                (output for output in outputs if output.get("focused") and output.get("enabled", True)),
                None,
            )
            if not focused:
                return None, 1.0, 0, 0
            logical = focused.get("logical_size", {})
            return (
                focused.get("name"),
                float(focused.get("scale", 1.0)),
                int(logical.get("width", 0)),
                int(logical.get("height", 0)),
            )
        except Exception:
            return None, 1.0, 0, 0

    @staticmethod
    def _get_hyprland_focused_output() -> Tuple[Optional[str], float, int, int]:
        if not shutil.which("hyprctl"):
            return None, 1.0, 0, 0
        try:
            monitors = ScreenCapture._run_json_command(["hyprctl", "-j", "monitors"])
            focused = next((monitor for monitor in monitors if monitor.get("focused")), None)
            if not focused:
                return None, 1.0, 0, 0
            scale = float(focused.get("scale", 1.0))
            logical_w = focused.get("scaledWidth") or round(float(focused.get("width", 0)) / scale)
            logical_h = focused.get("scaledHeight") or round(float(focused.get("height", 0)) / scale)
            return focused.get("name"), scale, int(logical_w), int(logical_h)
        except Exception:
            return None, 1.0, 0, 0

    @staticmethod
    def _get_sway_focused_output() -> Tuple[Optional[str], float, int, int]:
        if not shutil.which("swaymsg"):
            return None, 1.0, 0, 0
        try:
            workspaces = ScreenCapture._run_json_command(["swaymsg", "-t", "get_workspaces", "-r"])
            focused_workspace = next((workspace for workspace in workspaces if workspace.get("focused")), None)
            if not focused_workspace:
                return None, 1.0, 0, 0
            name = focused_workspace.get("output")
            outputs = ScreenCapture._run_json_command(["swaymsg", "-t", "get_outputs", "-r"])
            output = next((item for item in outputs if item.get("name") == name and item.get("active")), None)
            if not output:
                return name, 1.0, 0, 0
            rect = output.get("rect", {})
            return name, float(output.get("scale", 1.0)), int(rect.get("width", 0)), int(rect.get("height", 0))
        except Exception:
            return None, 1.0, 0, 0

    @staticmethod
    def _get_niri_focused_output() -> Tuple[Optional[str], float, int, int]:
        if not shutil.which("niri"):
            return None, 1.0, 0, 0
        try:
            data = ScreenCapture._run_json_command(["niri", "msg", "-j", "focused-output"])
            name = data.get("name")
            logical = data.get("logical", {})
            scale = float(logical.get("scale", 1.0))
            lw = int(logical.get("width", 0))
            lh = int(logical.get("height", 0))
            return name, scale, lw, lh
        except Exception:
            return None, 1.0, 0, 0

    @staticmethod
    def _get_focused_output() -> Tuple[Optional[str], float, int, int]:
        resolver = {
            "umbriel": ScreenCapture._get_umbriel_focused_output,
            "niri": ScreenCapture._get_niri_focused_output,
            "hyprland": ScreenCapture._get_hyprland_focused_output,
            "sway": ScreenCapture._get_sway_focused_output,
            "wayfire": ScreenCapture._get_wayfire_focused_output,
        }.get(detect_compositor().id)
        return resolver() if resolver else (None, 1.0, 0, 0)

    @staticmethod
    def _find_matching_qt_screen(output_name: Optional[str]) -> Optional[QScreen]:
        screens = QGuiApplication.screens()
        if output_name:
            for s in screens:
                if s.name() == output_name:
                    return s
            # Keep compositor-reported output dimensions if Qt cannot map the
            # output name to a QScreen.
            return None
        cursor_screen = QGuiApplication.screenAt(QCursor.pos())
        if cursor_screen:
            return cursor_screen
        return QGuiApplication.primaryScreen()

    @staticmethod
    def capture() -> Optional[CapturedScreen]:
        output_name, output_scale, output_lw, output_lh = ScreenCapture._get_focused_output()
        qt_screen = ScreenCapture._find_matching_qt_screen(output_name)
        if not output_name and qt_screen:
            output_name = qt_screen.name() or None

        cmd = ["grim", "-t", "ppm"]
        if output_name:
            cmd.extend(["-o", output_name])
        elif qt_screen:
            geom = qt_screen.geometry()
            if geom.width() <= 0 or geom.height() <= 0:
                return None
            cmd.extend(["-g", f"{geom.x()},{geom.y()} {geom.width()}x{geom.height()}"])
        else:
            # Fail closed if no screen can be identified. grim without -o/-g
            # captures the whole desktop, which is the bug this prevents.
            return None
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
            elif output_lw > 0 and output_lh > 0:
                logical_w, logical_h = output_lw, output_lh
                scale = output_scale
            else:
                scale = output_scale if output_scale > 0 else 1.0
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
