#!/usr/bin/env bash

set -e

REPO="https://github.com/thiagoburg/celvo.git"
DIR="$HOME/.local/share/celvo"

echo "Installing Celvo..."
echo


if [ ! -d "$DIR" ]; then

    echo "Downloading Celvo..."

    mkdir -p "$HOME/.local/share"

    git clone "$REPO" "$DIR"

else

    echo "Celvo repository already exists"

    cd "$DIR"

    git pull

fi


cd "$DIR"


chmod +x setup.sh


./setup.sh
