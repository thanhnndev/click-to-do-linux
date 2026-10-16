# Installation

## One-command install (Arch, Debian/Ubuntu, Fedora, openSUSE)

```bash
git clone https://github.com/thanhnndev/click-to-do-linux.git
cd click-to-do-linux
./install.sh                  # system deps + app + desktop launcher + session startup
./install.sh --with-ollama    # ...and the Ollama runtime
./install.sh --no-deps --yes  # skip system packages, no prompts
```

`install.sh` detects the distro and installs `grim`, `wl-clipboard`, `tesseract`
(+ Vietnamese data) with the native package manager, installs the app with
[`uv tool install`](https://docs.astral.sh/uv/guides/tools/) on Python 3.12, then
runs `click-to-do install` to set up:

1. The `click-to-do` launcher (managed by uv).
2. XDG application launchers and hicolor icons under `$XDG_DATA_HOME` (default: `~/.local/share`).
3. Background startup matched to the current session: a systemd user service tied to
   `graphical-session.target` when the user manager is available. If that target is
   inactive during installation, an XDG autostart entry is also added as a fallback;
   if systemd cannot be used, XDG autostart is used on its own. The installer verifies
   systemd before reporting the service active, and the daemon safely ignores a second
   launch if both session mechanisms start it.
4. The non-scrolling overlay rule only when Niri is the currently detected compositor
   and its config file already exists. The rule is backed up before it is changed;
   if `NIRI_SOCKET` is unavailable, it is applied on the next config reload.

The tray icon is a Qt StatusNotifierItem. Its visibility depends on the shell or bar
providing an SNI host; custom bars can use `click-to-do bar-status`. The installer
does not assume that a tray host exists in every desktop environment.
For a standalone session that starts neither `graphical-session.target` nor XDG
autostart applications, add `click-to-do daemon` to that compositor's native startup.

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
click-to-do uninstall            # remove startup entry, launchers, icons, Niri rule
click-to-do uninstall --purge    # ...and delete ~/.config/click-to-do + downloaded Tesseract data
```

Models pulled with Ollama are left untouched; remove them with `ollama rm <model>`.
