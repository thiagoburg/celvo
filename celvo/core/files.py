from pathlib import Path

from .config import AUDIO_DIR


def get_latest_audio():
    files = list(AUDIO_DIR.glob("*.wav"))

    if not files:
        return None

    return max(
        files,
        key=lambda file: file.stat().st_mtime,
    )
