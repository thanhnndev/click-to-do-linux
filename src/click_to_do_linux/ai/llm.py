"""LLM Integration module using Ollama for Translate, Summarize, Explain, Rewrite, and Custom Prompt."""

import json
from typing import Generator, List, Optional
import requests


class LLMService:
    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2.5:3b"):
        self.host = host.rstrip("/")
        self.model = model

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.host}/api/version", timeout=1.2)
            return r.status_code == 200
        except Exception:
            return False

    def get_models(self) -> List[str]:
        try:
            r = requests.get(f"{self.host}/api/tags", timeout=1.5)
            if r.status_code == 200:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def _generate_stream(self, prompt: str, system: Optional[str] = None) -> Generator[str, None, None]:
        url = f"{self.host}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": True, "keep_alive": "10m"}
        # Qwen3 / reasoning models: skip the hidden <think> phase for instant, clean output
        if self.model.lower().startswith(("qwen3", "deepseek-r1")):
            payload["think"] = False
        payload["options"] = {"temperature": 0.3}
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

    @staticmethod
    def _lang_name(lang: str) -> str:
        return "Vietnamese (Tiếng Việt, with full and correct diacritics)" if lang == "vi" else "English"

    def summarize(self, text: str, lang: str = "vi") -> Generator[str, None, None]:
        lang_name = self._lang_name(lang)
        system = f"Provide a direct, concise bullet-point summary in {lang_name}. No intro fluff."
        return self._generate_stream(f"Summarize:\n\n{text}", system=system)

    def explain(self, text: str, lang: str = "vi") -> Generator[str, None, None]:
        lang_name = self._lang_name(lang)
        system = f"Explain the following text, terminal command, or code clearly and concisely in {lang_name}."
        return self._generate_stream(f"Explain:\n\n{text}", system=system)

    def translate(self, text: str, target_lang: str = "vi") -> Generator[str, None, None]:
        target_name = self._lang_name(target_lang)
        system = (
            f"You are a professional translator. Translate the text into {target_name}. "
            "The text comes from OCR of a screenshot, so silently fix obvious recognition glitches. "
            "Keep names, code, URLs and numbers unchanged. If the text is already in the target language, "
            "translate it into English instead. Output ONLY the translation."
        )
        return self._generate_stream(text, system=system)

    def rewrite(self, text: str) -> Generator[str, None, None]:
        system = (
            "Improve clarity, grammar, spelling (including diacritics) and tone while preserving the original "
            "language and meaning. Output ONLY the improved text."
        )
        return self._generate_stream(text, system=system)

    def custom_ask(self, context_text: str, question: str, lang: str = "vi") -> Generator[str, None, None]:
        lang_name = self._lang_name(lang)
        system = f"Answer the user's question about the provided screen text directly in {lang_name}."
        prompt = f"Context from screen:\n{context_text}\n\nQuestion: {question}"
        return self._generate_stream(prompt, system=system)
