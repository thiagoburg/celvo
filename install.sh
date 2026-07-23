#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"

echo "Installing Celvo..."

echo ""
echo "Checking system dependencies..."

if command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y \
        python3 \
        python3-pip \
        python3-devel \
        git \
        wget \
        cmake \
        gcc-c++ \
        make

elif command -v apt >/dev/null 2>&1; then
    sudo apt update

    sudo apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        git \
        wget \
        cmake \
        g++ \
        make

else
    echo "Unsupported Linux distribution"
    exit 1
fi


echo ""
echo "Setting up Python environment..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"


echo ""
echo "Installing whisper.cpp..."

if [ ! -d "$PROJECT_DIR/whisper.cpp" ]; then
    git clone https://github.com/ggml-org/whisper.cpp.git \
        "$PROJECT_DIR/whisper.cpp"
fi

cd "$PROJECT_DIR/whisper.cpp"

cmake -B build
cmake --build build -j


echo ""
echo "Downloading Whisper model..."

mkdir -p "$PROJECT_DIR/models"

MODEL="$PROJECT_DIR/models/ggml-large-v3-q5_0.bin"

if [ ! -f "$MODEL" ]; then
    wget -O "$MODEL" \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-q5_0.bin
fi


echo ""
echo "Creating commands..."

mkdir -p "$BIN_DIR"


cat > "$BIN_DIR/celvo" <<WRAPPER
#!/usr/bin/env bash

cd "$PROJECT_DIR"

case "\$1" in

record)
    "$VENV_DIR/bin/python" -m celvo record
    ;;

process)
    "$VENV_DIR/bin/python" -m celvo process
    ;;

*)
    echo "Usage:"
    echo "  celvo record"
    echo "  celvo process"
    ;;

esac
WRAPPER


chmod +x "$BIN_DIR/celvo"


echo ""
echo "Celvo installed successfully"
echo ""
echo "Commands:"
echo "  celvo record"
echo "  celvo process"
