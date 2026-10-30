"""Draggable, transparent subtitle window."""

from __future__ import annotations

import tkinter as tk


class SubtitleOverlay:
    def __init__(self, root: tk.Tk) -> None:
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        transparent = "#ff00fe"
        self.window.configure(bg=transparent)
        try:
            self.window.attributes("-transparentcolor", transparent)
        except tk.TclError:
            pass
        width, height = 940, 180
        x = max(0, (self.window.winfo_screenwidth() - width) // 2)
        y = max(0, self.window.winfo_screenheight() - height - 50)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.source_label = tk.Label(
            self.window, bg="#101010", fg="white", font=("Arial", 19, "bold"),
            wraplength=900, justify="center", padx=12, pady=7,
        )
        self.source_label.pack(fill="x", pady=(2, 4))
        self.target_label = tk.Label(
            self.window, bg="#101010", fg="white", font=("Arial", 23, "bold"),
            wraplength=900, justify="center", padx=12, pady=8,
        )
        self.target_label.pack(fill="x")
        self.hide_job: str | None = None
        self.drag_offset = (0, 0)
        for widget in (self.window, self.source_label, self.target_label):
            widget.bind("<Button-1>", self._start_drag)
            widget.bind("<B1-Motion>", self._drag)
        self.window.withdraw()

    def _start_drag(self, event: tk.Event) -> None:
        self.drag_offset = (event.x_root - self.window.winfo_x(), event.y_root - self.window.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        dx, dy = self.drag_offset
        self.window.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")

    def show(self, source: str, translation: str) -> None:
        self.source_label.configure(text=source)
        self.target_label.configure(text=translation)
        self.window.deiconify()
        if self.hide_job is not None:
            self.window.after_cancel(self.hide_job)
        self.hide_job = self.window.after(6500, self.hide)

    def hide(self) -> None:
        self.window.withdraw()
        self.hide_job = None
