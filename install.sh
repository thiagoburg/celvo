#!/usr/bin/env bash

set -e

REPO="https://github.com/thiagoburg/celvo.git"
DIR="$HOME/.local/share/celvo"
VERSION="1.1.2"


echo
echo "==> Installing Celvo v$VERSION"
echo


if ! command -v git >/dev/null 2>&1; then

    echo "==> Installing dependencies..."

    if command -v apt >/dev/null 2>&1; then

        sudo apt update >/dev/null
        sudo apt install -y git >/dev/null

    elif command -v dnf >/dev/null 2>&1; then

        sudo dnf install -y git >/dev/null

    elif command -v pacman >/dev/null 2>&1; then

        sudo pacman -Sy --noconfirm git >/dev/null

    elif command -v zypper >/dev/null 2>&1; then

        sudo zypper install -y git >/dev/null

    else

        echo "Unsupported Linux distribution."
        exit 1

    fi

fi


if [ ! -d "$DIR" ]; then

    echo "==> Downloading Celvo..."

    mkdir -p "$HOME/.local/share"

    git clone -q "$REPO" "$DIR"

    echo "✓ Done"

else

    cd "$DIR"
    git pull -q

fi


cd "$DIR"

chmod +x setup.sh

./setup.sh
