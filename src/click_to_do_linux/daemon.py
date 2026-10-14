"""Resident Daemon with Universal Bar Quick-Action Tray Icon (StatusNotifierItem) & Unix Socket."""

import json
import os
import sys

os.environ["QT_LOGGING_RULES"] = "qt.qpa.services.debug=false;qt.qpa.services.warning=false"

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QGuiApplication, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .ai.ocr import OCREngine
from .i18n import t
from .capture.screen import ScreenCapture
from .ui.icons import get_icon
from .ui.overlay import OverlayWindow
from .ui.setup_window import SetupWindow

SOCKET_NAME = f"click-to-do-{os.getuid()}.sock"
APP_ID = "click-to-do-overlay"


class ClickToDoDaemon:
    """Resident daemon providing 0ms overlay trigger and universal bar Quick Action icon."""

    def __init__(self):
        QGuiApplication.setDesktopFileName(APP_ID)
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.active_overlay: OverlayWindow | None = None
        self.settings_win: SetupWindow | None = None

        self.server = QLocalServer()
        QLocalServer.removeServer(SOCKET_NAME)
        if not self.server.listen(SOCKET_NAME):
            print(f"[Daemon] Cannot listen on socket {SOCKET_NAME}")
            sys.exit(1)

        self.server.newConnection.connect(self._on_client_connected)

        # Initialize Universal Bar Quick Action Icon (StatusNotifierItem / SystemTray)
        # Works out-of-the-box on Dank Material Shell, Umbriel, Waybar, Quickshell, KDE, etc.
        self._init_bar_tray_icon()

        # Pre-warm OCR model in RAM
        OCREngine.warmup()
        print(f"[Daemon] Ready & Bar Icon active ({SOCKET_NAME})")

    def _init_bar_tray_icon(self):
        icon = QIcon.fromTheme("click-to-do", get_icon("app_logo", "#38bdf8", 22))
        self.app.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip(t("tray_tooltip"))

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #141418;
                border: 1px solid #27272a;
                border-radius: 8px;
                padding: 4px;
                color: #e4e4e7;
                font-size: 12px;
            }
            QMenu::item { padding: 6px 18px 6px 10px; border-radius: 5px; }
            QMenu::item:selected { background-color: #27272a; color: #ffffff; }
        """)

        act_cap = QAction(get_icon("sparkles", "#38bdf8", 14), t("tray_capture"), menu)
        act_cap.triggered.connect(lambda: QTimer.singleShot(120, self.trigger_overlay))
        menu.addAction(act_cap)

        act_color = QAction(get_icon("pipette", "#e4e4e7", 14), t("tray_color"), menu)
        act_color.triggered.connect(lambda: QTimer.singleShot(120, lambda: self.trigger_overlay(start_color_picker=True)))
        menu.addAction(act_color)

        menu.addSeparator()

        act_set = QAction(get_icon("settings", "#e4e4e7", 14), t("tray_settings"), menu)
        act_set.triggered.connect(self.open_settings)
        menu.addAction(act_set)

        act_quit = QAction(get_icon("power", "#f87171", 14), t("tray_quit"), menu)
        act_quit.triggered.connect(self.app.quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        # Single Left-Click on Bar Icon -> Immediately trigger Click to Do overlay!
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            QTimer.singleShot(80, self.trigger_overlay)
        # Middle-Click on Bar Icon -> Immediately trigger Color Picker mode!
        elif reason == QSystemTrayIcon.ActivationReason.MiddleClick:
            QTimer.singleShot(80, lambda: self.trigger_overlay(start_color_picker=True))

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
        elif cmd == "color":
            self.trigger_overlay(start_color_picker=True)
        elif cmd == "settings":
            self.open_settings()
        elif cmd == "quit":
            self.app.quit()

    def trigger_overlay(self, start_color_picker: bool = False):
        if self.active_overlay and self.active_overlay.isVisible():
            self.active_overlay.close()
            self.active_overlay = None
            return

        captured = ScreenCapture.capture()
        if not captured:
            return

        self.active_overlay = OverlayWindow(captured)
        if start_color_picker:
            self.active_overlay.color_picker_active = True
        self.active_overlay.closed.connect(self._on_overlay_closed)
        self.active_overlay.show_exact_overlay()

    def open_settings(self):
        if self.settings_win and self.settings_win.isVisible():
            self.settings_win.activateWindow()
            self.settings_win.raise_()
            return
        self.settings_win = SetupWindow()
        self.settings_win.setWindowIcon(QIcon.fromTheme("click-to-do", get_icon("app_logo", "#38bdf8", 32)))
        self.settings_win.show()

    def _on_overlay_closed(self):
        if self.active_overlay:
            self.active_overlay.deleteLater()
            self.active_overlay = None

    def run(self):
        sys.exit(self.app.exec())


def send_command_to_daemon(cmd: str = "capture") -> bool:
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if sock.waitForConnected(120):
        sock.write(cmd.encode("utf-8"))
        sock.waitForBytesWritten(120)
        sock.waitForReadyRead(120)
        sock.disconnectFromServer()
        return True
    return False


def print_bar_status_json():
    """Outputs Waybar / Umbriel / Quickshell compatible JSON status for custom bar buttons."""
    running = False
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if sock.waitForConnected(80):
        running = True
        sock.disconnectFromServer()

    payload = {
        "text": "󰆞",
        "alt": "ready" if running else "offline",
        "tooltip": "Click to Do (Left-click: Capture | Right-click: Settings)",
        "class": "active" if running else "inactive",
    }
    print(json.dumps(payload, ensure_ascii=False))
