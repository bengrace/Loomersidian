#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
MIN_PYTHON_MINOR=9

cd "$REPO_ROOT"

# ---------- find a suitable python (prefer highest available) ----------
find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    bin=$(command -v "$candidate" 2>/dev/null || true)
    if [ -n "$bin" ]; then
      minor=$("$bin" -c "import sys; print(sys.version_info.minor)")
      if [ "$minor" -ge "$MIN_PYTHON_MINOR" ]; then
        echo "$bin"
        return
      fi
    fi
  done
  echo ""
}

PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
  echo "ERROR: No Python >= 3.$MIN_PYTHON_MINOR found on PATH."
  echo "Install Python 3.9+ and re-run this script."
  exit 1
fi
echo "Using Python: $PYTHON ($("$PYTHON" --version))"

# ---------- check / recreate venv ----------
need_recreate=false

if [ ! -d "$VENV_DIR" ]; then
  need_recreate=true
  echo "No .venv found — creating one."
elif ! "$VENV_DIR/bin/python" --version &>/dev/null; then
  need_recreate=true
  echo ".venv/bin/python is broken (stale path?) — recreating."
elif ! "$VENV_DIR/bin/python" -c "import sys; assert sys.version_info >= (3,$MIN_PYTHON_MINOR)" &>/dev/null; then
  need_recreate=true
  echo ".venv Python is too old — recreating."
fi

if $need_recreate; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv "$VENV_DIR" --clear
fi

# ---------- activate ----------
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------- upgrade pip & install ----------
pip install --upgrade pip --quiet
pip install -e . --quiet
echo "Dependencies installed."

# ---------- verify CLI ----------
if loomersidian --help &>/dev/null; then
  echo "loomersidian CLI: OK"
else
  echo "ERROR: loomersidian CLI failed after install."
  exit 1
fi

# ---------- verify ffmpeg (and persist PATH fix into the venv) ----------
# On macOS, Homebrew installs ffmpeg to /opt/homebrew/bin (Apple Silicon) or
# /usr/local/bin (Intel). These are often missing from non-interactive shells,
# which causes frame extraction to fail silently. We probe known locations and,
# if needed, append a PATH prepend to the venv's activate script so every future
# `source .venv/bin/activate` inherits the fix.
ffmpeg_dir=""
if ! command -v ffmpeg &>/dev/null; then
  for candidate in /opt/homebrew/bin /usr/local/bin; do
    if [ -x "$candidate/ffmpeg" ]; then
      ffmpeg_dir="$candidate"
      export PATH="$ffmpeg_dir:$PATH"
      break
    fi
  done
fi

if command -v ffmpeg &>/dev/null; then
  echo "ffmpeg: OK ($(ffmpeg -version 2>&1 | head -1))"
  if [ -n "$ffmpeg_dir" ]; then
    activate_file="$VENV_DIR/bin/activate"
    marker="# loomersidian: ensure ffmpeg on PATH"
    if ! grep -qF "$marker" "$activate_file" 2>/dev/null; then
      {
        echo ""
        echo "$marker"
        echo "case \":\$PATH:\" in"
        echo "  *\":$ffmpeg_dir:\"*) ;;"
        echo "  *) export PATH=\"$ffmpeg_dir:\$PATH\" ;;"
        echo "esac"
      } >> "$activate_file"
      echo "Patched $activate_file to prepend $ffmpeg_dir to PATH on activation."
    fi
  fi
else
  echo "WARNING: ffmpeg not found. Frame extraction will fail."
  echo "  macOS:  brew install ffmpeg"
  echo "  Linux:  sudo apt-get install ffmpeg"
fi

echo ""
echo "Environment ready. Activate with:  source .venv/bin/activate"
