# Installation

## One-command install (Arch, Debian/Ubuntu, Fedora, openSUSE)

```bash
git clone https://github.com/thanhnndev/click-to-do-linux.git
cd click-to-do-linux
./install.sh                  # system deps + app + launcher + systemd service
./install.sh --with-ollama    # ...and the Ollama runtime
./install.sh --no-deps --yes  # skip system packages, no prompts
```

`install.sh` detects the distro and installs `grim`, `wl-clipboard`, `tesseract`
(+ Vietnamese data) with the native package manager, installs the app with
[`uv tool install`](https://docs.astral.sh/uv/guides/tools/) on Python 3.12, then
runs `click-to-do install` to set up:

1. `~/.local/bin/click-to-do` launcher (managed by uv).
2. Desktop launcher (`~/.local/share/applications/click-to-do.desktop`) and icons.
3. A systemd user service (`click-to-do.service`) so the daemon and bar icon start with the session.
4. The non-scrolling floating window rule in `~/.config/niri/config.kdl` (if Niri is present).

| Distro family | Packages installed |
| :--- | :--- |
| Arch / CachyOS / Manjaro | `grim wl-clipboard tesseract tesseract-data-vie tesseract-data-eng uv` |
| Debian / Ubuntu | `grim wl-clipboard tesseract-ocr tesseract-ocr-vie` + Qt runtime libs |
| Fedora / Nobara | `grim wl-clipboard tesseract tesseract-langpack-vie` + Qt runtime libs |
| openSUSE | `grim wl-clipboard tesseract-ocr tesseract-ocr-traineddata-vietnamese` |

Only the Arch/CachyOS path has been run on real hardware; see
[COMPATIBILITY.md](COMPATIBILITY.md).

## Arch Linux: AUR / PKGBUILD

```bash
# from the AUR (once published)
yay -S click-to-do-linux-git        # or paru

# or build the PKGBUILD in this repo
cd packaging/arch && makepkg -si
```

The package depends on `python-pyqt6`, `python-opencv`, `python-onnxruntime`,
`grim`, `wl-clipboard`, `tesseract` (+ `vie`/`eng` data) and the AUR packages
`python-rapidocr` and `python-rembg`. Then:

```bash
systemctl --user enable --now click-to-do.service
click-to-do settings          # Shortcuts tab binds a key for your compositor
```

## Developer setup

```bash
uv sync
uv run click-to-do install
```

## Configure models (GUI)

```bash
click-to-do settings
```

Pick the cutout engine and the Ollama model, then click **Download & Warmup
Models**. The UI language (Vietnamese / English / auto) is in the same window.

## Uninstall

From the GUI: **Settings > Uninstall...** (optionally also delete config and
downloaded data).

From the terminal:

```bash
./install.sh --uninstall         # same as the two lines below + `uv tool uninstall`
click-to-do uninstall            # remove service, launchers, icons, Niri rule
click-to-do uninstall --purge    # ...and delete ~/.config/click-to-do + downloaded Tesseract data
```

Models pulled with Ollama are left untouched; remove them with `ollama rm <model>`.
