"""Small local-first Celvo desktop application."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from ..core.recorder import format_time
from .controller import RecordingController, TranscriptionController, UiEvent
from .library import RecordingEntry, delete_recording, list_recordings, open_local_path, rename_recording
from .theme import apply_theme, apply_windows_dark_titlebar


class CelvoWindow:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Celvo — Private audio recorder")
        self.root.minsize(720, 500)
        self.root.geometry("850x620")
        self.recording = RecordingController()
        self.transcription = TranscriptionController()
        self._recording_active = False
        self._transcribing = False
        self._closing = False
        self._entries: dict[str, RecordingEntry] = {}
        self.style = ttk.Style(root)

        self._build_widgets()
        self._apply_theme()
        self.refresh_library()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._poll_events)

    def _build_widgets(self) -> None:
        main = ttk.Frame(self.root, padding=18)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(2, weight=1)

        ttk.Label(main, text="Celvo", font=("TkDefaultFont", 20, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(main, text="Private, offline recording and transcription").grid(
            row=0, column=1, sticky="e", padx=(12, 8)
        )
        capture = ttk.LabelFrame(main, text="Record", padding=12)
        capture.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 12))
        capture.columnconfigure(0, weight=1)

        controls = ttk.Frame(capture)
        controls.grid(row=0, column=0, sticky="ew")
        self.record_button = ttk.Button(controls, text="●  Start recording", command=self.start_recording)
        self.record_button.pack(side="left")
        self.stop_button = ttk.Button(
            controls, text="■  Stop and save", command=self.stop_recording, state="disabled"
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.timer_var = tk.StringVar(value="00:00")
        ttk.Label(controls, textvariable=self.timer_var, font=("TkDefaultFont", 14, "bold")).pack(
            side="right"
        )

        library = ttk.LabelFrame(main, text="Recordings", padding=10)
        library.grid(row=2, column=0, columnspan=2, sticky="nsew")
        library.rowconfigure(0, weight=1)
        library.columnconfigure(0, weight=1)
        columns = ("name", "duration", "modified", "transcript")
        self.tree = ttk.Treeview(library, columns=columns, show="headings", selectmode="browse")
        for column, title, width in (
            ("name", "Recording", 260),
            ("duration", "Duration", 90),
            ("modified", "Recorded", 160),
            ("transcript", "Transcript", 110),
        ):
            self.tree.heading(column, text=title)
            self.tree.column(column, width=width, anchor="w")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(library, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._selection_changed())
        self.tree.bind("<Double-1>", lambda _event: self.open_recording())

        actions = ttk.Frame(library)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.transcribe_button = ttk.Button(
            actions, text="Transcribe selected", command=self.transcribe_selected, state="disabled"
        )
        self.transcribe_button.pack(side="left")
        self.open_audio_button = ttk.Button(
            actions, text="Open audio", command=self.open_recording, state="disabled"
        )
        self.open_audio_button.pack(side="left", padx=(8, 0))
        self.open_transcript_button = ttk.Button(
            actions, text="Open transcript", command=self.open_transcript, state="disabled"
        )
        self.open_transcript_button.pack(side="left", padx=(8, 0))
        self.rename_button = ttk.Button(
            actions, text="Rename", command=self.rename_selected, state="disabled"
        )
        self.rename_button.pack(side="left", padx=(8, 0))
        self.delete_button = ttk.Button(
            actions, text="Delete", command=self.delete_selected, state="disabled"
        )
        self.delete_button.pack(side="left", padx=(8, 0))
        self.status_var = tk.StringVar(value="Ready. Recordings and transcripts stay on this device.")
        ttk.Label(main, textvariable=self.status_var, wraplength=800).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(12, 0)
        )

    def _apply_theme(self) -> None:
        apply_theme(self.root, self.style)
        self.root.after(150, lambda: apply_windows_dark_titlebar(self.root))

    def start_recording(self) -> None:
        try:
            self.recording.start("both", None, None)
        except Exception as exc:
            self._show_error("Could not start recording", exc)
            return
        self._recording_active = True
        self.timer_var.set("00:00")
        self.status_var.set("Starting audio capture…")
        self.record_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

    def stop_recording(self) -> None:
        if self._recording_active:
            self.status_var.set("Stopping and saving recording…")
            self.stop_button.configure(state="disabled")
            self.recording.stop()

    def transcribe_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if entry.has_transcript and not messagebox.askyesno(
            "Replace transcript?",
            f"A transcript already exists for {entry.path.name}. Transcribe again and replace it?",
            parent=self.root,
        ):
            return
        try:
            self.transcription.start(entry.path)
        except Exception as exc:
            self._show_error("Could not start transcription", exc)
            return
        self._transcribing = True
        self.transcribe_button.configure(state="disabled")
        self.status_var.set(f"Transcribing {entry.path.name} locally…")

    def open_recording(self) -> None:
        entry = self._selected_entry()
        if entry is not None:
            self._open_path(entry.path)

    def open_transcript(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        if not entry.has_transcript or entry.transcript_path is None:
            self._show_error("Transcript not found", "Transcribe this recording first.")
            return
        self._open_path(entry.transcript_path)

    def rename_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        new_name = simpledialog.askstring(
            "Rename recording",
            "New recording name (without .wav):",
            initialvalue=entry.path.stem,
            parent=self.root,
        )
        if new_name is None:
            return
        try:
            new_path = rename_recording(entry, new_name)
        except (OSError, ValueError, RuntimeError) as exc:
            self._show_error("Could not rename recording", exc)
            return
        self.status_var.set(f"Recording renamed: {new_path.name}")
        self.refresh_library(selected_path=new_path)

    def delete_selected(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            return
        has_transcript = entry.has_transcript
        details = " The matching transcript will be moved too." if has_transcript else ""
        if not messagebox.askyesno(
            "Move recording to Recycle Bin?",
            f"Move {entry.path.name} to the Recycle Bin?{details}\n\n"
            "You can restore it from the Recycle Bin.",
            parent=self.root,
        ):
            return
        try:
            delete_recording(entry)
        except (OSError, RuntimeError) as exc:
            self._show_error("Could not delete recording", exc)
            self.refresh_library()
            return
        self.status_var.set(f"Moved {entry.path.name} to the Recycle Bin.")
        self.refresh_library()

    def _open_path(self, path: Path) -> None:
        try:
            open_local_path(path)
        except Exception as exc:
            self._show_error("Could not open file", exc)

    def refresh_library(self, selected_path: Path | None = None) -> None:
        if selected_path is None:
            selected = self._selected_entry()
            selected_path = selected.path if selected else None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._entries.clear()
        try:
            entries = list_recordings()
        except OSError as exc:
            self.status_var.set(f"Could not read recordings: {exc}")
            entries = []
        selected_iid = None
        for index, entry in enumerate(entries):
            iid = f"recording-{index}"
            self._entries[iid] = entry
            duration = _format_duration(entry.duration_seconds)
            modified = entry.modified_at.strftime("%Y-%m-%d %H:%M")
            transcript = "Ready" if entry.has_transcript else "Not transcribed"
            self.tree.insert("", "end", iid=iid, values=(entry.path.name, duration, modified, transcript))
            if entry.path == selected_path:
                selected_iid = iid
        if selected_iid:
            self.tree.selection_set(selected_iid)
            self.tree.focus(selected_iid)
        self._selection_changed()

    def _selected_entry(self) -> RecordingEntry | None:
        selection = self.tree.selection()
        return self._entries.get(selection[0]) if selection else None

    def _selection_changed(self) -> None:
        entry = self._selected_entry()
        selected = entry is not None
        self.open_audio_button.configure(state="normal" if selected else "disabled")
        self.transcribe_button.configure(
            state="normal" if selected and not self._transcribing else "disabled"
        )
        self.open_transcript_button.configure(
            state="normal" if selected and entry is not None and entry.has_transcript else "disabled"
        )
        self.rename_button.configure(state="normal" if selected else "disabled")
        self.delete_button.configure(state="normal" if selected else "disabled")

    def _poll_events(self) -> None:
        for event in self.recording.drain_events() + self.transcription.drain_events():
            self._handle_event(event)
        self.root.after(100, self._poll_events)

    def _handle_event(self, event: UiEvent) -> None:
        if event.kind == "recording_progress":
            seconds = float(event.payload)
            self.timer_var.set(format_time(seconds))
            self.status_var.set("Recording… Click Stop and save when finished.")
        elif event.kind == "recording_finished":
            self._recording_active = False
            self.record_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_var.set(f"Recording saved: {event.payload}")
            self.refresh_library()
        elif event.kind == "recording_failed":
            self._recording_active = False
            self.record_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.status_var.set(f"Recording failed: {event.payload}")
            self._show_error("Recording failed", event.payload)
        elif event.kind == "transcription_status":
            self.status_var.set(str(event.payload))
        elif event.kind == "transcription_finished":
            self._transcribing = False
            self.status_var.set(f"Transcript saved: {event.payload}")
            self.refresh_library()
            notify_transcription_ready(self.root, Path(event.payload))
        elif event.kind == "transcription_failed":
            self._transcribing = False
            self.status_var.set(f"Transcription failed: {event.payload}")
            self._show_error("Transcription failed", event.payload)
        elif event.kind == "transcription_cancelled":
            self._transcribing = False
            if not self._closing:
                self.status_var.set("Transcription cancelled.")
        self._selection_changed()
        if self._closing and not self._recording_active and not self._transcribing:
            self.root.destroy()

    def close(self) -> None:
        if self._closing:
            return
        if self._recording_active or self._transcribing:
            if not messagebox.askyesno(
                "Celvo is busy",
                "Stop the recording and wait for active work to finish before closing Celvo?",
                parent=self.root,
            ):
                return
            self._closing = True
            if self._recording_active:
                self.stop_recording()
            if self._transcribing:
                self.transcription.cancel()
            self.status_var.set("Stopping active work before closing…")
            return
        self.root.destroy()

    def _show_error(self, title: str, error: object) -> None:
        messagebox.showerror(title, str(error), parent=self.root)


def _format_duration(seconds: float | None) -> str:
    return "Unknown" if seconds is None else format_time(seconds)


def notify_transcription_ready(root: tk.Tk, transcript: Path) -> None:
    """Notify the user audibly and visually when local transcription completes."""
    try:
        if sys.platform == "win32":
            import winsound

            winsound.MessageBeep(winsound.MB_ICONINFORMATION)
        else:
            root.bell()
    except (ImportError, RuntimeError, tk.TclError):
        pass
    messagebox.showinfo(
        "Transcription ready",
        f"Your transcript is ready:\n{transcript}",
        parent=root,
    )


def launch_ui() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError(f"Could not open the Celvo desktop window: {exc}") from exc
    CelvoWindow(root)
    root.mainloop()
