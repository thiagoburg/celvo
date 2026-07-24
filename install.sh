#!/usr/bin/env bash

set -e

REPO="https://github.com/thiagoburg/celvo.git"
DIR="$HOME/.local/share/celvo"
VERSION="1.1.2"

echo
echo "==> Installing Celvo v$VERSION"
echo

mkdir -p "$HOME/.local/share"

if [ ! -d "$DIR" ]; then
    git clone -q "$REPO" "$DIR"
else
    cd "$DIR"
    git pull -q
fi

cd "$DIR"

chmod +x setup.sh

./setup.sh >/dev/null

echo
echo "✓ Celvo installed successfully."
echo
echo "Commands:"
echo
echo "  record"
echo "  process"
echo
