from pathlib import Path
import subprocess

from .config import (
    WHISPER_CLI,
    WHISPER_MODEL,
    WHISPER_LANGUAGE,
    OUTPUT_DIR,
)


def transcribe_audio(audio_file: Path):

    output_file = OUTPUT_DIR / audio_file.stem

    command = [
        WHISPER_CLI,
        "-m",
        WHISPER_MODEL,
        "-f",
        str(audio_file),
        "-l",
        WHISPER_LANGUAGE,
        "-otxt",
        "-of",
        str(output_file),
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    text_file = Path(
        str(output_file) + ".txt"
    )

    text = text_file.read_text(
        encoding="utf-8"
    )

    return {
        "language": WHISPER_LANGUAGE,
        "text": text,
        "file": text_file,
    }
