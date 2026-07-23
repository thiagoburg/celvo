import sys

from .core.recorder import record_audio
from .core.processor import process_latest


DEFAULT_RECORD_TIME = 10


def main():
    if len(sys.argv) < 2:
        print("Usage: celvo <record|process>")
        return

    command = sys.argv[1]

    if command == "record":
        record_audio(DEFAULT_RECORD_TIME)

    elif command == "process":
        process_latest()

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
