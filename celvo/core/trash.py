import subprocess
from pathlib import Path


def move_to_trash(file: Path):
    subprocess.run(
        ["gio", "trash", str(file)],
        check=True,
    )
