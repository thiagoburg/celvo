"""Celvo command line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core.audio import AudioCaptureError, get_audio_backend
from .core.config import (
    AUDIO_DIR,
    MODEL_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    WHISPER_CLI,
    WHISPER_MODEL,
    ensure_directories,
)
from .core.processor import process_latest
from .core.recorder import record_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="celvo", description="Private, offline audio recording and transcription."
    )
    parser.add_argument("--version", action="version", version=f"Celvo {__version__}")
    commands = parser.add_subparsers(dest="command")
    record = commands.add_parser("record", help="Record microphone and system audio.")
    record.add_argument("--source", choices=("both", "microphone", "system"), default="both")
    record.add_argument("--microphone-device", type=_device_id, help="Input device ID (see `celvo devices`).")
    record.add_argument(
        "--system-device", type=_device_id, help="Output/loopback device ID (see `celvo devices`)."
    )
    commands.add_parser("process", help="Transcribe the most recently recorded WAV file.")
    commands.add_parser("devices", help="List available recording devices.")
    commands.add_parser("diagnose", help="Check audio, storage, executable, and model configuration.")
    commands.add_parser("ui", help="Open the Celvo desktop interface.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        if args.command == "record":
            record_audio(args.source, args.microphone_device, args.system_device)
        elif args.command == "process":
            process_latest()
        elif args.command == "devices":
            _show_devices()
        elif args.command == "diagnose":
            return _diagnose()
        elif args.command == "ui":
            from .ui.app import launch_ui

            launch_ui()
        return 0
    except (AudioCaptureError, RuntimeError, OSError, ValueError) as exc:
        print(f"celvo: error: {exc}", file=sys.stderr)
        return 1


def _show_devices() -> None:
    for device in get_audio_backend().list_devices():
        default = " (default)" if device.is_default else ""
        print(f"{device.kind:10} {device.id}: {device.name}{default}")


def _device_id(value: str) -> str | int:
    return int(value) if value.isdecimal() else value


def _diagnose() -> int:
    ok = True
    try:
        ensure_directories()
        for name, path in (
            ("Recordings", AUDIO_DIR),
            ("Transcriptions", OUTPUT_DIR),
            ("Temporary files", TEMP_DIR),
            ("Models", MODEL_DIR),
        ):
            print(f"OK {name}: {path}")
        devices = get_audio_backend().list_devices()
        print(f"OK audio backend: {get_audio_backend().name} ({len(devices)} visible devices)")
    except (AudioCaptureError, OSError) as exc:
        print(f"ERROR audio/storage: {exc}")
        ok = False
    for name, path in (("whisper-cli", Path(WHISPER_CLI)), ("model", Path(WHISPER_MODEL))):
        exists = path.is_file()
        print(f"{'OK' if exists else 'MISSING'} {name}: {path}")
        ok &= exists
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
