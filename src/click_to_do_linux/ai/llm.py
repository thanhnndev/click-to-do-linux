"""LLM integration for Translate, Summarize, Explain, Rewrite and Custom Prompt.

Two backends: Ollama (native API) and any OpenAI-compatible server (e.g. FastFlowLM, which runs on the NPU).
"""

import json
from typing import Generator, List, Optional
import requests


class LLMService:
    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "qwen2.5:3b",
        backend: str = "ollama",
        keep_alive: str = "2m",
    ):
        self.host = host.rstrip("/")
        self.model = model
        self.backend = backend
        self.keep_alive = keep_alive

    @classmethod
    def from_config(cls, cfg) -> "LLMService":
        if cfg.llm_backend == "openai":
            return cls(host=cfg.openai_base_url, model=cfg.openai_model, backend="openai")
        return cls(host=cfg.ollama_host, model=cfg.ollama_model, backend="ollama", keep_alive=cfg.llm_keep_alive)

    def is_available(self) -> bool:
        try:
            path = "/models" if self.backend == "openai" else "/api/version"
            r = requests.get(f"{self.host}{path}", timeout=1.2)
            return r.status_code == 200
        except Exception:
            return False

    def get_models(self) -> List[str]:
        try:
            if self.backend == "openai":
                r = requests.get(f"{self.host}/models", timeout=1.5)
                if r.status_code == 200:
                    return [m["id"] for m in r.json().get("data", [])]
                return []
            r = requests.get(f"{self.host}/api/tags", timeout=1.5)
            if r.status_code == 200:
                data = r.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []

    def _generate_openai(self, prompt: str, system: Optional[str] = None) -> Generator[str, None, None]:
        # Qwen3 soft switch: skip the hidden <think> phase (OpenAI API has no `think` field)
        if self.model.lower().startswith("qwen3") and "-tk" not in self.model.lower():
            prompt = f"{prompt}\n/no_think"
        messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        payload = {"model": self.model, "messages": messages, "stream": True, "temperature": 0.3}
        try:
            with requests.post(f"{self.host}/chat/completions", json=payload, stream=True, timeout=60) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line or not line.startswith(b"data:"):
                        continue
                    data = line[5:].strip()
                    if data == b"[DONE]":
                        break
                    choices = json.loads(data).get("choices") or [{}]
                    text = (choices[0].get("delta") or {}).get("content") or ""
                    if text:
                        yield text
        except Exception as e:
            yield f"\n[Error: {e}]"

    def _generate_stream(self, prompt: str, system: Optional[str] = None) -> Generator[str, None, None]:
        if self.backend == "openai":
            yield from self._generate_openai(prompt, system)
            return
        url = f"{self.host}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": True, "keep_alive": self._keep_alive_value()}
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

    def _keep_alive_value(self):
        v = str(self.keep_alive).strip()
        return int(v) if v.lstrip("-").isdigit() else v

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
