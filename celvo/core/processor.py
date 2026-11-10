from collections.abc import Callable
from pathlib import Path
from threading import Event

from .files import get_latest_audio
from .whisper import transcribe_audio


def process_latest():
    audio = get_latest_audio()

    if not audio:
        raise RuntimeError("No audio files found")

    return process_audio(audio)


def process_audio(
    audio: Path,
    status_callback: Callable[[str], None] | None = None,
    *,
    cancel_event: Event | None = None,
) -> Path:
    """Transcribe one selected recording, optionally reporting status to a caller."""
    audio = Path(audio)
    if not audio.is_file():
        raise RuntimeError(f"Audio file does not exist: {audio}")
    if status_callback:
        status_callback(f"Transcribing {audio.name} locally with whisper.cpp…")
    else:
        print(f"🎧 Processing: {audio.name}")
        print("📝 Transcribing locally with whisper.cpp...")
    result = transcribe_audio(audio, cancel_event=cancel_event)
    output = Path(result["file"])
    if status_callback:
        status_callback(f"Transcript saved: {output}")
    else:
        print(f"Language: {result['language']}\nSaved: {output}")

    return output
