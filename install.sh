#!/usr/bin/env bash

set -euo pipefail

ARCHIVE_URL="https://codeload.github.com/thiagoburg/celvo/tar.gz/refs/heads/main"
DIR="$HOME/.local/share/celvo"
VERSION="1.2.1"

echo
echo "==> Installing Celvo v$VERSION"
echo

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

rm -rf "$DIR"
mkdir -p "$HOME/.local/share"

curl -fsSL "$ARCHIVE_URL" | tar -xzf - -C "$tmpdir"
mv "$tmpdir/celvo-main" "$DIR"

cd "$DIR"
chmod +x setup.sh
./setup.sh
