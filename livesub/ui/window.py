"""Main Tkinter window. Worker threads communicate through SessionEvent only."""

from __future__ import annotations

from datetime import datetime
from queue import Empty
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from livesub.audio.devices import list_devices
from livesub.session import SessionController
from livesub.settings import (
    DEVICES, LANGUAGES, SOURCES, TRANSLATORS, WHISPER_MODELS,
    SessionSettings, load_settings, save_settings,
)
from livesub.ui.overlay import SubtitleOverlay


class LiveSubApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("liveSub")
        self.root.geometry("880x760")
        self.root.minsize(720, 600)
        self.overlay = SubtitleOverlay(self.root)
        self.session = SessionController()
        self.running = False
        self.stopping = False
        defaults = SessionSettings()

        self.source_var = tk.StringVar(value=defaults.source)
        self.speaker_var = tk.StringVar(value=defaults.speaker)
        self.mic_var = tk.StringVar(value=defaults.mic)
        self.input_language_var = tk.StringVar(value=defaults.input_language)
        self.target_language_var = tk.StringVar(value=defaults.target_language)
        self.model_var = tk.StringVar(value=defaults.whisper_model)
        self.device_var = tk.StringVar(value=defaults.device)
        self.translator_var = tk.StringVar(value=defaults.translator)
        self.ollama_model_var = tk.StringVar(value=defaults.ollama_model)
        self.show_subtitles_var = tk.BooleanVar(value=defaults.show_subtitles)
        self.status_var = tk.StringVar(value="Sẵn sàng. Lần đầu dùng cần tải các model miễn phí.")
        self.settings_widgets: list[tk.Widget] = []

        self._build_ui()
        self._load_settings()
        self.refresh_devices()
        self._update_translator_controls()
        self.root.bind("<Control-Shift-s>", self._toggle_hotkey)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(80, self._poll_events)

    def _combo(
        self, parent: tk.Widget, row: int, label: str, variable: tk.StringVar,
        values: tuple[str, ...],
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", padx=(0, 8), pady=5)
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=19)
        combo.grid(row=row, column=1, sticky="ew", pady=5)
        self.settings_widgets.append(combo)
        return combo

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)
        setup = ttk.LabelFrame(self.root, text="Thu âm và ngôn ngữ", padding=10)
        setup.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        setup.columnconfigure(0, weight=1)
        setup.columnconfigure(1, weight=1)
        left, right = ttk.Frame(setup), ttk.Frame(setup)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        left.columnconfigure(1, weight=1)
        right.columnconfigure(1, weight=1)
        self._combo(left, 0, "Nguồn âm thanh:", self.source_var, SOURCES)
        self._combo(left, 1, "Ngôn ngữ nói:", self.input_language_var, ("auto",) + LANGUAGES)
        self._combo(left, 2, "Dịch sang:", self.target_language_var, LANGUAGES)
        self._combo(left, 3, "Model nghe:", self.model_var, WHISPER_MODELS)
        self._combo(left, 4, "Xử lý bằng:", self.device_var, DEVICES)
        self._combo(right, 0, "Model dịch:", self.translator_var, TRANSLATORS)
        self.translator_var.trace_add("write", lambda *_: self._update_translator_controls())
        ttk.Label(right, text="Model Ollama:").grid(row=1, column=0, sticky="e", padx=(0, 8), pady=5)
        self.ollama_entry = ttk.Entry(right, textvariable=self.ollama_model_var)
        self.ollama_entry.grid(row=1, column=1, sticky="ew", pady=5)
        self.settings_widgets.append(self.ollama_entry)
        self.speaker_combo = self._combo(right, 2, "Loa (loopback):", self.speaker_var, ())
        self.mic_combo = self._combo(right, 3, "Micro:", self.mic_var, ())
        refresh = ttk.Button(right, text="Làm mới thiết bị", command=self.refresh_devices)
        refresh.grid(row=4, column=1, sticky="e", pady=(5, 0))
        self.settings_widgets.append(refresh)
        ttk.Label(
            setup, text="auto = tự nhận diện; ja = Nhật; en = Anh; vi = Việt. "
                        "Argos và Ollama đều chạy trên máy, không cần API key.",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))

        options = ttk.LabelFrame(self.root, text="Phụ đề", padding=10)
        options.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        options.columnconfigure(0, weight=1)
        ttk.Label(options, text="Từ cần giữ nguyên (mỗi dòng một từ hoặc cụm từ):").grid(
            row=0, column=0, sticky="w"
        )
        self.terms_text = ScrolledText(options, height=3, wrap="word")
        self.terms_text.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        ttk.Checkbutton(
            options, text="Hiện phụ đề trên màn hình", variable=self.show_subtitles_var,
            command=self._on_show_changed,
        ).grid(row=2, column=0, sticky="w")

        history_frame = ttk.LabelFrame(self.root, text="Lịch sử trong phiên", padding=10)
        history_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        history_frame.columnconfigure(0, weight=1)
        history_frame.rowconfigure(0, weight=1)
        self.history = ScrolledText(history_frame, wrap="word", height=10, state="disabled")
        self.history.grid(row=0, column=0, sticky="nsew")
        ttk.Button(history_frame, text="Xóa lịch sử", command=self._clear_history).grid(
            row=1, column=0, sticky="e", pady=(6, 0)
        )

        bottom = ttk.Frame(self.root, padding=(12, 4, 12, 12))
        bottom.grid(row=3, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.status_var, wraplength=580).grid(row=0, column=0, sticky="w")
        self.start_button = ttk.Button(bottom, text="Bắt đầu", command=self.start)
        self.start_button.grid(row=0, column=1, padx=(8, 4))
        self.stop_button = ttk.Button(bottom, text="Dừng", command=self.stop, state="disabled")
        self.stop_button.grid(row=0, column=2, padx=(4, 0))

    def _load_settings(self) -> None:
        try:
            settings = load_settings()
        except (OSError, ValueError, TypeError) as exc:
            self.status_var.set(f"Không đọc được cài đặt cũ: {exc}")
            return
        self.source_var.set(settings.source)
        self.speaker_var.set(settings.speaker)
        self.mic_var.set(settings.mic)
        self.input_language_var.set(settings.input_language)
        self.target_language_var.set(settings.target_language)
        self.model_var.set(settings.whisper_model)
        self.device_var.set(settings.device)
        self.translator_var.set(settings.translator)
        self.ollama_model_var.set(settings.ollama_model)
        self.show_subtitles_var.set(settings.show_subtitles)
        self.terms_text.insert("1.0", "\n".join(settings.terms))

    def _settings_snapshot(self) -> SessionSettings:
        terms = [line.strip() for line in self.terms_text.get("1.0", "end-1c").splitlines()]
        return SessionSettings.from_mapping({
            "source": self.source_var.get(),
            "speaker": self.speaker_var.get(),
            "mic": self.mic_var.get(),
            "input_language": self.input_language_var.get(),
            "target_language": self.target_language_var.get(),
            "whisper_model": self.model_var.get(),
            "device": self.device_var.get(),
            "translator": self.translator_var.get(),
            "ollama_model": self.ollama_model_var.get(),
            "show_subtitles": self.show_subtitles_var.get(),
            "terms": terms,
        })

    def _update_translator_controls(self) -> None:
        if hasattr(self, "ollama_entry"):
            enabled = self.translator_var.get() == "ollama" and not self.running
            self.ollama_entry.configure(state="normal" if enabled else "disabled")

    def refresh_devices(self) -> None:
        try:
            devices = list_devices()
            self.speaker_combo.configure(values=devices.speakers)
            self.mic_combo.configure(values=devices.microphones)
            if devices.speakers and self.speaker_var.get() not in devices.speakers:
                self.speaker_var.set(devices.default_speaker or devices.speakers[0])
            if devices.microphones and self.mic_var.get() not in devices.microphones:
                self.mic_var.set(devices.default_microphone or devices.microphones[0])
            if not devices.speakers and not devices.microphones:
                self.status_var.set("Không tìm thấy loa hoặc micro. Hãy kiểm tra thiết bị âm thanh.")
        except Exception as exc:
            self.status_var.set(f"Không dò được thiết bị âm thanh: {exc}")

    def _on_show_changed(self) -> None:
        if not self.show_subtitles_var.get():
            self.overlay.hide()

    def _append_history(self, message: str) -> None:
        self.history.configure(state="normal")
        self.history.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n")
        self.history.see("end")
        self.history.configure(state="disabled")

    def _clear_history(self) -> None:
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.configure(state="disabled")

    def _set_running_state(self, running: bool) -> None:
        self.running = running
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")
        for widget in self.settings_widgets:
            state = "disabled" if running else (
                "readonly" if isinstance(widget, ttk.Combobox) else "normal"
            )
            widget.configure(state=state)
        self._update_translator_controls()

    def _poll_events(self) -> None:
        try:
            while True:
                event = self.session.events.get_nowait()
                if event.session_id != self.session.session_id:
                    continue
                if event.kind == "status":
                    self.status_var.set(str(event.payload))
                elif event.kind == "result":
                    source, translated = event.payload
                    self._append_history(f"{source}  →  {translated}")
                    if self.show_subtitles_var.get():
                        self.overlay.show(source, translated)
                elif event.kind == "error":
                    self.status_var.set(str(event.payload))
                    self._append_history(f"Lỗi: {event.payload}")
                elif event.kind == "done":
                    self.stopping = False
                    self._set_running_state(False)
                    if event.payload == "stopped":
                        self.status_var.set("Đã dừng.")
        except Empty:
            pass
        self.root.after(80, self._poll_events)

    def _toggle_hotkey(self, _event: tk.Event | None = None) -> None:
        if self.running:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        if self.running:
            return
        settings = self._settings_snapshot()
        try:
            settings.validate_capture()
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        try:
            save_settings(settings)
        except OSError as exc:
            self._append_history(f"Không lưu được cài đặt: {exc}")
        if self.session.start(settings):
            self.stopping = False
            self._set_running_state(True)
            self.status_var.set("Đang tải model nhận dạng. Lần đầu có thể cần tải từ Internet…")

    def stop(self) -> None:
        if not self.running or self.stopping:
            return
        self.stopping = True
        self.stop_button.configure(state="disabled")
        self.session.stop()
        self.overlay.hide()
        self.status_var.set("Đang dừng…")

    def close(self) -> None:
        self.session.stop()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
