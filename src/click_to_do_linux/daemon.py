"""Background Resident Daemon with zero DBus warnings and instant Niri floating trigger."""

import os
import sys
from pathlib import Path

# Suppress unnecessary xdg-desktop-portal registration warning before importing Qt
os.environ["QT_LOGGING_RULES"] = "qt.qpa.services.debug=false;qt.qpa.services.warning=false"

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication

from .ai.ocr import OCREngine
from .capture.screen import ScreenCapture
from .ui.overlay import OverlayWindow

SOCKET_NAME = f"click-to-do-{os.getuid()}.sock"
APP_ID = "click-to-do-overlay"


class ClickToDoDaemon:
    def __init__(self):
        QGuiApplication.setDesktopFileName(APP_ID)
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.active_overlay: OverlayWindow | None = None
        self.server = QLocalServer()
        QLocalServer.removeServer(SOCKET_NAME)
        if not self.server.listen(SOCKET_NAME):
            print(f"[Daemon] Cannot listen on socket {SOCKET_NAME}")
            sys.exit(1)

        self.server.newConnection.connect(self._on_client_connected)

        OCREngine.warmup()
        print(f"[Daemon] Ready ({SOCKET_NAME})")

    def _on_client_connected(self):
        conn = self.server.nextPendingConnection()
        if not conn:
            return
        conn.readyRead.connect(lambda: self._handle_command(conn))

    def _handle_command(self, conn: QLocalSocket):
        cmd = bytes(conn.readAll()).decode("utf-8").strip()
        conn.write(b"OK")
        conn.flush()
        conn.disconnectFromServer()

        if cmd == "capture":
            self.trigger_overlay()
        elif cmd == "quit":
            self.app.quit()

    def trigger_overlay(self):
        if self.active_overlay and self.active_overlay.isVisible():
            self.active_overlay.close()
            self.active_overlay = None
            return

        captured = ScreenCapture.capture()
        if not captured:
            return

        self.active_overlay = OverlayWindow(captured)
        self.active_overlay.closed.connect(self._on_overlay_closed)
        self.active_overlay.show_exact_overlay()

    def _on_overlay_closed(self):
        if self.active_overlay:
            self.active_overlay.deleteLater()
            self.active_overlay = None

    def run(self):
        sys.exit(self.app.exec())


def send_command_to_daemon(cmd: str = "capture") -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if sock.waitForConnected(150):
        sock.write(cmd.encode("utf-8"))
        sock.waitForBytesWritten(150)
        sock.waitForReadyRead(150)
        sock.disconnectFromServer()
        return True
    return False
