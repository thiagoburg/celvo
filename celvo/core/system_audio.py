import subprocess
from pathlib import Path

from .audio import find_system_monitor


def record_system_audio(output: Path, duration: int):
    monitor = find_system_monitor()

    if not monitor:
        raise RuntimeError("System audio monitor not found")

    command = [
        "parec",
        "--device",
        monitor,
        "--format=s16le",
        "--rate=48000",
        "--channels=2",
    ]

    with output.open("wb") as file:
        process = subprocess.Popen(
            command,
            stdout=file,
        )

        try:
            process.wait(timeout=duration)

        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait()
