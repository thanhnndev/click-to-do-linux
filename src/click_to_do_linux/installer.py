"""Install XDG desktop integration and session-aware background startup."""

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .ui.icons import get_svg_xml


def _xdg_data_home() -> Path:
    value = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")).expanduser()
    return value if value.is_absolute() else Path.home() / ".local" / "share"


def _xdg_config_home() -> Path:
    value = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
    return value if value.is_absolute() else Path.home() / ".config"


def _write_text(path: Path, content: str) -> None:
    """Atomically write a user-owned integration file without following a stale symlink."""
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() and not path.is_symlink() else 0o644
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        temp_path.chmod(mode)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def _desktop_arg(value: str) -> str:
    """Quote one argument using the Desktop Entry Exec field rules."""
    escaped = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("`", "\\`")
        .replace("$", "\\$")
        .replace("%", "%%")
    )
    return f'"{escaped}"'


def _desktop_exec(*args: str) -> str:
    return " ".join(_desktop_arg(arg) for arg in args)


def _systemd_arg(value: str) -> str:
    """Quote an ExecStart argument and escape systemd specifiers/environment markers."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
    return f'"{escaped}"'


def _run(command: list[str], timeout: float = 8) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _systemctl(*args: str) -> subprocess.CompletedProcess | None:
    executable = shutil.which("systemctl")
    if not executable:
        return None
    try:
        return _run([executable, "--user", *args])
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess([executable, "--user", *args], 1, "", str(exc))


def get_executable_path() -> str:
    """Find the installed entry point or expose the active checkout's entry point."""
    found = shutil.which("click-to-do")
    if found:
        return found

    local_bin = Path.home() / ".local" / "bin"
    target_bin = local_bin / "click-to-do"
    candidates = (
        Path(sys.argv[0]).expanduser().absolute(),
        Path(sys.executable).parent / "click-to-do",
        Path.cwd() / ".venv" / "bin" / "click-to-do",
    )
    for candidate in candidates:
        if candidate.name.startswith("click-to-do") and candidate.exists():
            local_bin.mkdir(parents=True, exist_ok=True)
            if target_bin.exists() and not target_bin.is_symlink():
                raise FileExistsError(f"Refusing to replace an existing launcher: {target_bin}")
            if target_bin.exists() or target_bin.is_symlink():
                if target_bin.is_symlink() and target_bin.resolve() == candidate.resolve():
                    return str(target_bin)
                target_bin.unlink()
            target_bin.symlink_to(candidate)
            return str(target_bin)
    return str(target_bin)


def get_assets_dir() -> Path:
    """Icons shipped inside the package; fall back to the repository's assets/."""
    package_assets = Path(__file__).resolve().parent / "assets"
    return package_assets if package_assets.exists() else Path(__file__).resolve().parent.parent.parent / "assets"


def _systemd_unit(bin_path: str) -> str:
    executable = _systemd_arg(bin_path)
    return (
        "[Unit]\n"
        "Description=Click to Do workbench reminders and screen tools\n"
        "After=graphical-session.target\n"
        "PartOf=graphical-session.target\n\n"
        "[Service]\n"
        f"ExecStart={executable} daemon\n"
        "Restart=on-failure\n"
        "RestartSec=3\n\n"
        "[Install]\n"
        "WantedBy=graphical-session.target\n"
    )


def _remove_systemd_enablement(config_home: Path) -> None:
    wants_link = config_home / "systemd" / "user" / "graphical-session.target.wants" / "click-to-do.service"
    if wants_link.is_symlink():
        wants_link.unlink()
        try:
            wants_link.parent.rmdir()
        except OSError:
            pass


def _systemd_graphical_session_is_active() -> tuple[bool, str]:
    result = _systemctl("is-active", "graphical-session.target")
    if result is None:
        return False, "systemctl is unavailable"
    if result.returncode == 0 and result.stdout.strip() == "active":
        return True, ""
    reason = result.stderr.strip() or result.stdout.strip() or "graphical-session.target is not active"
    return False, reason


