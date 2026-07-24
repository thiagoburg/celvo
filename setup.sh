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
        echo
        echo "See log:"
        echo "  $LOG_FILE"
        echo
        echo "Last log lines:"
        tail -20 "$LOG_FILE"
        exit 1
    fi
}

echo
echo "================================"
echo " Installing Celvo v$INSTALLER_VERSION"
echo "================================"
echo

if [ "$EUID" -eq 0 ]; then
    echo "Error: Do not run this installer as root."
    exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
    echo "Error: sudo is required."
    exit 1
fi


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

    ok

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
        g++ \
        make \
        ffmpeg \
        portaudio19-dev

    ok

elif command -v pacman >/dev/null 2>&1; then

    info "✓ Arch Linux detected"

    run sudo pacman -Sy --noconfirm \
        python \
        python-pip \
        python-virtualenv \
        git \
        curl \
        wget \
        cmake \
        gcc \
        make \
        ffmpeg \
        portaudio

    ok

elif command -v zypper >/dev/null 2>&1; then

    info "✓ openSUSE detected"

    run sudo zypper install -y \
        python3 \
        python3-pip \
        python3-devel \
        git \
        curl \
        wget \
        cmake \
        gcc-c++ \
        make \
        ffmpeg \
        portaudio-devel

    ok

else

    echo "Unsupported Linux distribution."
    echo
    echo "Supported:"
    echo "- Fedora"
    echo "- Ubuntu"
    echo "- Debian"
    echo "- Arch Linux"
    echo "- openSUSE"

    exit 1

fi


step "Checking Python..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 was not installed."
    exit 1
fi


step "Creating Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    run python3 -m venv "$VENV_DIR"
fi

ok


source "$VENV_DIR/bin/activate"


step "Installing Python packages..."

run python -m pip install --upgrade pip
run pip install -r "$PROJECT_DIR/requirements.txt"

ok


step "Installing Celvo package..."

run "$VENV_DIR/bin/pip" install .

ok

step "Installing whisper.cpp..."


if [ ! -d "$PROJECT_DIR/whisper.cpp" ]; then

    run git clone \
    https://github.com/ggml-org/whisper.cpp.git \
    "$PROJECT_DIR/whisper.cpp"

fi


cd "$PROJECT_DIR/whisper.cpp"


if [ ! -d "build" ]; then

    run cmake -B build

fi


run cmake --build build -j"$(nproc)"

ok


step "Downloading Whisper model..."


MODEL_DIR="$PROJECT_DIR/models"
MODEL="$MODEL_DIR/ggml-large-v3-q5_0.bin"


mkdir -p "$MODEL_DIR"


if [ ! -f "$MODEL" ]; then

    echo "Downloading large-v3 Whisper model (~1GB)"

    run wget \
    -O "$MODEL" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin

else

    info "✓ Whisper model already present"

fi

ok


step "Creating commands..."


mkdir -p "$BIN_DIR"


cat > "$BIN_DIR/record" <<WRAPPER
#!/usr/bin/env bash

cd "$PROJECT_DIR"

"$VENV_DIR/bin/python" -m celvo record
WRAPPER


cat > "$BIN_DIR/process" <<WRAPPER
#!/usr/bin/env bash

cd "$PROJECT_DIR"

"$VENV_DIR/bin/python" -m celvo process
WRAPPER


chmod +x "$BIN_DIR/record"
chmod +x "$BIN_DIR/process"

ok


if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then

    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

fi


step "Verifying installation..."

run "$VENV_DIR/bin/python" -c "import celvo"

ok


echo
echo "────────────────────────────────"
echo
echo "✓ Celvo installed successfully."
echo
echo "Commands:"
echo
echo "  record"
echo "  process"
echo
echo "User files:"
echo
echo "  ~/Documents/celvo/audio"
echo "  ~/Documents/celvo/transcription"
echo
echo "Installation log:"
echo "  $LOG_FILE"
echo
echo "Restart your terminal if commands are not found."
