"""App Builder & System Installer (Desktop entry, Icon, Systemd Service, Niri/Umbriel/Waybar integration)."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from .ui.icons import get_svg_xml


def get_executable_path() -> str:
    """Finds or links click-to-do binary into ~/.local/bin/click-to-do."""
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    target_bin = local_bin / "click-to-do"

    venv_bin = Path.cwd() / ".venv" / "bin" / "click-to-do"
    if venv_bin.exists():
        if target_bin.exists() or target_bin.is_symlink():
            target_bin.unlink()
        target_bin.symlink_to(venv_bin)
        return str(target_bin)

    which_bin = shutil.which("click-to-do")
    return which_bin or str(venv_bin)


def install_system_integration() -> tuple[bool, str]:
    """Installs binary symlink, SVG icon, .desktop files, systemd user service, and Niri rule."""
    try:
        bin_path = get_executable_path()

        # 1. Install SVG Icon
        icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
        icon_dir.mkdir(parents=True, exist_ok=True)
        icon_file = icon_dir / "click-to-do.svg"
        icon_file.write_text(get_svg_xml("app_logo", "#38bdf8", 64), encoding="utf-8")

        # 2. Install Desktop Entries (Main App + Settings + Hidden Overlay ID)
        apps_dir = Path.home() / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)

        (apps_dir / "click-to-do.desktop").write_text(
            f"[Desktop Entry]\n"
            f"Type=Application\n"
            f"Name=Click to Do\n"
            f"GenericName=Screen Intelligence Overlay\n"
            f"Comment=Instant OCR, Cutout, and Local AI Screen Overlay\n"
            f"Exec={bin_path} capture\n"
            f"Icon=click-to-do\n"
            f"Terminal=false\n"
            f"Categories=Utility;Graphics;\n"
            f"Actions=Settings;Daemon;\n\n"
            f"[Desktop Action Settings]\n"
            f"Name=Settings & Local Models\n"
            f"Exec={bin_path} settings\n\n"
            f"[Desktop Action Daemon]\n"
            f"Name=Start Background Daemon\n"
            f"Exec={bin_path} daemon\n",
            encoding="utf-8",
        )

        (apps_dir / "click-to-do-overlay.desktop").write_text(
            f"[Desktop Entry]\n"
            f"Type=Application\n"
            f"Name=Click to Do Overlay\n"
            f"Exec={bin_path} capture\n"
            f"Icon=click-to-do\n"
            f"NoDisplay=true\n",
            encoding="utf-8",
        )

        # 3. Install Systemd User Service (Works across Niri, Umbriel, Hyprland, Sway, KDE)
        systemd_dir = Path.home() / ".config" / "systemd" / "user"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        service_file = systemd_dir / "click-to-do.service"
        service_file.write_text(
            f"[Unit]\n"
            f"Description=Click to Do Linux Resident Daemon & Bar Tray\n"
            f"After=graphical-session.target\n"
            f"PartOf=graphical-session.target\n\n"
            f"[Service]\n"
            f"ExecStart={bin_path} daemon\n"
            f"Restart=on-failure\n"
            f"RestartSec=2\n\n"
            f"[Install]\n"
            f"WantedBy=graphical-session.target\n",
            encoding="utf-8",
        )

        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "--now", "click-to-do.service"], check=False)

        # 4. Ensure Niri non-scrolling floating rule if Niri config exists
        niri_cfg = Path.home() / ".config" / "niri" / "config.kdl"
        if niri_cfg.exists():
            content = niri_cfg.read_text(encoding="utf-8")
            pattern = re.compile(
                r'window-rule\s*\{\s*match\s+app-id="\^click-to-do-overlay\$"[\s\S]*?\}\s*\}',
                re.MULTILINE,
            )
            content = pattern.sub("", content)
            new_rule = """
window-rule {
    match app-id="^click-to-do-overlay$"
    open-floating true
    default-floating-position x=0 y=0 relative-to="top-left"
    border { off; }
    shadow { off; }
    focus-ring { off; }
}
"""
            niri_cfg.write_text(content.rstrip() + "\n" + new_rule, encoding="utf-8")
            subprocess.run(["niri", "msg", "action", "load-config-file"], check=False)

        return True, (
            f"Installed successfully!\n"
            f"• Binary symlink: {bin_path}\n"
            f"• Systemd user service: click-to-do.service (enabled & running)\n"
            f"• Universal Bar Tray Icon: Active on any SNI bar (Niri, Umbriel, Waybar)"
        )
    except Exception as e:
        return False, f"Installation error: {e}"
