"""Voice activity segmentation for 16 kHz mono PCM16 audio."""

from __future__ import annotations

from collections import deque

SAMPLE_RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1_000


class SpeechSegmenter:
    def __init__(
        self, min_seconds: float = 1.2, max_seconds: float = 4.5,
        silence_ms: int = 500, min_speech_ms: int = 240,
    ) -> None:
        self.min_frames = max(1, round(min_seconds * 1_000 / FRAME_MS))
        self.max_frames = max(self.min_frames, round(max_seconds * 1_000 / FRAME_MS))
        self.silence_frames = max(1, silence_ms // FRAME_MS)
        self.min_speech_frames = max(1, min_speech_ms // FRAME_MS)
        self.preroll: deque[bytes] = deque(maxlen=10)
        self.frames: list[bytes] = []
        self.speech_frames = 0
        self.silence_run = 0

    def add(self, frame: bytes, is_speech: bool) -> bytes | None:
        if len(frame) != FRAME_SAMPLES * 2:
            raise ValueError("Audio frame must be 20 ms of mono PCM16 at 16 kHz")
        if not self.frames:
            if not is_speech:
                self.preroll.append(frame)
                return None
            self.frames.extend(self.preroll)
            self.preroll.clear()
        self.frames.append(frame)
        if is_speech:
            self.speech_frames += 1
            self.silence_run = 0
        else:
            self.silence_run += 1
        if len(self.frames) >= self.max_frames:
            return self.flush()
        if len(self.frames) >= self.min_frames and self.silence_run >= self.silence_frames:
            return self.flush()
        return None

    def flush(self) -> bytes | None:
        result = b"".join(self.frames) if self.speech_frames >= self.min_speech_frames else None
        self.frames.clear()
        self.speech_frames = 0
        self.silence_run = 0
        return result
