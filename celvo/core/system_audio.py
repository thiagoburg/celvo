import subprocess
from pathlib import Path

from .audio import find_system_monitor


def record_system_audio(output: Path, stop_event):
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

        while not stop_event.is_set():
            stop_event.wait(0.1)

        process.terminate()
        process.wait()