def _desktop_file(bin_path: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Click to Do\n"
        "GenericName=Office Productivity Assistant\n"
        "Comment=Personal workbench with focus timer, wellness reminders, notes, tasks, and screen tools\n"
        "Name[vi]=Click to Do — Bàn làm việc\n"
        "GenericName[vi]=Trợ lý công việc cá nhân\n"
        "Comment[vi]=Bàn làm việc cá nhân với Pomodoro, nhắc sức khỏe, ghi chú, danh sách việc và công cụ màn hình\n"
        f"Exec={_desktop_exec(bin_path, 'office')}\n"
        "Icon=click-to-do\n"
        "Terminal=false\n"
        "StartupWMClass=click-to-do-office\n"
        "Categories=Office;Utility;\n"
        "Actions=Capture;Color;Settings;\n\n"
        "[Desktop Action Capture]\n"
        "Name=Capture Screen\n"
        f"Exec={_desktop_exec(bin_path, 'capture')}\n\n"
        "[Desktop Action Color]\n"
        "Name=Pick Screen Color\n"
        f"Exec={_desktop_exec(bin_path, 'color')}\n\n"
        "[Desktop Action Settings]\n"
        "Name=Settings & Local Models\n"
        f"Exec={_desktop_exec(bin_path, 'settings')}\n"
    )


def _settings_desktop_file(bin_path: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Click to Do Settings\n"
        "GenericName=Settings & Local AI Model Manager\n"
        "Comment=Configure the workbench, screen overlay, and local AI models\n"
        f"Exec={_desktop_exec(bin_path, 'settings')}\n"
        "Icon=click-to-do\n"
        "Terminal=false\n"
        "StartupWMClass=click-to-do-settings\n"
        "Categories=Utility;Settings;\n"
    )


def _overlay_desktop_file(bin_path: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Click to Do Overlay\n"
        f"Exec={_desktop_exec(bin_path, 'capture')}\n"
        "Icon=click-to-do\n"
        "NoDisplay=true\n"
    )


