import logging
import os
import shutil
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from .audio import AudioCaptureError, TrackInfo, get_audio_backend
from .config import AUDIO_DIR, TEMP_DIR, ensure_directories
from .files import get_next_id
from .mixer import mix_tracks, validate_wav

logger = logging.getLogger(__name__)


def format_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, second = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{second:02d}"
    return f"{minutes:02d}:{second:02d}"


def record_audio(
    source: str = "both",
    microphone_device: str | int | None = None,
    system_device: str | int | None = None,
    *,
    stop_event: threading.Event | None = None,
    progress_callback: Callable[[float], None] | None = None,
):
    if source not in {"both", "microphone", "system"}:
        raise ValueError("Recording source must be both, microphone, or system.")
    ensure_directories()
    backend = get_audio_backend()
    sources = [name for name in ("microphone", "system") if source == "both" or source == name]
    number, output, reservation = _reserve_output()
    partial_dir = TEMP_DIR / f"recording_{number:03d}-{uuid.uuid4().hex[:8]}.partial"
    try:
        partial_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        reservation.unlink(missing_ok=True)
        raise
    stop = stop_event if stop_event is not None else threading.Event()
    start = threading.Event()
    ready = {name: threading.Event() for name in sources}
    tracks: dict[str, TrackInfo] = {}
    failures: list[tuple[str, BaseException]] = []

    def worker(name: str) -> None:
        try:
            capture = backend.capture_microphone if name == "microphone" else backend.capture_system_audio
            device = microphone_device if name == "microphone" else system_device
            tracks[name] = capture(partial_dir / f"{name}.wav", stop, ready[name], start, device)
        except BaseException as exc:
            failures.append((name, exc))
            stop.set()
        finally:
            ready[name].set()

    threads = [
        threading.Thread(target=worker, args=(name,), name=f"celvo-{name}", daemon=False) for name in sources
    ]
    for thread in threads:
        thread.start()
    try:
        deadline = time.monotonic() + 15
        while not all(event.is_set() for event in ready.values()):
            if failures:
                break
            if time.monotonic() >= deadline:
                failures.append(
                    ("initialization", AudioCaptureError("Audio source initialization timed out."))
                )
                stop.set()
                break
            time.sleep(0.05)
        if not failures:
            start_at = time.monotonic()
            start.set()
            if progress_callback:
                progress_callback(0.0)
            else:
                print("🔴 Recording 00:00 | Ctrl+C to stop", end="", flush=True)
            while any(thread.is_alive() for thread in threads):
                if failures:
                    stop.set()
                    break
                elapsed = int(time.monotonic() - start_at)
                if progress_callback:
                    progress_callback(float(elapsed))
                else:
                    print(f"\r🔴 Recording {format_time(elapsed)} | Ctrl+C to stop", end="", flush=True)
                time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping recording...")
    finally:
        stop.set()
        start.set()
        for thread in threads:
            thread.join(timeout=15)
        alive = [thread.name for thread in threads if thread.is_alive()]
        if alive:
            failures.append(
                (
                    "shutdown",
                    AudioCaptureError(
                        f"Audio capture did not stop cleanly: {', '.join(alive)}. "
                        f"Partial files retained at {partial_dir}"
                    ),
                )
            )
    if failures:
        reservation.unlink(missing_ok=True)
        raise _format_failure(failures, partial_dir)
    try:
        staging = AUDIO_DIR / f".{output.stem}.{uuid.uuid4().hex}.wav.partial"
        mix_tracks(list(tracks.values()), staging)
        validate_wav(staging)
        os.replace(staging, output)
    except Exception as exc:
        reservation.unlink(missing_ok=True)
        raise AudioCaptureError(
            f"Recording was not finalized; captured source files are preserved at {partial_dir}: {exc}"
        ) from exc
    reservation.unlink(missing_ok=True)
    try:
        shutil.rmtree(partial_dir)
    except OSError as exc:
        logger.warning(
            "Recording finalized, but temporary files could not be removed from %s: %s", partial_dir, exc
        )
    duration = int(time.monotonic() - start_at)
    if progress_callback is None:
        print(f"\nDuration: {format_time(duration)}")
        print(f"Saved: {output}")
    return output


def _reserve_output() -> tuple[int, Path, Path]:
    number = get_next_id()
    while True:
        output = AUDIO_DIR / f"recording_{number:03d}.wav"
        reservation = AUDIO_DIR / f".{output.name}.celvo-lock"
        try:
            fd = os.open(reservation, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            if output.exists():
                reservation.unlink(missing_ok=True)
                number += 1
                continue
            return number, output, reservation
        except FileExistsError:
            number += 1


def _format_failure(
    failures: list[tuple[str, BaseException]], partial: Path | None = None
) -> AudioCaptureError:
    details = "; ".join(f"{name}: {exc}" for name, exc in failures)
    suffix = f" Partial capture files: {partial}" if partial else ""
    return AudioCaptureError(f"Recording failed ({details}).{suffix}")
