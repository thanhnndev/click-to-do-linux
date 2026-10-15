# Contributing

Thanks for helping. Bug reports, compatibility reports and patches are welcome.

## Before you start

- Check [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md). The project is tested
  on one machine only, so "it works on my distro / compositor" reports are
  especially valuable.
- Open an issue first for larger changes so the direction can be agreed.

## Development setup

```bash
git clone https://github.com/thanhnndev/click-to-do-linux.git
cd click-to-do-linux
uv sync
uv run click-to-do settings      # GUI
uv run click-to-do daemon        # resident daemon
```

Requires a Wayland session with `grim` and `wl-clipboard`; `tesseract` with
Vietnamese data is needed for diacritic-accurate OCR.

## Code layout

| Path | What |
| :--- | :--- |
| `src/click_to_do_linux/capture/` | screen capture |
| `src/click_to_do_linux/ai/` | OCR, cutout, LLM, optional NPU detection |
| `src/click_to_do_linux/ui/` | overlay and settings windows (PyQt6) |
| `src/click_to_do_linux/compositor.py` | compositor detection and shortcut writers |
| `src/click_to_do_linux/i18n.py` | all UI strings (vi / en) |
| `scripts/` | screenshots/GIF generator, LLM benchmark |
| `packaging/` | AUR PKGBUILD |

## Guidelines

- Keep code in the style of the surrounding code; add UI strings to `i18n.py`
  in both languages.
- Do not claim performance numbers you have not measured. Put measurements in
  docs with the machine and conditions, as in [docs/NPU.md](docs/NPU.md).
- Do not add emoji to docs or UI strings.
- Never edit a user's compositor config beyond a single include line, and
  always make a backup first.
- Screenshots must come from `scripts/make_screenshots.py` (synthetic desktop)
  so no private content is published.

## Pull requests

1. Fork and create a branch from `master`.
2. Make a focused change; update docs if behavior changes.
3. Test it on your setup and say which distro and compositor you used.
4. Open a pull request describing the change and how you tested it.

By contributing you agree that your work is licensed under GPL-3.0-or-later.
