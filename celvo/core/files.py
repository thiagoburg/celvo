from .config import AUDIO_DIR, OUTPUT_DIR


def extract_number(filename):
    parts = filename.stem.split("_")

    if len(parts) != 2:
        return None

    try:
        return int(parts[1])

    except ValueError:
        return None


def get_next_id():
    numbers = []

    sources = [
        AUDIO_DIR.glob("recording_*.wav"),
        OUTPUT_DIR.glob("clean_text_*.txt"),
        OUTPUT_DIR.glob("summary_*.txt"),
    ]

    for files in sources:
        for file in files:
            number = extract_number(file)

            if number is not None:
                numbers.append(number)

    if not numbers:
        return 1

    return max(numbers) + 1


def get_latest_audio():
    files = list(
        AUDIO_DIR.glob("recording_*.wav")
    )

    if not files:
        return None

    return max(
        files,
        key=lambda file: file.stat().st_mtime,
    )


def get_output_files(number):
    clean = OUTPUT_DIR / f"clean_text_{number:03d}.txt"
    summary = OUTPUT_DIR / f"summary_{number:03d}.txt"

    return clean, summary
