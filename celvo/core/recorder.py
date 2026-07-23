from datetime import datetime
from pathlib import Path
import tempfile
import threading

from .config import AUDIO_DIR, ensure_directories
from .microphone import record_microphone
from .system_audio import record_system_audio
from .mixer import mix_audio


def record_audio(duration):
    ensure_directories()

    filename = datetime.now().strftime("recording_%Y%m%d_%H%M%S.wav")
    output = AUDIO_DIR / filename

    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        mic_file = temp_dir / "microphone.wav"
        system_file = temp_dir / "system.raw"

        mic_thread = threading.Thread(
            target=record_microphone,
            args=(mic_file, duration),
        )

        system_thread = threading.Thread(
            target=record_system_audio,
            args=(system_file, duration),
        )

        print("Recording...")

        mic_thread.start()
        system_thread.start()

        mic_thread.join()
        system_thread.join()

        mix_audio(
            mic_file,
            system_file,
            output,
        )

    print(f"Saved: {output}")

    return output
