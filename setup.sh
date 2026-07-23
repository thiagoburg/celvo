#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"

INSTALLER_VERSION="1.1.0"

echo "Installing Celvo v$INSTALLER_VERSION"
echo

if [ "$EUID" -eq 0 ]; then
    echo "Error: Do not run this installer as root."
    exit 1
fi

if ! command -v sudo >/dev/null 2>&1; then
    echo "Error: sudo is required."
    exit 1
fi


echo "Detecting system..."

if command -v dnf >/dev/null 2>&1; then

    echo "Fedora/RHEL based system detected"

    sudo dnf install -y \
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

    echo "Debian/Ubuntu based system detected"

    sudo apt update

    sudo apt install -y \
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


elif command -v pacman >/dev/null 2>&1; then

    echo "Arch based system detected"

    sudo pacman -Sy --noconfirm \
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


elif command -v zypper >/dev/null 2>&1; then

    echo "openSUSE based system detected"

    sudo zypper install -y \
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


echo
echo "Checking Python..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: Python 3 was not installed."
    exit 1
fi


echo
echo "Creating Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi


source "$VENV_DIR/bin/activate"


echo
echo "Installing Python dependencies..."

python -m pip install --upgrade pip

pip install -r "$PROJECT_DIR/requirements.txt"


echo
echo "Installing Celvo package..."

$VENV_DIR/bin/pip install .

echo "Installing whisper.cpp..."


if [ ! -d "$PROJECT_DIR/whisper.cpp" ]; then

    git clone \
    https://github.com/ggml-org/whisper.cpp.git \
    "$PROJECT_DIR/whisper.cpp"

fi


cd "$PROJECT_DIR/whisper.cpp"


if [ ! -d "build" ]; then

    cmake -B build

fi


cmake --build build -j"$(nproc)"


echo
echo "Downloading Whisper model..."


MODEL_DIR="$PROJECT_DIR/models"
MODEL="$MODEL_DIR/ggml-large-v3-q5_0.bin"


mkdir -p "$MODEL_DIR"


if [ ! -f "$MODEL" ]; then

    echo "Downloading large-v3 Whisper model (~1GB)"

    wget \
    -O "$MODEL" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin

else

    echo "Whisper model already exists"

fi


echo
echo "Creating commands..."


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


if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then

    echo
    echo "Adding ~/.local/bin to PATH"

    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

fi


echo
echo "Checking installation..."


"$VENV_DIR/bin/python" -c "import celvo"


echo
echo "Celvo installed successfully."
echo
echo "Commands:"
echo
echo "  record"
echo "  process"
echo
echo "Restart your terminal if commands are not found."
