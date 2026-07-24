#!/usr/bin/env bash

set -e

REPO="https://github.com/thiagoburg/celvo.git"
DIR="$HOME/.local/share/celvo"

VERSION="1.1.2"

echo
echo "==> Installing Celvo v$VERSION"
echo


if [ ! -d "$DIR" ]; then

    mkdir -p "$HOME/.local/share"

    echo "==> Downloading Celvo..."

    git clone -q "$REPO" "$DIR" >/dev/null 2>&1

    echo "✓ Done"

else

    cd "$DIR"

    git pull -q >/dev/null 2>&1

fi


cd "$DIR"


chmod +x setup.sh

./setup.sh
