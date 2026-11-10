#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOG_FILE="${TMPDIR:-/tmp}/celvo-install.log"
TMP_BIN_DIR="$(mktemp -d)"
WHISPER_VERSION="v1.9.5"
WHISPER_COMMIT="d1be6fde11ac6e0407606b4e42fe72d34add8037"
MODEL_NAME="ggml-large-v3.bin"
MODEL_SHA256="64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2"

trap 'rm -rf "$TMP_BIN_DIR"' EXIT
rm -f "$LOG_FILE"

AVAILABLE_MB="$(df -Pm / | awk 'NR==2 {print $4}')"
if [ "${AVAILABLE_MB:-0}" -lt 8000 ]; then
    echo
    echo "Error: Not enough free disk space."
    echo "Celvo needs at least 8 GB free on / during installation for the full-precision model and build files."
    echo "See $LOG_FILE"
    exit 1
fi

run() {
    if ! "$@" >>"$LOG_FILE" 2>&1; then
        echo
        echo "✗ Installation failed."
        echo "See $LOG_FILE"
        tail -20 "$LOG_FILE" || true
        exit 1
    fi
}

if ! command -v sudo >/dev/null 2>&1; then
    echo "Error: sudo is required."
    exit 1
fi

if command -v dnf >/dev/null 2>&1; then
    run sudo dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        python3-virtualenv \
        python3-tkinter \
        git \
        curl \
        wget \
        cmake \
        gcc-c++ \
        make \
        ffmpeg \
        portaudio-devel

elif command -v apt-get >/dev/null 2>&1; then
    run sudo apt-get update -qq
    run sudo apt-get install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-tk \
        git \
        curl \
        wget \
        cmake \
        build-essential \
        ffmpeg \
        portaudio19-dev \
        pulseaudio-utils

elif command -v pacman >/dev/null 2>&1; then
    run sudo pacman -Sy --noconfirm \
        python \
        python-pip \
        tk \
        git \
        curl \
        wget \
        cmake \
        base-devel \
        ffmpeg \
        portaudio

elif command -v zypper >/dev/null 2>&1; then
    run sudo zypper install -y \
        python3 \
        python3-pip \
        python3-tk \
        git \
        curl \
        wget \
        cmake \
        gcc-c++ \
        make \
        ffmpeg \
        portaudio-devel
else
    echo "Unsupported Linux distribution."
    exit 1
fi

if ! command -v pactl >/dev/null 2>&1; then
    echo
    echo "Error: pactl is required for system audio capture."
    echo "On Ubuntu, install pulseaudio-utils."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    run python3 -m venv "$VENV_DIR"
fi

run "$VENV_DIR/bin/python" -m pip install --upgrade pip
run "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
run "$VENV_DIR/bin/pip" install .

if ! "$VENV_DIR/bin/python" -c 'import tkinter' >>"$LOG_FILE" 2>&1; then
    echo "Error: Tkinter is required for the Celvo desktop UI. Install your distribution's Tk package (for example, python3-tk on Ubuntu/Debian), then rerun setup.sh." >&2
    exit 1
fi

WHISPER_DIR="$PROJECT_DIR/whisper.cpp"
if [ ! -d "$WHISPER_DIR" ]; then
    run git clone --depth 1 --branch "$WHISPER_VERSION" https://github.com/ggml-org/whisper.cpp.git "$WHISPER_DIR"
fi
if [ "$(git -C "$WHISPER_DIR" rev-parse HEAD)" != "$WHISPER_COMMIT" ]; then
    echo "Error: whisper.cpp checkout is not the pinned $WHISPER_VERSION revision." >&2
    exit 1
fi

run cmake -S "$WHISPER_DIR" -B "$WHISPER_DIR/build" -DWHISPER_BUILD_TESTS=OFF
run cmake --build "$WHISPER_DIR/build" --config Release -j"$(nproc)" --target whisper-cli

MODEL_DIR="${CELVO_MODEL_DIR:-$HOME/Documents/celvo/models}"
MODEL="$MODEL_DIR/$MODEL_NAME"
mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL" ] || [ "$(sha256sum "$MODEL" | awk '{print $1}')" != "$MODEL_SHA256" ]; then
    PARTIAL="$MODEL.part"
    run curl --fail --location --retry 3 --retry-connrefused -o "$PARTIAL" \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL_NAME?download=true"
    if [ "$(sha256sum "$PARTIAL" | awk '{print $1}')" != "$MODEL_SHA256" ]; then
        echo "Error: downloaded Whisper model failed SHA-256 verification." >&2
        exit 1
    fi
    mv -f "$PARTIAL" "$MODEL"
fi

mkdir -p "$HOME/.local/bin"
cat > "$TMP_BIN_DIR/celvo" <<EOF2
#!/usr/bin/env bash
exec "$VENV_DIR/bin/celvo" "\$@"
EOF2

cat > "$TMP_BIN_DIR/record" <<EOF2
#!/usr/bin/env bash
exec "$VENV_DIR/bin/celvo" record "\$@"
EOF2

cat > "$TMP_BIN_DIR/process" <<EOF2
#!/usr/bin/env bash
exec "$VENV_DIR/bin/celvo" process "\$@"
EOF2

install -m 755 "$TMP_BIN_DIR/celvo" "$HOME/.local/bin/celvo"
install -m 755 "$TMP_BIN_DIR/record" "$HOME/.local/bin/record"
install -m 755 "$TMP_BIN_DIR/process" "$HOME/.local/bin/process"

APPLICATIONS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPLICATIONS_DIR"
DESKTOP_EXECUTABLE="${VENV_DIR//\\/\\\\}"
DESKTOP_EXECUTABLE="${DESKTOP_EXECUTABLE//\"/\\\"}"
cat > "$TMP_BIN_DIR/celvo.desktop" <<EOF2
[Desktop Entry]
Type=Application
Name=Celvo
Comment=Private, offline audio recording and transcription
Exec="$DESKTOP_EXECUTABLE/bin/celvo" ui
Terminal=false
Categories=AudioVideo;Audio;Recorder;
EOF2
install -m 644 "$TMP_BIN_DIR/celvo.desktop" "$APPLICATIONS_DIR/celvo.desktop"

run "$VENV_DIR/bin/python" -c "import celvo"
run "$VENV_DIR/bin/celvo" --version

cat <<EOF
✓ Celvo installed successfully.

Commands:

  celvo record
  celvo process

Desktop app: Celvo in your applications menu (or run: celvo ui)
EOF
