#!/usr/bin/env bash

set -euo pipefail

ARCHIVE_URL="https://codeload.github.com/thiagoburg/celvo/tar.gz/refs/heads/main"
BASE="$HOME/.local/share"
DIR="$BASE/celvo"

echo
echo "==> Installing Celvo v$VERSION"
echo

mkdir -p "$BASE"
tmpdir="$(mktemp -d "$BASE/.celvo-stage.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

echo "==> Downloading Celvo source"
curl --fail --location --retry 3 --retry-connrefused "$ARCHIVE_URL" | tar -xzf - --strip-components=1 -C "$tmpdir"
test -f "$tmpdir/pyproject.toml" || { echo "Error: downloaded Celvo source is incomplete." >&2; exit 1; }

# Keep the existing model before replacing the application directory.
old_model="$DIR/models/ggml-large-v3.bin"
new_model="${CELVO_MODEL_DIR:-$HOME/Documents/celvo/models}/ggml-large-v3.bin"
if [ -f "$old_model" ] && [ ! -e "$new_model" ]; then
    mkdir -p "$(dirname "$new_model")"
    cp -n "$old_model" "$new_model"
fi

backup=""
if [ -e "$DIR" ]; then
    backup="$BASE/celvo.previous.$(date +%Y%m%d%H%M%S).$$"
    mv "$DIR" "$backup"
fi
if ! mv "$tmpdir" "$DIR"; then
    if [ -n "$backup" ] && [ ! -e "$DIR" ]; then mv "$backup" "$DIR"; fi
    echo "Error: could not stage the replacement installation." >&2
    exit 1
fi
if ! bash "$DIR/setup.sh"; then
    failed="$BASE/celvo.failed.$(date +%Y%m%d%H%M%S).$$"
    mv "$DIR" "$failed" || true
    if [ -n "$backup" ] && [ ! -e "$DIR" ]; then mv "$backup" "$DIR"; fi
    echo "Error: installation verification failed. Previous installation restored; new files retained at $failed." >&2
    exit 1
fi
if [ -n "$backup" ]; then
    echo "Previous installation preserved at $backup"
fi
trap - EXIT
rm -rf "$tmpdir"
