"""Configuration manager for Click to Do Linux."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Config:
    setup_completed: bool = False
    # Background removal model: 'u2netp' (fast ~4MB) or 'isnet-general-use' (accurate ~170MB)
    bg_removal_model: str = "u2netp"
    # Local LLM settings
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    # LLM backend: "ollama" (GPU/CPU) or "openai" (any OpenAI-compatible server, e.g. FastFlowLM on the NPU)
    llm_backend: str = "ollama"
    openai_base_url: str = "http://127.0.0.1:52625/v1"
    openai_model: str = "qwen3:4b"
    # How long Ollama keeps the model resident after a request ("0" = unload immediately, "-1" = forever)
    llm_keep_alive: str = "2m"
    # Text-line detection: "cpu" or "npu" (AMD XDNA2 via a Ryzen AI Software install, see docs/NPU.md)
    ocr_det_backend: str = "cpu"
    ryzenai_dir: str = str(Path.home() / "ryzenai")
    target_language: str = "vi"
    # UI language: "auto" (follow system locale), "vi" or "en"
    ui_language: str = "auto"
    # App workbench theme: "dark" or "light"
    ui_theme: str = "dark"
    search_engine: str = "google"
    auto_detect_qr: bool = True
    save_directory: str = str(Path.home() / "Pictures" / "ClickToDo")


def get_config_dir() -> Path:
    d = Path.home() / ".config" / "click-to-do"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


def load_config() -> Config:
    path = get_config_path()
    if not path.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        valid = {k: v for k, v in data.items() if k in Config.__annotations__}
        return Config(**valid)
    except Exception as e:
        print(f"[Config] Load error: {e}")
        return Config()


def save_config(config: Config) -> None:
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Config] Save error: {e}")
