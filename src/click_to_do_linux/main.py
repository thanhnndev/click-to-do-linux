"""Main CLI & Entrypoint for Click to Do Linux."""

import argparse
import os
import sys

os.environ["QT_LOGGING_RULES"] = "qt.qpa.services.debug=false;qt.qpa.services.warning=false"

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from .capture.screen import ScreenCapture
from .config import load_config
from .daemon import APP_ID, ClickToDoDaemon, send_command_to_daemon
from .ui.overlay import OverlayWindow
from .ui.setup_window import SetupWindow


def run_capture():
    if send_command_to_daemon("capture"):
        return

    QGuiApplication.setDesktopFileName(APP_ID)
    app = QApplication.instance() or QApplication(sys.argv)

    cfg = load_config()
    if not cfg.setup_completed:
        win = SetupWindow()
        win.show()
        sys.exit(app.exec())

    captured = ScreenCapture.capture()
    if not captured:
        sys.exit(1)

    overlay = OverlayWindow(captured)
    overlay.show_exact_overlay()
    sys.exit(app.exec())


def run_settings():
    QGuiApplication.setDesktopFileName(APP_ID)
    app = QApplication.instance() or QApplication(sys.argv)
    win = SetupWindow()
    win.show()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="Click to Do Linux")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("capture", help="Trigger instant screen overlay")
    subparsers.add_parser("daemon", help="Run background daemon")
    subparsers.add_parser("settings", help="Open settings and model manager")
    subparsers.add_parser("stop", help="Stop background daemon")

    args = parser.parse_args()

    if args.command == "daemon":
        ClickToDoDaemon().run()
    elif args.command == "settings":
        run_settings()
    elif args.command == "stop":
        send_command_to_daemon("quit")
    else:
        run_capture()


if __name__ == "__main__":
    main()
