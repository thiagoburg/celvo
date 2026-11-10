"""Safe local whisper.cpp invocation."""

from __future__ import annotations

import os
import subprocess
import threading
import uuid
import wave
from pathlib import Path

from .config import OUTPUT_DIR, THREADS, WHISPER_CLI, WHISPER_LANGUAGE, WHISPER_MODEL

_active_process_lock = threading.Lock()
_active_processes: set[subprocess.Popen] = set()


def terminate_active_transcriptions() -> None:
    """Immediately stop active whisper-cli processes, safe to call from the UI thread."""
    with _active_process_lock:
        processes = tuple(_active_processes)
    for process in processes:
        if process.poll() is None:
            try:
                # terminate() maps to TerminateProcess on Windows, so an inference
                # that is busy inside native code cannot hold the UI open.
                process.terminate()
            except OSError:
                pass


class TranscriptionCancelled(RuntimeError):
    """Raised when the user closes Celvo during transcription."""


def transcribe_audio(
    audio_file: Path, *, cancel_event: threading.Event | None = None
) -> dict[str, str | Path]:
    audio_file = Path(audio_file)
    if not audio_file.is_file():
        raise RuntimeError(f"Audio file does not exist: {audio_file}")
    if not Path(WHISPER_CLI).is_file():
        raise RuntimeError(f"whisper.cpp executable was not found: {WHISPER_CLI}. Set CELVO_WHISPER_CLI.")
    if not Path(WHISPER_MODEL).is_file():
        raise RuntimeError(f"Whisper model was not found: {WHISPER_MODEL}. Set CELVO_WHISPER_MODEL.")
    try:
        with wave.open(str(audio_file), "rb") as source:
            if source.getnframes() < 1:
                raise RuntimeError(f"Audio file is empty: {audio_file}")
            if source.getnchannels() not in (1, 2) or source.getsampwidth() not in (2, 4):
                raise RuntimeError(f"Audio file has an unsupported WAV format: {audio_file}")
    except wave.Error as exc:
        raise RuntimeError(f"Audio file is not a valid WAV: {audio_file}: {exc}") from exc

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_base = OUTPUT_DIR / audio_file.stem
    text_file = Path(f"{output_base}.txt")
    temporary_base = OUTPUT_DIR / f".{audio_file.stem}.{uuid.uuid4().hex}.partial"
    temporary_text = Path(f"{temporary_base}.txt")
    command = [
        str(WHISPER_CLI),
        "-m",
        str(WHISPER_MODEL),
        "-f",
        str(audio_file),
        "-l",
        WHISPER_LANGUAGE,
        "-t",
        str(THREADS),
        "-otxt",
        "-of",
        str(temporary_base),
    ]
    run_options = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if os.name == "nt":
        # Keep whisper-cli hidden and isolate it so shutdown cannot leave child processes behind.
        run_options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    process = None
    try:
        process = subprocess.Popen(command, **run_options)
        with _active_process_lock:
            _active_processes.add(process)
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                if cancel_event is not None and cancel_event.is_set():
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate(timeout=5)
                    temporary_text.unlink(missing_ok=True)
                    raise TranscriptionCancelled(
                        "Transcription cancelled because Celvo is closing."
                    )
    except OSError as exc:
        temporary_text.unlink(missing_ok=True)
        raise RuntimeError(f"Could not start whisper.cpp: {exc}") from exc
    finally:
        if process is not None:
            with _active_process_lock:
                _active_processes.discard(process)
    if process.returncode:
        temporary_text.unlink(missing_ok=True)
        detail = (stderr or stdout or "").strip()
        raise RuntimeError(
            f"whisper.cpp exited with status {process.returncode}: {detail or 'no diagnostic output'}"
        )
    if not temporary_text.is_file():
        raise RuntimeError(f"whisper.cpp reported success but did not create transcription: {text_file}")
    try:
        text = temporary_text.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        temporary_text.unlink(missing_ok=True)
        raise RuntimeError(f"Could not read UTF-8 transcription {temporary_text}: {exc}") from exc
    os.replace(temporary_text, text_file)
    return {"language": WHISPER_LANGUAGE, "text": text, "file": text_file}
