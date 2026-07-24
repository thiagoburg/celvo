#!/usr/bin/env bash

set -e

REPO="https://github.com/thiagoburg/celvo.git"
DIR="$HOME/.local/share/celvo"
VERSION="1.1.2"

echo
echo "==> Installing Celvo v$VERSION"
echo

if [ ! -d "$DIR" ]; then

    echo "==> Downloading Celvo..."

    mkdir -p "$HOME/.local/share"

    git clone -q "$REPO" "$DIR"

    echo "✓ Done"

else

    echo "==> Updating Celvo..."

    cd "$DIR"

    git pull -q

    echo "✓ Done"

fi

cd "$DIR"

chmod +x setup.sh

./setup.sh
