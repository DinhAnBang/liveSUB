"""Capture speaker loopback and/or microphone audio into bounded segments."""

from __future__ import annotations

from contextlib import ExitStack
from queue import Empty, Full, Queue
import sys
import threading

from livesub.audio.segmenter import FRAME_SAMPLES, SAMPLE_RATE, SpeechSegmenter
from livesub.settings import SessionSettings


def _mono_float(audio, np):
    values = np.asarray(audio, dtype=np.float32)
    if values.ndim == 2:
        values = values.mean(axis=1)
    values = values.reshape(-1)
    if values.size < FRAME_SAMPLES:
        values = np.pad(values, (0, FRAME_SAMPLES - values.size))
    return values[:FRAME_SAMPLES]


def _offer_audio(audio_queue: Queue[bytes], chunk: bytes) -> None:
    try:
        audio_queue.put_nowait(chunk)
    except Full:
        try:
            audio_queue.get_nowait()
        except Empty:
            pass
        try:
            audio_queue.put_nowait(chunk)
        except Full:
            pass


def capture_audio(
    settings: SessionSettings, stop_event: threading.Event, audio_queue: Queue[bytes]
) -> None:
    """Block until stopped; raise capture errors to the session controller."""
    com_initialized = False
    try:
        if sys.platform == "win32":
            import ctypes
            result = ctypes.windll.ole32.CoInitialize(None)
            com_initialized = result in (0, 1)

        import numpy as np
        import soundcard as sc
        import webrtcvad

        vad = webrtcvad.Vad(2)
        segmenter = SpeechSegmenter()
        with ExitStack() as stack:
            system_recorder = None
            mic_recorder = None
            if settings.source in ("system", "both") and settings.speaker:
                speaker = sc.get_microphone(settings.speaker, include_loopback=True)
                system_recorder = stack.enter_context(speaker.recorder(samplerate=SAMPLE_RATE))
            if settings.source in ("mic", "both") and settings.mic:
                microphone = sc.get_microphone(settings.mic)
                mic_recorder = stack.enter_context(microphone.recorder(samplerate=SAMPLE_RATE))
            if system_recorder is None and mic_recorder is None:
                raise RuntimeError("Không mở được nguồn thu âm đã chọn.")

            while not stop_event.is_set():
                system_audio = (
                    _mono_float(system_recorder.record(numframes=FRAME_SAMPLES), np)
                    if system_recorder is not None else None
                )
                mic_audio = (
                    _mono_float(mic_recorder.record(numframes=FRAME_SAMPLES), np)
                    if mic_recorder is not None else None
                )
                if system_audio is not None and mic_audio is not None:
                    mixed = 0.3 * system_audio + 0.7 * mic_audio
                else:
                    mixed = system_audio if system_audio is not None else mic_audio
                frame = np.clip(mixed * 32768.0, -32768, 32767).astype("<i2").tobytes()
                try:
                    is_speech = vad.is_speech(frame, SAMPLE_RATE)
                except Exception:
                    is_speech = False
                chunk = segmenter.add(frame, is_speech)
                if chunk:
                    _offer_audio(audio_queue, chunk)
    finally:
        if com_initialized:
            ctypes.windll.ole32.CoUninitialize()
