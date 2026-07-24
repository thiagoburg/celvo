#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"

INSTALLER_VERSION="1.1.2"

LOG_FILE="/tmp/celvo-install.log"

rm -f "$LOG_FILE"

step() {
    echo
    echo "==> $1"
}

ok() {
    echo "✓ Done"
}

info() {
    echo "$1"
}

run() {
    if ! "$@" >>"$LOG_FILE" 2>&1; then
        echo
        echo "✗ Installation failed."
        echo "Check $LOG_FILE"
        exit 1
    fi
}


step "Detecting system..."

if command -v dnf >/dev/null 2>&1; then

    info "✓ Fedora Linux detected"

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

elif command -v apt >/dev/null 2>&1; then

    info "✓ Debian/Ubuntu detected"

    run sudo apt update

    run sudo apt install -y \
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

    info "✓ Arch Linux detected"

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

    info "✓ openSUSE detected"

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

ok


step "Checking Python..."

command -v python3 >/dev/null 2>&1 || exit 1

ok


step "Creating Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    run python3 -m venv "$VENV_DIR"
fi

ok


step "Installing Python packages..."

run "$VENV_DIR/bin/python" -m pip install --upgrade pip
run "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

ok


step "Installing Celvo package..."

run "$VENV_DIR/bin/pip" install .

ok


step "Installing whisper.cpp..."

WHISPER_DIR="$PROJECT_DIR/whisper.cpp"

if [ ! -d "$WHISPER_DIR" ]; then

    run git clone \
        https://github.com/ggerganov/whisper.cpp.git \
        "$WHISPER_DIR"

fi

cd "$WHISPER_DIR"

run cmake -B build
run cmake --build build -j"$(nproc)"

cd "$PROJECT_DIR"

ok


step "Downloading Whisper model..."

MODEL_DIR="$PROJECT_DIR/models"
MODEL="$MODEL_DIR/ggml-large-v3-q5_0.bin"

mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL" ]; then

    info "Downloading large-v3 Whisper model (~1GB)"

    run wget \
        -O "$MODEL" \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin

else

    info "✓ Whisper model already present"

fi

ok


step "Creating commands..."

mkdir -p "$BIN_DIR"


cat > "$BIN_DIR/record" <<EOF
#!/usr/bin/env bash
cd "$PROJECT_DIR"
"$VENV_DIR/bin/python" -m celvo record
EOF


cat > "$BIN_DIR/process" <<EOF
#!/usr/bin/env bash
cd "$PROJECT_DIR"
"$VENV_DIR/bin/python" -m celvo process
EOF


chmod +x "$BIN_DIR/record"
chmod +x "$BIN_DIR/process"

ok


step "Verifying installation..."

run "$VENV_DIR/bin/python" -c "import celvo"

ok


echo
echo "✓ Celvo installed successfully."
echo
echo "Commands:"
echo
echo "  record"
echo "  process"
