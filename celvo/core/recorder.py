from pathlib import Path
import tempfile
import threading
import time
import sys

from .config import AUDIO_DIR, ensure_directories
from .files import get_next_id
from .microphone import record_microphone
from .system_audio import record_system_audio
from .mixer import mix_audio


def format_time(seconds):
    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes:02d}:{seconds:02d}"


def record_audio():
    ensure_directories()

    number = get_next_id()

    filename = f"recording_{number:03d}.wav"
    output = AUDIO_DIR / filename

    stop_event = threading.Event()

    with tempfile.TemporaryDirectory() as temp:
        temp_dir = Path(temp)

        mic_file = temp_dir / "microphone.wav"
        system_file = temp_dir / "system.raw"

        mic_thread = threading.Thread(
            target=record_microphone,
            args=(mic_file, stop_event),
        )

        system_thread = threading.Thread(
            target=record_system_audio,
            args=(system_file, stop_event),
        )

        start_time = time.time()

        print("🔴 Recording 00:00 | Ctrl+C to stop", end="", flush=True)

        mic_thread.start()
        system_thread.start()

        try:
            while True:
                elapsed = int(time.time() - start_time)

                sys.stdout.write(
                    f"\r🔴 Recording {format_time(elapsed)} | Ctrl+C to stop"
                )

                sys.stdout.flush()

                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\nStopping recording...")
            stop_event.set()

        mic_thread.join()
        system_thread.join()

        mix_audio(
            mic_file,
            system_file,
            output,
        )

    duration = int(time.time() - start_time)

    print(f"Duration: {format_time(duration)}")
    print(f"Saved: {output}")

    return output
