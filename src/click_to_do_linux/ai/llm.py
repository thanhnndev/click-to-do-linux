"""LLM Integration module using Ollama for Summarize, Explain, Translate, and Rewrite."""

import json
from typing import Generator, List, Optional
import requests


class LLMService:
    """Interacts with local Ollama or OpenAI-compatible server for intelligent text tasks."""

    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2.5:latest"):
        self.host = host.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/version", timeout=1.5)
            return r.status_code == 200
        except Exception:
            return False

    def get_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=2.0)
            if r.status_code == 200:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def _generate_stream(self, prompt: str, system: Optional[str] = None) -> Generator[str, None, None]:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }
        if system:
            payload["system"] = system

        try:
            with requests.post(url, json=payload, stream=True, timeout=30) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    text = chunk.get("response", "")
                    if text:
                        yield text
                    if chunk.get("done", False):
                        break
        except Exception as e:
            yield f"\n[Error: {e}]"

    def summarize(self, text: str, lang: str = "vi") -> Generator[str, None, None]:
        lang_name = "tiếng Việt" if lang == "vi" else "English"
        system = f"You are a helpful assistant. Provide a clear, concise summary in {lang_name}."
        prompt = f"Summarize the following content concisely:\n\n{text}"
        return self._generate_stream(prompt, system=system)

    def explain(self, text: str, lang: str = "vi") -> Generator[str, None, None]:
        lang_name = "tiếng Việt" if lang == "vi" else "English"
        system = f"You are an expert tutor. Explain the following text or code snippet clearly in simple terms in {lang_name}."
        prompt = f"Explain this:\n\n{text}"
        return self._generate_stream(prompt, system=system)

    def translate(self, text: str, target_lang: str = "vi") -> Generator[str, None, None]:
        target_name = "tiếng Việt" if target_lang == "vi" else ("English" if target_lang == "en" else target_lang)
        system = f"You are a professional translator. Translate the given text accurately and naturally into {target_name}. Output ONLY the translated text without commentary."
        prompt = f"Translate the following text:\n\n{text}"
        return self._generate_stream(prompt, system=system)

    def rewrite(self, text: str) -> Generator[str, None, None]:
        system = "You are a professional editor. Improve the grammar, clarity, and tone of the given text while keeping its original meaning."
        prompt = f"Rewrite and polish the following text:\n\n{text}"
        return self._generate_stream(prompt, system=system)
