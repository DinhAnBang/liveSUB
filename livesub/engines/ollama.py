"""Translate through an Ollama model bound to local loopback."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from livesub.engines import StatusCallback

LANGUAGE_NAMES = {"ja": "Japanese", "en": "English", "vi": "Vietnamese"}


class OllamaTranslator:
    def __init__(self, model_name: str = "qwen3:4b") -> None:
        if model_name.lower().endswith(":cloud"):
            raise ValueError("Chỉ dùng model Ollama cục bộ; model ':cloud' không được hỗ trợ.")
        self.model_name = model_name

    def translate(
        self, text: str, source: str, target: str,
        terms: tuple[str, ...], status: StatusCallback,
    ) -> str:
        if source == target:
            return text
        system = (
            f"Translate conversational {LANGUAGE_NAMES.get(source, source)} into "
            f"{LANGUAGE_NAMES.get(target, target)}. Return only the translation. "
            "Preserve names, numbers, and capitalization."
        )
        if terms:
            system += f" Keep these terms exactly as written: {', '.join(terms)}."
        request = Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps({
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": text},
                ],
                "stream": False,
                "think": False,
                "options": {"temperature": 0},
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=90) as response:
                result = json.load(response)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama báo lỗi: {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(
                "Không kết nối được Ollama trên máy. Hãy mở Ollama và tải model bằng "
                f"lệnh: ollama pull {self.model_name}"
            ) from exc
        translated = (result.get("message") or {}).get("content", "").strip()
        if not translated:
            raise RuntimeError("Ollama trả về bản dịch rỗng.")
        return translated
