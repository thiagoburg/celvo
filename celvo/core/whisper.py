from pathlib import Path

from faster_whisper import WhisperModel

from .config import WHISPER_MODEL, OUTPUT_DIR


def transcribe_audio(audio_file: Path):
    model = WhisperModel(
        WHISPER_MODEL,
        device="cpu",
        compute_type="int8",
    )

    segments, info = model.transcribe(
        str(audio_file),
    )

    text = " ".join(
        segment.text.strip()
        for segment in segments
    )

    output = OUTPUT_DIR / f"{audio_file.stem}_raw.txt"

    output.write_text(
        text,
        encoding="utf-8",
    )

    return {
        "language": info.language,
        "text": text,
        "file": output,
    }
