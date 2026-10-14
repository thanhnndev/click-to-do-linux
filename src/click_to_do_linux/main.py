"""Main CLI & Entrypoint for Click to Do Linux."""

import argparse
import os
import sys

os.environ["QT_LOGGING_RULES"] = "qt.qpa.services.debug=false;qt.qpa.services.warning=false"

from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtWidgets import QApplication

from .capture.screen import ScreenCapture
from .config import load_config
from .daemon import APP_ID, ClickToDoDaemon, print_bar_status_json, send_command_to_daemon
from .installer import install_system_integration, uninstall_system_integration
from .ui.icons import get_icon
from .ui.overlay import OverlayWindow
from .ui.setup_window import SetupWindow


def run_capture(color_mode: bool = False):
    cmd = "color" if color_mode else "capture"
    if send_command_to_daemon(cmd):
        return

    QGuiApplication.setDesktopFileName(APP_ID)
    app = QApplication.instance() or QApplication(sys.argv)
    icon = QIcon.fromTheme("click-to-do", get_icon("app_logo", "#38bdf8", 32))
    app.setWindowIcon(icon)

    cfg = load_config()
    if not cfg.setup_completed:
        win = SetupWindow()
        win.setWindowIcon(icon)
        win.show()
        sys.exit(app.exec())

    captured = ScreenCapture.capture()
    if not captured:
        sys.exit(1)

    overlay = OverlayWindow(captured)
    if color_mode:
        overlay.color_picker_active = True
    overlay.show_exact_overlay()
    sys.exit(app.exec())


def run_settings():
    if send_command_to_daemon("settings"):
        return
    QGuiApplication.setDesktopFileName("click-to-do-settings")
    app = QApplication.instance() or QApplication(sys.argv)
    icon = QIcon.fromTheme("click-to-do", get_icon("app_logo", "#38bdf8", 32))
    app.setWindowIcon(icon)
    win = SetupWindow()
    win.setWindowIcon(icon)
    win.show()
    sys.exit(app.exec())


def main():
    parser = argparse.ArgumentParser(description="Click to Do Linux — Screen Intelligence Overlay")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("capture", help="Trigger instant screen overlay")
    subparsers.add_parser("color", help="Trigger screen HEX color picker")
    subparsers.add_parser("daemon", help="Run resident background daemon & bar tray icon")
    subparsers.add_parser("settings", help="Open settings and local AI model manager")
    subparsers.add_parser("install", help="Build and install desktop app, icon, and systemd service")
    uninstall_p = subparsers.add_parser("uninstall", help="Remove desktop app, icon, and systemd service")
    uninstall_p.add_argument("--purge", action="store_true", help="Also delete config and downloaded data")
    subparsers.add_parser("bar-status", help="Output JSON status for custom Waybar/Umbriel modules")
    subparsers.add_parser("stop", help="Stop background daemon")

    args = parser.parse_args()

    if args.command == "daemon":
        ClickToDoDaemon().run()
    elif args.command == "color":
        run_capture(color_mode=True)
    elif args.command == "settings":
        run_settings()
    elif args.command == "install":
        ok, msg = install_system_integration()
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.command == "uninstall":
        ok, msg = uninstall_system_integration(purge_data=args.purge)
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.command == "bar-status":
        print_bar_status_json()
    elif args.command == "stop":
        send_command_to_daemon("quit")
    else:
        run_capture()


if __name__ == "__main__":
    main()
