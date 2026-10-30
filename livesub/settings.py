"""Validated session settings and paths shared by the application."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Mapping

APP_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = APP_DIR / "models"
SETTINGS_PATH = APP_DIR / "liveSUB_settings.json"
LANGUAGES = ("ja", "en", "vi")
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")
SOURCES = ("both", "system", "mic")
TRANSLATORS = ("argos", "ollama")
DEVICES = ("cpu", "cuda")


def _choice(value: Any, allowed: tuple[str, ...], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default


@dataclass(frozen=True)
class SessionSettings:
    source: str = "both"
    speaker: str = ""
    mic: str = ""
    input_language: str = "auto"
    target_language: str = "vi"
    whisper_model: str = "small"
    device: str = "cpu"
    translator: str = "argos"
    ollama_model: str = "qwen3:4b"
    show_subtitles: bool = True
    terms: tuple[str, ...] = ()

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "SessionSettings":
        raw_terms = values.get("terms", ())
        terms = (
            tuple(dict.fromkeys(str(term).strip() for term in raw_terms if str(term).strip()))
            if isinstance(raw_terms, (list, tuple)) else ()
        )
        return cls(
            source=_choice(values.get("source"), SOURCES, "both"),
            speaker=str(values.get("speaker") or ""),
            mic=str(values.get("mic") or ""),
            input_language=_choice(values.get("input_language"), ("auto",) + LANGUAGES, "auto"),
            target_language=_choice(values.get("target_language"), LANGUAGES, "vi"),
            whisper_model=_choice(values.get("whisper_model"), WHISPER_MODELS, "small"),
            device=_choice(values.get("device"), DEVICES, "cpu"),
            translator=_choice(values.get("translator"), TRANSLATORS, "argos"),
            ollama_model=str(values.get("ollama_model") or "qwen3:4b").strip() or "qwen3:4b",
            show_subtitles=bool(values.get("show_subtitles", True)),
            terms=terms,
        )

    def validate_capture(self) -> None:
        if self.source == "system" and not self.speaker:
            raise ValueError("Chưa chọn loa để thu âm thanh máy.")
        if self.source == "mic" and not self.mic:
            raise ValueError("Chưa chọn micro.")
        if self.source == "both" and not (self.speaker or self.mic):
            raise ValueError("Chưa tìm thấy loa hoặc micro.")

    def to_mapping(self) -> dict[str, Any]:
        values = asdict(self)
        values["terms"] = list(self.terms)
        return values


def load_settings() -> SessionSettings:
    if not SETTINGS_PATH.exists():
        return SessionSettings()
    values = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    if not isinstance(values, dict):
        raise ValueError("File cài đặt phải chứa một đối tượng JSON.")
    return SessionSettings.from_mapping(values)


def save_settings(settings: SessionSettings) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(settings.to_mapping(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
