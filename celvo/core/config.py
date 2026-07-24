from pathlib import Path
import os


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path.home() / "Documents" / "celvo"

AUDIO_DIR = DATA_DIR / "audio"
OUTPUT_DIR = DATA_DIR / "transcription"

WHISPER_CLI = str(
    PROJECT_ROOT / "whisper.cpp" / "build" / "bin" / "whisper-cli"
)

WHISPER_MODEL = str(
    PROJECT_ROOT / "models" / "ggml-large-v3-q5_0.bin"
)

WHISPER_LANGUAGE = "es"

THREADS = os.cpu_count()


def ensure_directories():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
