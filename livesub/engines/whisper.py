"""Offline speech recognition with faster-whisper."""

from __future__ import annotations

from livesub.settings import MODEL_DIR


class LocalWhisper:
    def __init__(self, model_name: str = "small", device: str = "cpu") -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError("Thiếu faster-whisper. Cài các gói trong requirements.txt.") from exc
        compute_type = "int8" if device == "cpu" else "float16"
        try:
            self.model = WhisperModel(
                model_name, device=device, compute_type=compute_type,
                download_root=str(MODEL_DIR / "whisper"),
            )
        except Exception as exc:
            raise RuntimeError(f"Không tải được Whisper ({model_name}, {device}): {exc}") from exc

    def transcribe(
        self, pcm16: bytes, language: str | None = None, terms: tuple[str, ...] = ()
    ) -> tuple[str, str]:
        import numpy as np

        audio = np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0
        if audio.size == 0:
            return "", language or ""
        segments, info = self.model.transcribe(
            audio,
            language=language,
            initial_prompt=", ".join(terms) or None,
            beam_size=1,
            condition_on_previous_text=False,
            vad_filter=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, language or getattr(info, "language", "") or ""
