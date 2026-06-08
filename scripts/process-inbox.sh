#!/usr/bin/env bash
#
# Process every video+transcript pair found in inbox/ subfolders.
# Skips folders whose output slug already exists in output/.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INBOX="$REPO_ROOT/inbox"
OUTPUT="$REPO_ROOT/output"

cd "$REPO_ROOT"

# Activate venv (bootstrap first if needed)
if ! source .venv/bin/activate 2>/dev/null || ! command -v loomersidian &>/dev/null; then
  echo "Environment not ready — running bootstrap first..."
  bash "$REPO_ROOT/scripts/bootstrap.sh"
  source .venv/bin/activate
fi

# Ensure ffmpeg is on PATH (Homebrew on Apple Silicon installs to /opt/homebrew/bin
# which is often missing from non-interactive shells). Without this, frame extraction
# fails silently and leaves empty output stubs.
if ! command -v ffmpeg &>/dev/null; then
  for candidate in /opt/homebrew/bin /usr/local/bin; do
    if [ -x "$candidate/ffmpeg" ]; then
      export PATH="$candidate:$PATH"
      echo "Added $candidate to PATH for ffmpeg."
      break
    fi
  done
fi
if ! command -v ffmpeg &>/dev/null; then
  echo "ERROR: ffmpeg not found on PATH. Install with 'brew install ffmpeg' (macOS) or 'apt-get install ffmpeg' (Linux)."
  exit 1
fi

if [ ! -d "$INBOX" ]; then
  echo "No inbox/ directory found. Nothing to process."
  exit 0
fi

processed=0
skipped=0
failed=0

for folder in "$INBOX"/*/; do
  [ -d "$folder" ] || continue
  folder_name=$(basename "$folder")

  # Find the video file (.mp4)
  video=$(find "$folder" -maxdepth 1 -iname '*.mp4' -print -quit 2>/dev/null || true)
  if [ -z "$video" ]; then
    echo "SKIP: '$folder_name' — no .mp4 found"
    skipped=$((skipped + 1))
    continue
  fi

  # Find the transcript (.srt first, then .txt)
  transcript=$(find "$folder" -maxdepth 1 \( -iname '*.srt' -o -iname '*.txt' \) -print -quit 2>/dev/null || true)
  if [ -z "$transcript" ]; then
    echo "SKIP: '$folder_name' — no .srt or .txt transcript found"
    skipped=$((skipped + 1))
    continue
  fi

  # Compute the output slug the same way the Python code does:
  # lowercase, spaces/underscores → hyphens, strip specials, collapse hyphens
  stem=$(basename "$video" .mp4)
  slug=$(echo "$stem" | tr '[:upper:]' '[:lower:]' | sed 's/[_ ]/-/g; s/[^a-z0-9-]//g; s/-\{2,\}/-/g; s/^-//; s/-$//')

  if [ -d "$OUTPUT/$slug" ]; then
    if [ -f "$OUTPUT/$slug/timeline.md" ]; then
      echo "SKIP: '$folder_name' — already processed (output/$slug/timeline.md exists)"
      skipped=$((skipped + 1))
      continue
    else
      echo "Found stale empty stub at output/$slug — removing and reprocessing."
      rm -rf "$OUTPUT/$slug"
    fi
  fi

  echo "Processing: '$folder_name'..."
  if loomersidian generate -i "$video" -t "$transcript" -o "$OUTPUT" --verbose; then
    processed=$((processed + 1))
  else
    echo "FAIL: '$folder_name'"
    failed=$((failed + 1))
  fi
  echo ""
done

echo "Done. Processed: $processed | Skipped: $skipped | Failed: $failed"
