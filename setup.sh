#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"
LOG_FILE="/tmp/celvo-install.log"

rm -f "$LOG_FILE"

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
        git \
        curl \
        wget \
        cmake \
        build-essential \
        ffmpeg \
        portaudio19-dev

elif command -v pacman >/dev/null 2>&1; then
    run sudo pacman -Sy --noconfirm \
        python \
        python-pip \
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

if [ ! -d "$VENV_DIR" ]; then
    run python3 -m venv "$VENV_DIR"
fi

run "$VENV_DIR/bin/python" -m pip install --upgrade pip
run "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
run "$VENV_DIR/bin/pip" install .

WHISPER_DIR="$PROJECT_DIR/whisper.cpp"
if [ ! -d "$WHISPER_DIR" ]; then
    run git clone https://github.com/ggerganov/whisper.cpp.git "$WHISPER_DIR"
fi

cd "$WHISPER_DIR"
run cmake -B build
run cmake --build build -j"$(nproc)"
cd "$PROJECT_DIR"

MODEL_DIR="$PROJECT_DIR/models"
MODEL="$MODEL_DIR/ggml-large-v3-q5_0.bin"
mkdir -p "$MODEL_DIR"
if [ ! -f "$MODEL" ]; then
    run wget -O "$MODEL" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin
fi

mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/record" <<EOF2
#!/usr/bin/env bash
cd "$PROJECT_DIR"
"$VENV_DIR/bin/python" -m celvo record
EOF2

cat > "$BIN_DIR/process" <<EOF2
#!/usr/bin/env bash
cd "$PROJECT_DIR"
"$VENV_DIR/bin/python" -m celvo process
EOF2

chmod +x "$BIN_DIR/record" "$BIN_DIR/process"

if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc"
fi

run "$VENV_DIR/bin/python" -c "import celvo"

echo
echo "✓ Celvo installed successfully."
echo
echo "Commands:"
echo
echo "  record"
echo "  process"
