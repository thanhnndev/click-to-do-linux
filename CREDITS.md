# Credits & Third-Party Licenses

**Click to Do for Linux** is an independent open-source project and is **not affiliated with, endorsed by, or sponsored by Microsoft**. "Click to Do" is a feature name of Windows 11; this project is an unofficial Linux re-implementation of the interaction concept.

Copyright © 2026 thanhnndev. Licensed under the [GNU GPL v3.0 or later](LICENSE).

## Libraries

| Component | Used for | License |
| :--- | :--- | :--- |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) | Text-line detection (ONNX Runtime) | Apache-2.0 |
| [PaddleOCR / PP-OCR](https://github.com/PaddlePaddle/PaddleOCR) | Detection models behind RapidOCR | Apache-2.0 |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) + [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) | Vietnamese / English text recognition | Apache-2.0 |
| [rembg](https://github.com/danielgatis/rembg) | Subject cutout runtime | MIT |
| [U²-Net / u2netp](https://github.com/xuebinqin/U-2-Net) | Fast cutout model | Apache-2.0 |
| [IS-Net / DIS](https://github.com/xuebinqin/DIS) | High-precision cutout model | Apache-2.0 |
| [Ollama](https://github.com/ollama/ollama) | Local LLM runtime (separate install) | MIT |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GUI toolkit | GPL v3 (reason this project is GPL) |
| [OpenCV](https://github.com/opencv/opencv-python) | Image processing | Apache-2.0 |
| [Pillow](https://github.com/python-pillow/Pillow) | Imaging | MIT-CMU (HPND) |
| [NumPy](https://numpy.org/) | Arrays | BSD-3-Clause |
| [Requests](https://github.com/psf/requests) | HTTP client | Apache-2.0 |
| [grim](https://sr.ht/~emersion/grim/) | Wayland screenshots (external tool) | MIT |

## Language models (not bundled — pulled by the user via Ollama)

| Model | Author | License |
| :--- | :--- | :--- |
| Qwen2.5 / Qwen3 | Alibaba Cloud | Apache-2.0 (Qwen2.5 3B uses the Qwen Research License) |
| Gemma 3 | Google DeepMind | [Gemma Terms of Use](https://ai.google.dev/gemma/terms) |
| Sailor2 | Sea AI Lab / SAIL community | Apache-2.0 |
| Aya Expanse | Cohere For AI | CC-BY-NC 4.0 (non-commercial) |
| Llama 3.2 | Meta | Llama 3.2 Community License |

Model licenses are summarized for convenience; always check the model card of the exact tag you download.