def _autostart_desktop_file(bin_path: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Click to Do background service\n"
        "Comment=Keep Pomodoro and wellbeing reminders running in this desktop session\n"
        f"Exec={_desktop_exec(bin_path, 'daemon')}\n"
        "Terminal=false\n"
        "NoDisplay=true\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def _launch_daemon_in_current_session(bin_path: str, warnings: list[str]) -> bool:
    """Start now when install is run inside a Wayland session whose target is not active."""
    if not os.environ.get("WAYLAND_DISPLAY"):
        return False
    try:
        process = subprocess.Popen(
            [bin_path, "daemon"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        return process.poll() is None
    except OSError as exc:
        warnings.append(f"Could not launch the daemon in the current session: {exc}")
        return False


def _desktop_directory() -> Path | None:
    xdg_user_dir = shutil.which("xdg-user-dir")
    if xdg_user_dir:
        try:
            result = _run([xdg_user_dir, "DESKTOP"], timeout=3)
            directory = result.stdout.strip()
            candidate = Path(directory).expanduser() if directory else None
            if result.returncode == 0 and candidate and candidate.is_absolute() and candidate.is_dir():
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            pass
    fallback = Path.home() / "Desktop"
    return fallback if fallback.is_dir() else None


def _refresh_desktop_caches(data_home: Path, warnings: list[str]) -> None:
    icon_cache = shutil.which("gtk-update-icon-cache")
    if icon_cache:
        try:
            result = _run([icon_cache, "-f", "-t", str(data_home / "icons" / "hicolor")])
            if result.returncode:
                warnings.append("Could not refresh the GTK icon cache; the desktop may update it on its next refresh.")
        except (OSError, subprocess.TimeoutExpired):
            warnings.append("Could not refresh the GTK icon cache; the desktop may update it on its next refresh.")
    database = shutil.which("update-desktop-database")
    if database:
        try:
            result = _run([database, str(data_home / "applications")])
            if result.returncode:
                warnings.append("Could not refresh the desktop application database; the launcher files were still installed.")
        except (OSError, subprocess.TimeoutExpired):
            warnings.append("Could not refresh the desktop application database; the launcher files were still installed.")


_NIRI_RULE_START = "// >>> click-to-do overlay rule (managed) >>>"
_NIRI_RULE_END = "// <<< click-to-do overlay rule (managed) <<<"
_NIRI_OVERLAY_RULE = (
    'window-rule {\n'
    '    match app-id="^click-to-do-overlay$"\n'
    '    open-floating true\n'
    '    default-floating-position x=0 y=0 relative-to="top-left"\n'
    '    border { off; }\n'
    '    shadow { off; }\n'
    '    focus-ring { off; }\n'
    '}\n'
)


def _strip_niri_overlay_rule(content: str) -> str:
    managed = re.compile(
        rf"(?m)^{re.escape(_NIRI_RULE_START)}\n[\s\S]*?^{re.escape(_NIRI_RULE_END)}\n?"
    )
    content = managed.sub("", content)
    # Migrate the exact unmarked rule written by older installer versions.
    legacy = re.compile(
        r'(?m)^window-rule\s*\{\s*match\s+app-id="\^click-to-do-overlay\$"'
        r'[\s\S]*?^\}\s*\n?'
    )
    return legacy.sub("", content)


def _install_niri_overlay_rule(warnings: list[str]) -> bool:
    """Manage the overlay rule only in an active Niri session, never by file presence alone."""
    from . import compositor

    comp = compositor.detect()
    if comp.id != "niri" or not comp.config_path or not comp.config_path.is_file():
        return False

    config_path = comp.config_path
    original = config_path.read_text(encoding="utf-8")
    clean = _strip_niri_overlay_rule(original).rstrip()
    if clean:
        clean += "\n\n"
    updated = f"{clean}{_NIRI_RULE_START}\n{_NIRI_OVERLAY_RULE}{_NIRI_RULE_END}\n"
    if updated == original:
        return False

    backup = config_path.with_name(config_path.name + ".click-to-do.bak")
    shutil.copy2(config_path, backup)
    _write_text(config_path, updated)

    niri_socket = os.environ.get("NIRI_SOCKET")
    niri_command = shutil.which("niri")
    if niri_socket and niri_command:
        try:
            result = _run([niri_command, "msg", "action", "load-config-file"])
            if result.returncode:
                detail = result.stderr.strip() or result.stdout.strip() or "reload command failed"
                warnings.append(f"Niri rule was written but its live reload failed: {detail}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            warnings.append(f"Niri rule was written but could not be reloaded: {exc}")
    elif not niri_socket:
        warnings.append("Niri rule was written; NIRI_SOCKET was not available, so it takes effect on the next Niri config reload.")
    else:
        warnings.append("Niri rule was written; the `niri` command was unavailable for live reload.")
    return True


def _install_background_startup(bin_path: str, config_home: Path, warnings: list[str]) -> str:
    """Use systemd's graphical target where available and XDG autostart as a portable fallback."""
    service_dir = config_home / "systemd" / "user"
    service_file = service_dir / "click-to-do.service"
    autostart_file = config_home / "autostart" / "click-to-do.desktop"
    graphical_session_active, target_reason = _systemd_graphical_session_is_active()
    manager = _systemctl("show-environment")
    systemd_available = bool(manager and manager.returncode == 0)

    if systemd_available:
        service_dir.mkdir(parents=True, exist_ok=True)
        _write_text(service_file, _systemd_unit(bin_path))
        reload_result = _systemctl("daemon-reload")
        enable_result = _systemctl("enable", "click-to-do.service") if reload_result and reload_result.returncode == 0 else None
        if reload_result and reload_result.returncode == 0 and enable_result and enable_result.returncode == 0:
            if graphical_session_active:
                active_result = _systemctl("is-active", "click-to-do.service")
                was_active = bool(active_result and active_result.returncode == 0 and active_result.stdout.strip() == "active")
                start_result = _systemctl("restart" if was_active else "start", "click-to-do.service")
                verified = _systemctl("is-active", "click-to-do.service")
                if start_result and start_result.returncode == 0 and verified and verified.returncode == 0 and verified.stdout.strip() == "active":
                    if autostart_file.exists():
                        autostart_file.unlink()
                    return "systemd user service (graphical-session.target; enabled and active)"
                detail = "start command failed" if not start_result or start_result.returncode else "service did not remain active"
                if verified and (verified.stderr.strip() or verified.stdout.strip()):
                    detail = verified.stderr.strip() or verified.stdout.strip()
                warnings.append(f"systemd could not keep the daemon active ({detail}); using XDG autostart as a session fallback.")
                _systemctl("disable", "--now", "click-to-do.service")
                service_file.unlink(missing_ok=True)
                _remove_systemd_enablement(config_home)
                _systemctl("daemon-reload")
            else:
                warnings.append(
                    f"graphical-session.target is not active now ({target_reason}); the systemd unit is enabled for sessions that start it."
                )
                autostart_file.parent.mkdir(parents=True, exist_ok=True)
                _write_text(autostart_file, _autostart_desktop_file(bin_path))
                launched = _launch_daemon_in_current_session(bin_path, warnings)
                suffix = "; daemon launched for this session" if launched else ""
                return "systemd session unit enabled + XDG autostart fallback" + suffix
        else:
            details = []
            for label, result in (("daemon-reload", reload_result), ("enable", enable_result)):
                if result is None or result.returncode:
                    msg = (result.stderr.strip() or result.stdout.strip()) if result else "not run"
                    details.append(f"{label}: {msg or 'failed'}")
            warnings.append("systemd setup failed (" + "; ".join(details) + "); using XDG autostart instead.")
            _systemctl("disable", "--now", "click-to-do.service")
            service_file.unlink(missing_ok=True)
            _remove_systemd_enablement(config_home)
            _systemctl("daemon-reload")
    else:
        detail = manager.stderr.strip() if manager else "systemctl is unavailable"
        warnings.append(f"No usable systemd user manager ({detail or 'not available'}); using XDG autostart.")
        if service_file.exists():
            service_file.unlink()
        _remove_systemd_enablement(config_home)

    autostart_file.parent.mkdir(parents=True, exist_ok=True)
    _write_text(autostart_file, _autostart_desktop_file(bin_path))
    launched = _launch_daemon_in_current_session(bin_path, warnings)
    suffix = "; daemon launched for this session" if launched else ""
    return "XDG autostart desktop entry (starts on graphical login)" + suffix


def install_system_integration() -> tuple[bool, str]:
    """Install standard XDG launchers and select a session-compatible daemon startup method."""
    warnings: list[str] = []
    try:
        bin_path = get_executable_path()
        data_home = _xdg_data_home()
        config_home = _xdg_config_home()
        assets_dir = get_assets_dir()

        # hicolor icons are consumed by GTK, Qt and desktop launchers across environments.
        hicolor_dir = data_home / "icons" / "hicolor"
        scalable_dir = hicolor_dir / "scalable" / "apps"
        scalable_dir.mkdir(parents=True, exist_ok=True)
        project_svg = assets_dir / "icon.svg"
        if project_svg.exists():
            shutil.copy2(project_svg, scalable_dir / "click-to-do.svg")
        else:
            _write_text(scalable_dir / "click-to-do.svg", get_svg_xml("app_logo", "#38bdf8", 64))

        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            size_dir = hicolor_dir / f"{size}x{size}" / "apps"
            size_dir.mkdir(parents=True, exist_ok=True)
            source = assets_dir / f"icon-{size}.png"
            if not source.exists():
                source = assets_dir / "icon.png"
            if source.exists():
                shutil.copy2(source, size_dir / "click-to-do.png")

        pixmaps_dir = data_home / "pixmaps"
        pixmaps_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("icon.png", "icon.svg"):
            source = assets_dir / filename
            if source.exists():
                shutil.copy2(source, pixmaps_dir / f"click-to-do.{filename.rsplit('.', 1)[-1]}")
                shutil.copy2(source, data_home / "icons" / f"click-to-do.{filename.rsplit('.', 1)[-1]}")

        apps_dir = data_home / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        app_desktop = apps_dir / "click-to-do.desktop"
        settings_desktop = apps_dir / "click-to-do-settings.desktop"
        overlay_desktop = apps_dir / "click-to-do-overlay.desktop"
        _write_text(app_desktop, _desktop_file(bin_path))
        _write_text(settings_desktop, _settings_desktop_file(bin_path))
        _write_text(overlay_desktop, _overlay_desktop_file(bin_path))

        desktop_dir = _desktop_directory()
        if desktop_dir:
            for entry in (app_desktop, settings_desktop):
                destination = desktop_dir / entry.name
                try:
                    shutil.copy2(entry, destination)
                    destination.chmod(destination.stat().st_mode | 0o111)
                except OSError as exc:
                    warnings.append(f"Could not create the optional desktop shortcut {destination}: {exc}")

        startup_mode = _install_background_startup(bin_path, config_home, warnings)
        try:
            niri_rule_installed = _install_niri_overlay_rule(warnings)
        except OSError as exc:
            niri_rule_installed = False
            warnings.append(f"Could not update the Niri overlay rule: {exc}")
        _refresh_desktop_caches(data_home, warnings)

        lines = [
            "Installed successfully.",
            f"• Launcher: {app_desktop}",
            f"• Settings: {settings_desktop}",
            f"• Background startup: {startup_mode}",
            "• Bar icon: requested through Qt StatusNotifierItem; visibility depends on the active shell/bar. Custom bars can use `click-to-do bar-status`.",
        ]
        if niri_rule_installed:
            lines.append("• Niri overlay rule: installed for the currently detected Niri session.")
        if warnings:
            lines.append("Warnings:")
            lines.extend(f"• {warning}" for warning in warnings)
        return True, "\n".join(lines)
    except Exception as exc:
        return False, f"Installation error: {exc}"


def _remove_niri_overlay_rule(path: Path) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8")
    updated = _strip_niri_overlay_rule(content).rstrip()
    updated = f"{updated}\n" if updated else ""
    if updated == content:
        return False
    _write_text(path, updated)
    return True


def uninstall_system_integration(purge_data: bool = False) -> tuple[bool, str]:
    """Remove Click to Do's XDG/systemd integration while retaining personal data by default."""
    removed: list[str] = []
    warnings: list[str] = []
    home = Path.home()
    data_home = _xdg_data_home()
    config_home = _xdg_config_home()
    bin_path = shutil.which("click-to-do") or str(home / ".local" / "bin" / "click-to-do")
    try:
        stop_result = _systemctl("disable", "--now", "click-to-do.service")
        if stop_result and stop_result.returncode and "not loaded" not in stop_result.stderr.lower():
            warnings.append("Could not stop the systemd user service; it may still be running until the session ends.")
        try:
            result = _run([bin_path, "stop"], timeout=3)
            if result.returncode:
                warnings.append("Could not send the stop command to a manually started daemon.")
        except (OSError, subprocess.TimeoutExpired):
            warnings.append("Could not send the stop command to a manually started daemon.")

        desktop_dir = _desktop_directory()
        targets = [
            config_home / "systemd" / "user" / "click-to-do.service",
            config_home / "systemd" / "user" / "graphical-session.target.wants" / "click-to-do.service",
            config_home / "autostart" / "click-to-do.desktop",
            data_home / "applications" / "click-to-do.desktop",
            data_home / "applications" / "click-to-do-settings.desktop",
            data_home / "applications" / "click-to-do-overlay.desktop",
            data_home / "pixmaps" / "click-to-do.png",
            data_home / "pixmaps" / "click-to-do.svg",
            data_home / "icons" / "click-to-do.png",
            data_home / "icons" / "click-to-do.svg",
            data_home / "icons" / "hicolor" / "scalable" / "apps" / "click-to-do.svg",
        ]
        if desktop_dir:
            targets.extend((desktop_dir / "click-to-do.desktop", desktop_dir / "click-to-do-settings.desktop"))
        for size in (16, 24, 32, 48, 64, 128, 256, 512):
            targets.append(data_home / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "click-to-do.png")

        bin_link = home / ".local" / "bin" / "click-to-do"
        # Keep launchers managed by uv/pipx; remove only a checkout link made by this installer.
        if bin_link.is_symlink() and "/uv/tools/" not in str(bin_link.resolve()) and "/pipx/" not in str(bin_link.resolve()):
            targets.append(bin_link)

        for path in targets:
            if path.exists() or path.is_symlink():
                path.unlink()
                removed.append(str(path))

        systemd_reload = _systemctl("daemon-reload")
        if systemd_reload and systemd_reload.returncode:
            warnings.append("Could not reload the systemd user manager after removing the service file.")

        try:
            from . import compositor

            compositor_configs = (
                ("niri", "Niri", config_home / "niri" / "config.kdl"),
                ("umbriel", "Umbriel", config_home / "umbriel" / "config.toml"),
                ("hyprland", "Hyprland", config_home / "hypr" / "hyprland.conf"),
                ("sway", "Sway", config_home / "sway" / "config"),
                ("river", "River", config_home / "river" / "init"),
            )
            for compositor_id, name, path in compositor_configs:
                if not path.exists():
                    continue
                try:
                    removed.extend(compositor.remove(compositor.Compositor(compositor_id, name, path, True)))
                except Exception as exc:
                    warnings.append(f"Could not remove {name} shortcuts: {exc}")
        except Exception as exc:
            warnings.append(f"Could not load compositor integration: {exc}")

        niri_config = config_home / "niri" / "config.kdl"
        if _remove_niri_overlay_rule(niri_config):
            removed.append(f"{niri_config} (Click to Do overlay rule)")
            niri_command = shutil.which("niri")
            if os.environ.get("NIRI_SOCKET") and niri_command:
                result = _run([niri_command, "msg", "action", "load-config-file"])
                if result.returncode:
                    warnings.append("Removed the Niri rule from disk; live reload failed and will apply on the next config reload.")
            else:
                warnings.append("Removed the Niri rule from disk; reload Niri's config to apply it in the current session.")

        _refresh_desktop_caches(data_home, warnings)

        if purge_data:
            data_dirs = {
                home / ".config" / "click-to-do",
                config_home / "click-to-do",
                home / ".local" / "share" / "click-to-do",
                data_home / "click-to-do",
            }
            for directory in data_dirs:
                if directory.exists():
                    shutil.rmtree(directory, ignore_errors=True)
                    removed.append(str(directory))

        note = "" if purge_data else " Personal configuration and downloaded data were kept."
        warning_text = "\nWarnings:\n" + "\n".join(f"• {warning}" for warning in warnings) if warnings else ""
        return True, f"Uninstalled. Removed {len(removed)} item(s).{note}{warning_text}"
    except Exception as exc:
        return False, f"Uninstall error: {exc}"
