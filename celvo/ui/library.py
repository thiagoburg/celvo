"""Local recording-library operations used by the desktop UI."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from send2trash import send2trash

from ..core.config import AUDIO_DIR, OUTPUT_DIR


@dataclass(frozen=True)
class RecordingEntry:
    path: Path
    duration_seconds: float | None
    modified_at: datetime
    transcript_path: Path | None

    @property
    def has_transcript(self) -> bool:
        return self.transcript_path is not None and self.transcript_path.is_file()


def list_recordings(
    audio_dir: Path | None = None, transcription_dir: Path | None = None
) -> list[RecordingEntry]:
    """Return completed WAV recordings newest first without reading audio into memory."""
    audio_dir = Path(audio_dir if audio_dir is not None else AUDIO_DIR)
    transcription_dir = Path(transcription_dir if transcription_dir is not None else OUTPUT_DIR)
    entries: list[RecordingEntry] = []
    for path in audio_dir.glob("*.wav"):
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime)
        except OSError:
            continue
        transcript = transcription_dir / f"{path.stem}.txt"
        entries.append(
            RecordingEntry(
                path=path,
                duration_seconds=_wav_duration(path),
                modified_at=modified_at,
                transcript_path=transcript if transcript.is_file() else None,
            )
        )
    return sorted(entries, key=lambda entry: entry.modified_at, reverse=True)


def _wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as source:
            rate = source.getframerate()
            return source.getnframes() / rate if rate else None
    except (OSError, wave.Error):
        return None


def rename_recording(
    entry: RecordingEntry, new_name: str, transcription_dir: Path | None = None
) -> Path:
    """Rename a WAV and its matching transcript without overwriting existing files."""
    new_stem = _validated_stem(new_name)
    source_audio = Path(entry.path)
    if not source_audio.is_file():
        raise FileNotFoundError(f"Recording does not exist: {source_audio}")
    target_audio = source_audio.with_name(f"{new_stem}.wav")
    if os.fspath(source_audio) == os.fspath(target_audio):
        return source_audio

    transcripts = Path(transcription_dir if transcription_dir is not None else OUTPUT_DIR)
    source_text = transcripts / f"{source_audio.stem}.txt"
    target_text = transcripts / f"{new_stem}.txt"
    has_text = source_text.is_file()
    _check_rename_target(source_audio, target_audio)
    if has_text:
        _check_rename_target(source_text, target_text)

    _move_without_overwrite(source_audio, target_audio)
    if has_text:
        try:
            _move_without_overwrite(source_text, target_text)
        except OSError:
            _move_without_overwrite(target_audio, source_audio)
            raise
    return target_audio


def delete_recording(entry: RecordingEntry, transcription_dir: Path | None = None) -> None:
    """Move a recording and matching transcript to the operating system trash."""
    audio = Path(entry.path)
    if not audio.is_file():
        raise FileNotFoundError(f"Recording does not exist: {audio}")
    transcripts = Path(transcription_dir if transcription_dir is not None else OUTPUT_DIR)
    transcript = transcripts / f"{audio.stem}.txt"
    if transcript.is_file():
        send2trash(str(transcript))
    send2trash(str(audio))


def _validated_stem(value: str) -> str:
    name = value.strip()
    if name.lower().endswith(".wav"):
        name = name[:-4]
    if not name or name in {".", ".."}:
        raise ValueError("Enter a non-empty recording name.")
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith((" ", ".")):
        raise ValueError("The recording name contains characters Windows does not allow.")
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved.update(f"COM{i}" for i in range(1, 10))
    reserved.update(f"LPT{i}" for i in range(1, 10))
    if name.split(".", 1)[0].upper() in reserved:
        raise ValueError("That name is reserved by Windows. Choose a different name.")
    if Path(name).name != name:
        raise ValueError("Enter only a file name, not a path.")
    return name


def _check_rename_target(source: Path, target: Path) -> None:
    if target.exists() and not source.samefile(target):
        raise FileExistsError(f"A file already exists with that name: {target}")


def _move_without_overwrite(source: Path, target: Path) -> None:
    """Move across directories safely, including case-only Windows renames."""
    if os.fspath(source) == os.fspath(target):
        return
    if target.exists():
        if not source.samefile(target):
            raise FileExistsError(f"A file already exists with that name: {target}")
        intermediate = source.with_name(f".celvo-rename-{uuid.uuid4().hex}.tmp")
        source.rename(intermediate)
        try:
            intermediate.rename(target)
        except OSError:
            intermediate.rename(source)
            raise
        return
    shutil.move(str(source), str(target))


def open_local_path(path: Path) -> None:
    """Open a local file with the operating system's registered application."""
    path = Path(path)
    if not path.is_file():
        raise RuntimeError(f"File does not exist: {path}")
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError as exc:
        raise RuntimeError(f"Could not open {path}: {exc}") from exc
