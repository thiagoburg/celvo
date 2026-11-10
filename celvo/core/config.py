"""Platform-aware Celvo paths and runtime settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from shutil import which

from platformdirs import user_data_dir

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "Celvo"
if sys.platform.startswith("win"):
    _default_data = Path.home() / "Documents" / "Celvo"
elif sys.platform.startswith("linux"):
    _default_data = Path.home() / "Documents" / "celvo"
else:
    _default_data = Path(user_data_dir(APP_NAME, appauthor=False))


def _configured_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path.home() / path


DATA_DIR = _configured_path(os.environ.get("CELVO_DATA_DIR", _default_data))
AUDIO_DIR = _configured_path(os.environ.get("CELVO_AUDIO_DIR", DATA_DIR / "audio"))
OUTPUT_DIR = _configured_path(os.environ.get("CELVO_TRANSCRIPTIONS_DIR", DATA_DIR / "transcription"))
TEMP_DIR = _configured_path(os.environ.get("CELVO_TEMP_DIR", DATA_DIR / "temporary"))
MODEL_DIR = _configured_path(os.environ.get("CELVO_MODEL_DIR", DATA_DIR / "models"))
WHISPER_LANGUAGE = os.environ.get("CELVO_LANGUAGE", "es")
THREADS = max(1, os.cpu_count() or 1)
MODEL_NAME = "ggml-large-v3.bin"
LEGACY_MODEL_NAMES = ("ggml-large-v3-q5_0.bin",)


def discover_whisper_cli() -> Path:
    """Find whisper-cli without relying on the current working directory."""
    override = os.environ.get("CELVO_WHISPER_CLI")
    if override:
        return _configured_path(override)
    executable = "whisper-cli.exe" if os.name == "nt" else "whisper-cli"
    candidates = [
        PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "Release" / "whisper-cli.exe",
        PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "Release" / "whisper-cli",
        PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "whisper-cli.exe",
        PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "whisper-cli",
        PROJECT_ROOT / "bin" / "whisper-cli.exe",
        PROJECT_ROOT / "bin" / "whisper-cli",
    ]
    located = which(executable) or which("whisper-cli")
    if located:
        candidates.insert(0, Path(located))
    return next((path for path in candidates if path.is_file()), candidates[0])


def discover_model() -> Path:
    override = os.environ.get("CELVO_WHISPER_MODEL")
    if override:
        return _configured_path(override)
    candidates = [
        MODEL_DIR / MODEL_NAME,
        PROJECT_ROOT / "models" / MODEL_NAME,
        *(MODEL_DIR / name for name in LEGACY_MODEL_NAMES),
        *(PROJECT_ROOT / "models" / name for name in LEGACY_MODEL_NAMES),
    ]
    return next((path for path in candidates if path.is_file()), candidates[0])


WHISPER_CLI = discover_whisper_cli()
WHISPER_MODEL = discover_model()


def ensure_directories() -> None:
    for directory in (AUDIO_DIR, OUTPUT_DIR, TEMP_DIR, MODEL_DIR):
        directory.mkdir(parents=True, exist_ok=True)
