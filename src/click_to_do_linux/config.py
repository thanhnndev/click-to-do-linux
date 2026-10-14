"""Configuration manager for Click to Do Linux."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class Config:
    # Hardware & AI Provider: 'auto', 'npu', 'gpu', 'cpu'
    ai_provider: str = "auto"
    
    # Preferred OCR engine
    ocr_engine: str = "rapidocr"
    
    # Background removal model: 'u2net', 'isnet-general-use', 'bria-rmbg'
    bg_removal_model: str = "isnet-general-use"
    
    # Local LLM settings
    ollama_enabled: bool = True
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:latest"
    
    # Target translation language: 'vi', 'en', 'fr', 'ja', 'zh', etc.
    target_language: str = "vi"
    
    # Search engine: 'google', 'duckduckgo', 'bing', 'kagi'
    search_engine: str = "google"
    
    # Visual Search: 'google_lens', 'bing'
    visual_search: str = "google_lens"
    
    # UI settings
    theme: str = "dark_glass"
    high_dpi_scaling: bool = True
    auto_detect_qr: bool = True
    auto_ocr_on_trigger: bool = True
    
    # Directory to save crops / images
    save_directory: str = str(Path.home() / "Pictures" / "ClickToDo")


def get_config_path() -> Path:
    config_dir = Path.home() / ".config" / "click-to-do"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_config() -> Config:
    path = get_config_path()
    if not path.exists():
        cfg = Config()
        save_config(cfg)
        return cfg
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Config(**{k: v for k, v in data.items() if k in Config.__annotations__})
    except Exception as e:
        print(f"[Config] Error loading {path}: {e}, using default config")
        return Config()


def save_config(config: Config) -> None:
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Config] Failed to save config to {path}: {e}")
