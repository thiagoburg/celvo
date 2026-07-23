from .files import get_latest_audio
from .whisper import transcribe_audio


def process_latest():

    audio = get_latest_audio()

    if not audio:
        raise RuntimeError("No audio files found")

    print(f"🎧 Processing: {audio.name}")

    print("🧠 Loading Whisper large-v3...")

    print("📝 Transcribing audio...")

    result = transcribe_audio(audio)

    print("")
    print(f"Language: {result['language']}")
    print("Saved:")
    print(result["file"])

    return result["file"]
