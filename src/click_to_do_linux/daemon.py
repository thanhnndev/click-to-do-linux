"""Resident workday timer, reminders, screen actions, and system tray integration."""

import json
import fcntl
import os
import stat
import sys
import threading
from pathlib import Path

os.environ["QT_LOGGING_RULES"] = "qt.qpa.services.debug=false;qt.qpa.services.warning=false"

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction, QGuiApplication, QIcon
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .ai.ocr import OCREngine
from .i18n import t
from .capture.screen import ScreenCapture
from .productivity import ProductivityService
from .ui.icons import get_icon
from .config import load_config
from .ui.fluent_theme import apply_app_font, sync_fluent_theme
from .ui.palette import theme_color, theme_stylesheet
from .ui.overlay import OverlayWindow
from .ui.workspace import OfficeWindow

SOCKET_NAME = f"click-to-do-{os.getuid()}.sock"
APP_ID = "click-to-do-overlay"


class ClickToDoDaemon:
    """Keep productivity timers, reminders, local models, and tray actions available."""

    def __init__(self):
        QGuiApplication.setDesktopFileName(APP_ID)
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        # Fluent controls must follow the saved palette before any window shows.
        apply_app_font(self.app)
        sync_fluent_theme(load_config().ui_theme)

        self.active_overlay: OverlayWindow | None = None
        self.office_win: OfficeWindow | None = None
        self.already_running = False
        try:
            self._instance_lock = self._acquire_instance_lock()
        except OSError as exc:
            print(f"[Daemon] Cannot acquire instance lock: {exc}")
            sys.exit(1)
        if self._instance_lock is None:
            self.already_running = True
            return

        self.server = QLocalServer()
        if not self.server.listen(SOCKET_NAME):
            if self._another_daemon_is_running():
                self._instance_lock.close()
                self.already_running = True
                return
            QLocalServer.removeServer(SOCKET_NAME)
            if not self.server.listen(SOCKET_NAME):
                if self._another_daemon_is_running():
                    self._instance_lock.close()
                    self.already_running = True
                    return
                print(f"[Daemon] Cannot listen on socket {SOCKET_NAME}")
                sys.exit(1)

        self.server.newConnection.connect(self._on_client_connected)

        # Request a StatusNotifierItem; visibility depends on the active shell/bar providing an SNI host.
        self._init_bar_tray_icon()

        self.office_service = ProductivityService(self.app)
        self.office_service.notification_requested.connect(self._show_notification)

        # Keep slow model initialization out of the UI/event-loop startup path.
        self._ocr_warmup_thread = threading.Thread(
            target=self._warmup_ocr,
            name="click-to-do-ocr-warmup",
            daemon=True,
        )
        self._ocr_warmup_thread.start()
        print(f"[Daemon] Ready; requested tray/SNI icon ({SOCKET_NAME}); OCR warmup runs in background")

    @staticmethod
    def _warmup_ocr() -> None:
        try:
            OCREngine.warmup()
        except Exception as exc:
            print(f"[Daemon] OCR warmup failed; it will initialize on first capture: {exc}")

    @staticmethod
    def _acquire_instance_lock():
        uid = os.getuid()
        runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR", "")).expanduser()
        if not runtime_dir.is_dir() or not os.access(runtime_dir, os.W_OK) or runtime_dir.stat().st_uid != uid:
            runtime_dir = Path.home() / ".cache" / "click-to-do"
            runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = runtime_dir / f"click-to-do-{uid}.lock"
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(lock_path, flags, 0o600)
        try:
            metadata = os.fstat(fd)
            if metadata.st_uid != uid or not stat.S_ISREG(metadata.st_mode):
                raise PermissionError(f"unsafe instance lock file: {lock_path}")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except Exception:
            os.close(fd)
            raise
        handle = os.fdopen(fd, "w", encoding="utf-8")
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        return handle

    @staticmethod
    def _another_daemon_is_running() -> bool:
        probe = QLocalSocket()
        probe.connectToServer(SOCKET_NAME)
        running = probe.waitForConnected(250)
        if running:
            probe.disconnectFromServer()
        return running

    def _init_bar_tray_icon(self):
        icon = QIcon.fromTheme("click-to-do", get_icon("app_logo", "#38bdf8", 22))
        self.app.setWindowIcon(icon)
        self.tray = QSystemTrayIcon(icon, self.app)
        self.tray.setToolTip(t("tray_tooltip"))

        menu = QMenu()
        self._tray_style = """
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
        """

        act_cap = QAction(get_icon("sparkles", "#38bdf8", 14), t("tray_capture"), menu)
        act_cap.triggered.connect(lambda: QTimer.singleShot(120, self.trigger_overlay))
        menu.addAction(act_cap)

        act_office = QAction(get_icon("briefcase", "#38bdf8", 14), t("tray_office"), menu)
        act_office.triggered.connect(self.open_office)
        menu.insertAction(act_cap, act_office)

        act_color = QAction(get_icon("pipette", "#e4e4e7", 14), t("tray_color"), menu)
        act_color.triggered.connect(lambda: QTimer.singleShot(120, lambda: self.trigger_overlay(start_color_picker=True)))
        menu.addAction(act_color)

        menu.addSeparator()

        act_set = QAction(get_icon("settings", "#e4e4e7", 14), t("tray_settings"), menu)
        act_set.triggered.connect(self.open_settings)
        menu.addAction(act_set)

        act_quit = QAction(get_icon("power", "#f87171", 14), t("tray_quit"), menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self._tray_actions = [(act_office, "briefcase", "#38bdf8"), (act_cap, "sparkles", "#38bdf8"), (act_color, "pipette", "#e4e4e7"), (act_set, "settings", "#e4e4e7"), (act_quit, "power", "#f87171")]
        self.tray.setContextMenu(menu)
        self._apply_tray_theme(load_config().ui_theme)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _apply_tray_theme(self, theme):
        self.tray.contextMenu().setStyleSheet(theme_stylesheet(self._tray_style, theme))
        for action, icon, color in self._tray_actions:
            action.setIcon(get_icon(icon, theme_color(color, theme), 14))

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
        elif cmd == "office":
            self.open_office()
        elif cmd == "quit":
            self._quit()

    def trigger_overlay(self, start_color_picker: bool = False):
        if self.active_overlay and self.active_overlay.isVisible():
            self.active_overlay.close()
            self.active_overlay = None
            return

        captured = ScreenCapture.capture()
        if not captured:
            return

        QGuiApplication.setDesktopFileName(APP_ID)
        self.active_overlay = OverlayWindow(captured)
        if start_color_picker:
            self.active_overlay.color_picker_active = True
        self.active_overlay.closed.connect(self._on_overlay_closed)
        self.active_overlay.show_exact_overlay()

    def _ensure_office(self):
        if self.office_win is None:
            self.office_win = OfficeWindow(
                self.office_service,
                on_capture=self._capture_from_office,
                on_quit=self._quit,
            )
            self.office_win.theme_changed.connect(self._apply_tray_theme)
            self.office_win.setWindowIcon(QIcon.fromTheme("click-to-do", get_icon("app_logo", "#38bdf8", 32)))
        return self.office_win

    def _capture_from_office(self, color_mode=False):
        if self.office_win:
            self.office_win.hide()
        QTimer.singleShot(160, lambda: self.trigger_overlay(start_color_picker=color_mode))

    def open_settings(self):
        window = self._ensure_office()
        window.show_settings()
        window.showNormal()
        window.activateWindow()
        window.raise_()

    def open_office(self):
        window = self._ensure_office()
        window.show_page("workbench")
        window.showNormal()
        window.activateWindow()
        window.raise_()

    def _quit(self):
        if self.office_win is not None:
            self.office_win.flush_pending_note()
        self.app.quit()

    def _show_notification(self, title: str, message: str):
        if self.tray.isVisible():
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 8000)

    def _on_overlay_closed(self):
        if self.active_overlay:
            self.active_overlay.deleteLater()
            self.active_overlay = None

    def run(self):
        if self.already_running:
            return
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
        "tooltip": "Click to Do (Left-click: Capture | Right-click: Workbench and Settings)",
        "class": "active" if running else "inactive",
    }
    print(json.dumps(payload, ensure_ascii=False))
