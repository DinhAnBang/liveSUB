"""Threaded session orchestration with UI-safe events."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
import threading

from livesub.audio.capture import capture_audio
from livesub.engines.argos import ArgosTranslator
from livesub.engines.ollama import OllamaTranslator
from livesub.engines.whisper import LocalWhisper
from livesub.settings import LANGUAGES, SessionSettings


@dataclass(frozen=True)
class SessionEvent:
    session_id: int
    kind: str
    payload: str | tuple[str, str] = ""


class SessionController:
    def __init__(self) -> None:
        self.events: Queue[SessionEvent] = Queue()
        self.session_id = 0
        self.running = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._requested_stop = threading.Event()

    def start(self, settings: SessionSettings) -> bool:
        settings.validate_capture()
        with self._lock:
            if self.running:
                return False
            self.running = True
            self.session_id += 1
            session_id = self.session_id
            self._stop_event = threading.Event()
            self._requested_stop = threading.Event()
        threading.Thread(
            target=self._run,
            args=(session_id, settings, self._stop_event, self._requested_stop),
            name="liveSub-processing", daemon=True,
        ).start()
        return True

    def stop(self) -> None:
        self._requested_stop.set()
        self._stop_event.set()

    def _emit(self, session_id: int, kind: str, payload: str | tuple[str, str] = "") -> None:
        self.events.put(SessionEvent(session_id, kind, payload))

    def _record(
        self, session_id: int, settings: SessionSettings, stop_event: threading.Event,
        audio_queue: Queue[bytes], done: threading.Event,
    ) -> None:
        try:
            capture_audio(settings, stop_event, audio_queue)
        except Exception as exc:
            if not stop_event.is_set():
                self._emit(session_id, "error", f"Thu âm: {exc}")
                stop_event.set()
        finally:
            done.set()

    def _run(
        self, session_id: int, settings: SessionSettings,
        stop_event: threading.Event, requested_stop: threading.Event,
    ) -> None:
        recorder: threading.Thread | None = None
        audio_queue: Queue[bytes] = Queue(maxsize=8)
        recorder_done = threading.Event()
        try:
            recognizer = LocalWhisper(settings.whisper_model, settings.device)
            if stop_event.is_set():
                return
            translator = (
                ArgosTranslator() if settings.translator == "argos"
                else OllamaTranslator(settings.ollama_model)
            )
            self._emit(session_id, "status", "Đang nghe. Phụ đề sẽ hiện khi có lời nói.")
            recorder = threading.Thread(
                target=self._record,
                args=(session_id, settings, stop_event, audio_queue, recorder_done),
                name="liveSub-recorder", daemon=True,
            )
            recorder.start()

            while not stop_event.is_set():
                try:
                    audio = audio_queue.get(timeout=0.2)
                except Empty:
                    if recorder_done.is_set():
                        break
                    continue
                hint = settings.input_language
                transcript, detected = recognizer.transcribe(
                    audio, None if hint == "auto" else hint, settings.terms,
                )
                if not transcript or stop_event.is_set():
                    continue
                source_language = detected if hint == "auto" else hint
                if source_language not in LANGUAGES:
                    self._emit(
                        session_id, "status",
                        f"Bỏ qua tiếng {source_language}; chỉ hỗ trợ ja, en, vi.",
                    )
                    continue
                translation = translator.translate(
                    transcript, source_language, settings.target_language, settings.terms,
                    lambda message: self._emit(session_id, "status", message),
                )
                if translation and not stop_event.is_set():
                    self._emit(session_id, "result", (transcript, translation))
                    self._emit(session_id, "status", "Đang nghe. Phụ đề sẽ hiện khi có lời nói.")
        except Exception as exc:
            self._emit(session_id, "error", str(exc))
        finally:
            stop_event.set()
            if recorder is not None:
                recorder.join(timeout=1)
            with self._lock:
                self.running = False
            self._emit(session_id, "done", "stopped" if requested_stop.is_set() else "error")
