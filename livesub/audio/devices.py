"""Discover recording devices without importing the audio backend at startup."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AudioDevices:
    speakers: tuple[str, ...]
    microphones: tuple[str, ...]
    default_speaker: str
    default_microphone: str


def list_devices() -> AudioDevices:
    import soundcard as sc

    speakers = tuple(item.name for item in sc.all_speakers())
    microphones = tuple(item.name for item in sc.all_microphones(include_loopback=False))
    try:
        default_speaker = sc.default_speaker() if speakers else None
    except Exception:
        default_speaker = None
    try:
        default_microphone = sc.default_microphone() if microphones else None
    except Exception:
        default_microphone = None
    return AudioDevices(
        speakers, microphones,
        default_speaker.name if default_speaker else "",
        default_microphone.name if default_microphone else "",
    )
