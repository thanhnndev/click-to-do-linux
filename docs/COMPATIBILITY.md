# Supported and tested configurations

Important: this project has so far been run and tested on one machine only
(the author's). Everything not marked "tested" below is implemented from the
documented behavior of that compositor or distro and has not been verified on
real hardware. Reports (working or broken) are welcome as issues.

## Tested

| Item | Value |
| :--- | :--- |
| Distro | CachyOS (Arch Linux), kernel 7.2.10 |
| Compositor / shell | Niri with Dank Material Shell, and Umbriel |
| Session | Wayland |
| Laptop | AMD Ryzen AI 9 HX 370 (Radeon 890M), NVIDIA RTX 5060 Laptop GPU, XDNA2 NPU |
| Python | 3.12 (uv) |
| LLM backends | Ollama (dGPU); FastFlowLM 1.0.8 on the NPU |
| NPU text detection | Ryzen AI Software 1.8 (Linux), fixed-shape PP-OCRv6 detection |

## Multi-monitor capture

Capture asks the compositor for its focused output on Umbriel, Niri, Hyprland,
Sway, and Wayfire, then passes that output to `grim`. Other compositors do not
share a standard Wayland API for focused-output queries, so capture falls back
to the Qt screen under the pointer, then the primary screen. It always limits
`grim` to one output or one screen geometry; if a multi-output screen cannot be
identified, capture stops instead of combining the desktop.

## Implemented, not tested on real hardware

| Area | Items |
| :--- | :--- |
| Compositors (shortcut apply) | Hyprland, Sway, River |
| Compositors (guide only) | labwc, Wayfire, KDE Plasma, GNOME, COSMIC |
| Bars / shells (tray icon) | Waybar, Quickshell, Hyprpanel, KDE panel |
| Distros (install.sh) | Debian/Ubuntu, Fedora/Nobara, openSUSE, Manjaro |
| Packaging | AUR PKGBUILD (built locally with makepkg; not published to the AUR yet) |

## Not supported

- X11 sessions (capture uses `grim`, which is Wayland only).
- Non-AMD NPUs for the NPU options.
- Windows and macOS.

## How to report a result

Open an issue with: distro and version, compositor and shell, output of
`click-to-do settings` > System tab (diagnostics), and what worked or failed.
