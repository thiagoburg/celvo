import sys

from .core.recorder import record_audio


DEFAULT_RECORD_TIME = 10


def main():
    if len(sys.argv) < 2:
        print("Usage: celvo <record|process>")
        return

    command = sys.argv[1]

    if command == "record":
        record_audio(DEFAULT_RECORD_TIME)

    elif command == "process":
        print("Process not implemented yet")

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
