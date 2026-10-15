# Models

## OCR (Vietnamese)

Stock PP-OCR models (RapidOCR/PaddleOCR) silently drop Vietnamese tone marks
(`Viet Nam` with diacritics becomes `Vit Nam`). Click to Do therefore uses a hybrid pipeline:

1. RapidOCR (ONNX) locates every text line; it is fast and language-agnostic.
2. Tesseract `vie+eng` reads each line, keeping the full diacritics.

If `tesseract` is not installed the app falls back to RapidOCR (English and
Chinese are fine, Vietnamese loses diacritics).

```bash
# Arch / CachyOS            sudo pacman -S tesseract
# Debian / Ubuntu           sudo apt install tesseract-ocr
# Fedora                    sudo dnf install tesseract
```

The compact Vietnamese/English data files (about 4.6 MB, `tessdata_fast`) are
downloaded to `~/.local/share/click-to-do/tessdata` by **Settings > Download &
Warmup Models**; no system language packs are required.

Text-line detection can optionally run on an AMD XDNA2 NPU, see [NPU.md](NPU.md).

## Local language models (Ollama)

Sizes are Ollama default downloads (q4_K_M). The Vietnamese column is a
qualitative rating (1-5) from published benchmarks and model cards we could
find (VMLU, translation roundups); no single benchmark covers all of these, so
test on your own text.

| Model (`ollama pull ...`) | Size | VRAM/RAM | Vietnamese (1-5) | Best for | License |
| :--- | ---: | ---: | :---: | :--- | :--- |
| `qwen3:1.7b` | 1.4 GB | ~2 GB | 2 | Old laptops, CPU-only, fastest replies | Apache-2.0 |
| `sailor2:1b` | 1.1 GB | ~2 GB | 3 | Tiny model tuned for SE-Asian languages | Apache-2.0 |
| `qwen2.5:3b` | 1.9 GB | ~3 GB | 3 | Fast streaming, solid everyday default | Qwen Research |
| `qwen3:4b` (recommended) | 2.5 GB | ~4 GB | 4 | Best balance: translate / summarize / explain | Apache-2.0 |
| `gemma3:4b` | 3.4 GB | ~5 GB | 4 | Natural phrasing, 128K context | Gemma Terms |
| `qwen3:8b` | 5.2 GB | ~7 GB | 5 | High accuracy, 8 GB GPUs | Apache-2.0 |
| `sailor2:8b` | 5.2 GB | ~7 GB | 5 | Strongest Vietnamese up to 8B | Apache-2.0 |
| `aya-expanse:8b` | 5.1 GB | ~7 GB | 4 | 23-language translation (non-commercial) | CC-BY-NC |
| `gemma3:12b` | 8.2 GB | ~10 GB | 5 | Best quality on 12 GB GPUs | Gemma Terms |

Qwen3 models have a "thinking" mode; Click to Do disables it (`think: false`)
so output streams immediately.

## Cutout models (ONNX, via `rembg`)

| Model | Size | Notes |
| :--- | ---: | :--- |
| `u2netp` | 4.7 MB | Smallest and fastest; rougher edges |
| `isnet-general-use` | 170 MB | High-precision edges |
