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

        # 1. Install Scalable SVG Icon & PNG Icons across all standard resolutions
        hicolor_dir = Path.home() / ".local" / "share" / "icons" / "hicolor"
        assets_dir = Path(__file__).resolve().parent.parent.parent / "assets"

        # Scalable SVG
        scalable_dir = hicolor_dir / "scalable" / "apps"
        scalable_dir.mkdir(parents=True, exist_ok=True)
        icon_file = scalable_dir / "click-to-do.svg"
        project_svg = assets_dir / "icon.svg"
        if project_svg.exists():
            shutil.copy2(project_svg, icon_file)
        else:
            icon_file.write_text(get_svg_xml("app_logo", "#38bdf8", 64), encoding="utf-8")

        # Multi-resolution PNGs (16x16 up to 512x512)
        for sz in (16, 24, 32, 48, 64, 128, 256, 512):
            sz_dir = hicolor_dir / f"{sz}x{sz}" / "apps"
            sz_dir.mkdir(parents=True, exist_ok=True)
            sz_src = assets_dir / f"icon-{sz}.png"
            if sz_src.exists():
                shutil.copy2(sz_src, sz_dir / "click-to-do.png")
            elif (assets_dir / "icon.png").exists():
                shutil.copy2(assets_dir / "icon.png", sz_dir / "click-to-do.png")

        # Fallback Pixmaps and user root icon folders
        pixmaps_dir = Path.home() / ".local" / "share" / "pixmaps"
        pixmaps_dir.mkdir(parents=True, exist_ok=True)
        if (assets_dir / "icon.png").exists():
            shutil.copy2(assets_dir / "icon.png", pixmaps_dir / "click-to-do.png")
            shutil.copy2(assets_dir / "icon.png", Path.home() / ".local" / "share" / "icons" / "click-to-do.png")
        if (assets_dir / "icon.svg").exists():
            shutil.copy2(assets_dir / "icon.svg", pixmaps_dir / "click-to-do.svg")
            shutil.copy2(assets_dir / "icon.svg", Path.home() / ".local" / "share" / "icons" / "click-to-do.svg")

        # Rebuild GTK Icon Theme cache so DEs/DMS reload immediately
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(hicolor_dir)], check=False)

        # 2. Install Desktop Entries (Main App + Settings App + Hidden Overlay ID)
        apps_dir = Path.home() / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)

        app_desktop = apps_dir / "click-to-do.desktop"
        app_desktop.write_text(
            f"[Desktop Entry]\n"
            f"Type=Application\n"
            f"Name=Click to Do\n"
            f"GenericName=Screen Intelligence Overlay\n"
            f"Comment=Instant OCR, Cutout, and Local AI Screen Overlay\n"
            f"Exec={bin_path} capture\n"
            f"Icon=click-to-do\n"
            f"Terminal=false\n"
            f"StartupWMClass=click-to-do-overlay\n"
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

        settings_desktop = apps_dir / "click-to-do-settings.desktop"
        settings_desktop.write_text(
            f"[Desktop Entry]\n"
            f"Type=Application\n"
            f"Name=Click to Do Settings\n"
            f"GenericName=Settings & Local AI Model Manager\n"
            f"Comment=Configure Click to Do overlay, local AI models (Ollama), and preferences\n"
            f"Exec={bin_path} settings\n"
            f"Icon=click-to-do\n"
            f"Terminal=false\n"
            f"StartupWMClass=click-to-do-settings\n"
            f"Categories=Utility;Settings;Graphics;\n",
            encoding="utf-8",
        )

        overlay_desktop = apps_dir / "click-to-do-overlay.desktop"
        overlay_desktop.write_text(
            f"[Desktop Entry]\n"
            f"Type=Application\n"
            f"Name=Click to Do Overlay\n"
            f"Exec={bin_path} capture\n"
            f"Icon=click-to-do\n"
            f"NoDisplay=true\n",
            encoding="utf-8",
        )

        # 3. Create desktop shortcuts on ~/Desktop if directory exists
        desktop_dir = Path.home() / "Desktop"
        if desktop_dir.exists():
            shutil.copy2(app_desktop, desktop_dir / "click-to-do.desktop")
            shutil.copy2(settings_desktop, desktop_dir / "click-to-do-settings.desktop")
            (desktop_dir / "click-to-do.desktop").chmod(0o755)
            (desktop_dir / "click-to-do-settings.desktop").chmod(0o755)

        subprocess.run(["update-desktop-database", str(apps_dir)], check=False)

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


def uninstall_system_integration(purge_data: bool = False) -> tuple[bool, str]:
    """Reverses install_system_integration(). Keeps user data unless purge_data is True."""
    removed: list[str] = []
    home = Path.home()
    try:
        subprocess.run(["systemctl", "--user", "disable", "--now", "click-to-do.service"], check=False)
        subprocess.run(["pkill", "-f", "click-to-do daemon"], check=False)

        targets = [
            home / ".config" / "systemd" / "user" / "click-to-do.service",
            home / ".local" / "share" / "applications" / "click-to-do.desktop",
            home / ".local" / "share" / "applications" / "click-to-do-settings.desktop",
            home / ".local" / "share" / "applications" / "click-to-do-overlay.desktop",
            home / "Desktop" / "click-to-do.desktop",
            home / "Desktop" / "click-to-do-settings.desktop",
            home / ".local" / "share" / "pixmaps" / "click-to-do.png",
            home / ".local" / "share" / "pixmaps" / "click-to-do.svg",
            home / ".local" / "share" / "icons" / "click-to-do.png",
            home / ".local" / "share" / "icons" / "click-to-do.svg",
            home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "click-to-do.svg",
        ]
        for sz in (16, 24, 32, 48, 64, 128, 256, 512):
            targets.append(home / ".local" / "share" / "icons" / "hicolor" / f"{sz}x{sz}" / "apps" / "click-to-do.png")

        bin_link = home / ".local" / "bin" / "click-to-do"
        if bin_link.is_symlink():  # only remove our own symlink, never a real file
            targets.append(bin_link)

        for p in targets:
            if p.exists() or p.is_symlink():
                p.unlink()
                removed.append(str(p))

        try:
            from . import compositor

            removed += compositor.remove()
        except Exception:
            pass

        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(home / ".local" / "share" / "icons" / "hicolor")], check=False)
        subprocess.run(["update-desktop-database", str(home / ".local" / "share" / "applications")], check=False)

        # Niri window rule
        niri_cfg = home / ".config" / "niri" / "config.kdl"
        if niri_cfg.exists():
            content = niri_cfg.read_text(encoding="utf-8")
            pattern = re.compile(
                r'\n?window-rule\s*\{\s*match\s+app-id="\^click-to-do-overlay\$"[\s\S]*?\}\s*\}\n?',
                re.MULTILINE,
            )
            new_content = pattern.sub("\n", content)
            if new_content != content:
                niri_cfg.write_text(new_content.rstrip() + "\n", encoding="utf-8")
                subprocess.run(["niri", "msg", "action", "load-config-file"], check=False)
                removed.append(f"{niri_cfg} (window-rule)")

        if purge_data:
            for d in (home / ".config" / "click-to-do", home / ".local" / "share" / "click-to-do"):
                if d.exists():
                    shutil.rmtree(d, ignore_errors=True)
                    removed.append(str(d))

        note = "" if purge_data else "\nConfig and downloaded data kept (use --purge to delete)."
        return True, f"Uninstalled. Removed {len(removed)} item(s).{note}"
    except Exception as e:
        return False, f"Uninstall error: {e}"
