from .files import get_latest_audio
from .whisper import transcribe_audio
from .ollama import clean_text
from .trash import move_to_trash
from .config import OUTPUT_DIR


def process_latest():
    audio = get_latest_audio()

    if not audio:
        raise RuntimeError("No audio files found")

    print(f"Processing: {audio}")

    whisper_result = transcribe_audio(audio)

    raw_file = whisper_result["file"]

    final_text = clean_text(
        whisper_result["text"]
    )

    output = OUTPUT_DIR / f"{audio.stem}.txt"

    output.write_text(
        final_text,
        encoding="utf-8",
    )

    move_to_trash(audio)
    move_to_trash(raw_file)

    print(f"Language: {whisper_result['language']}")
    print(f"Final text saved: {output}")

    return output
