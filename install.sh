#!/usr/bin/env bash

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
BIN_DIR="$HOME/.local/bin"

echo "Installing celvo..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found"
    exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Error: ffmpeg not found"
    echo "Install ffmpeg using your distribution package manager"
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "Error: ollama not found"
    exit 1
fi

if ! ollama list | grep -q "llama3.2:3b"; then
    echo "Error: llama3.2:3b model not found"
    echo "Run: ollama pull llama3.2:3b"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

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

echo ""
echo "celvo installed successfully"
echo ""
echo "Commands:"
echo "  record"
echo "  process"
