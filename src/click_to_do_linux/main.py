"""CLI entrypoint and main application for Click to Do Linux."""

import argparse
import os
import sys
from PyQt6.QtWidgets import QApplication

from .capture.screen import ScreenCapture
from .config import load_config
from .hardware import HardwareDetector
from .ui.overlay import OverlayWindow


def run_capture():
    """Captures screen and displays the Click to Do interactive AI overlay."""
    # Ensure Qt Application
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    captured = ScreenCapture.capture()
    if not captured:
        print("[Click to Do] Error: Failed to capture screen. Ensure 'grim' is installed on Wayland.")
        sys.exit(1)

    overlay = OverlayWindow(captured)
    overlay.showFullScreen()
    sys.exit(app.exec())


def show_status():
    """Prints diagnostic report of AI NPUs, GPUs, and Linux environment."""
    report = HardwareDetector.detect()
    print("=" * 60)
    print("           CLICK TO DO LINUX - HARDWARE STATUS")
    print("=" * 60)
    print(f"Desktop Session : {os.environ.get('XDG_CURRENT_DESKTOP', 'unknown')} ({os.environ.get('XDG_SESSION_TYPE', 'unknown')})")
    print(f"CPU             : {report.cpu_name}")
    print(f"NPU Detected    : {report.npu_name or 'None'}")
    if report.npu_device:
        print(f"NPU Device Node : {report.npu_device}")
        print(f"NPU Driver      : {report.npu_driver}")
    print(f"GPUs Detected   : {', '.join(report.gpu_names) if report.gpu_names else 'None'}")
    print(f"ONNX Providers  : {', '.join(report.onnx_providers)}")
    print(f"Active Engine   : {report.active_accelerator}")
    print(f"UI Badge        : {report.badge_text}")
    print("=" * 60)


def show_setup():
    """Shows keyboard shortcut configuration for Niri, Hyprland, Sway, KDE, and GNOME."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    print("=" * 60)
    print("          CLICK TO DO - SHORTCUT INTEGRATION GUIDE")
    print("=" * 60)

    print("\n👉 Dành cho Niri (~/.config/niri/config.kdl):")
    print("""Thêm dòng sau vào block 'binds { ... }':
    Mod+Q { spawn "click-to-do" "capture"; }
    Print { spawn "click-to-do" "capture"; }
""")

    print("👉 Dành cho Hyprland (~/.config/hypr/hyprland.conf):")
    print("""Thêm dòng sau:
    bind = SUPER, Q, exec, click-to-do capture
    bind = , Print, exec, click-to-do capture
""")

    print("👉 Dành cho Sway (~/.config/sway/config):")
    print("""Thêm dòng sau:
    bindsym $mod+q exec click-to-do capture
    bindsym Print exec click-to-do capture
""")

    print("👉 Dành cho KDE Plasma / GNOME:")
    print("Vào Settings -> Keyboard -> Custom Shortcuts -> Thêm shortcut mới:")
    print("Tên: Click to Do")
    print("Lệnh: click-to-do capture")
    print("Phím tắt: Super + Q hoặc PrintScreen")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Click to Do for Linux - AI Copilot+ PC Screen Intelligence")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("capture", help="Trigger screen capture and show interactive AI overlay")
    subparsers.add_parser("status", help="Show NPU / GPU hardware acceleration status")
    subparsers.add_parser("setup", help="Print shortcut configuration guide for desktop compositors")

    args = parser.parse_args()

    if args.command == "status":
        show_status()
    elif args.command == "setup":
        show_setup()
    else:
        # Default behavior: capture and show overlay
        run_capture()


if __name__ == "__main__":
    main()
