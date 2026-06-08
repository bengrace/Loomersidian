# Agent Instructions

## Environment Setup (run first)

Before running any `loomersidian` command, verify the environment works **and that `ffmpeg` is reachable**:

```bash
source .venv/bin/activate && loomersidian --help && command -v ffmpeg
```

All three must succeed. If any fail, run the bootstrap:

```bash
bash scripts/bootstrap.sh
source .venv/bin/activate
```

The bootstrap script detects a working Python (>=3.9), recreates `.venv` if it is broken or missing, installs dependencies, and checks for `ffmpeg`.

### ffmpeg PATH gotcha (macOS, non-interactive shells)

On macOS, Homebrew installs `ffmpeg` to `/opt/homebrew/bin/ffmpeg`, which is **not always on `PATH`** in non-interactive shells (this is the env that scripts and agents run in). If `which ffmpeg` returns nothing but `/opt/homebrew/bin/ffmpeg` exists, prepend it for the session **before** running any processing command:

```bash
export PATH="/opt/homebrew/bin:$PATH"
```

The processing scripts (`process-inbox.sh`) inherit this for the rest of the run.

## Primary Workflow

Process video + transcript pairs from `inbox/` into LLM-ready timelines in `output/`.

### Process all inbox items at once

```bash
bash scripts/process-inbox.sh
```

This iterates every subfolder in `inbox/`, finds the `.mp4` + `.srt`/`.txt` pair, skips folders already processed (output slug exists), and runs `loomersidian generate` for each.

### Generate a single timeline

```bash
source .venv/bin/activate
loomersidian generate -i "inbox/<folder>/<video>.mp4" -t "inbox/<folder>/<transcript>.srt" -o ./output --verbose
```

#### Tuning frame cadence (optional)

The timeline cadence is **driven by the transcript**, not by a fixed time interval: `loomersidian` merges adjacent transcript entries into 5–15s blocks (defaults) and extracts one frame per block at its midpoint. Talk fast → more blocks. Pause → fewer blocks but the same screen may repeat across them.

Two flags let you tune the block size up-front (use these *with* dedupe, not instead of it):

```bash
# Coarser blocks → fewer frames overall
loomersidian generate -i video.mp4 -t video.srt -o ./output --min-block 10 --max-block 30

# Generate AND dedupe in one shot (recommended for talky videos)
loomersidian generate -i video.mp4 -t video.srt -o ./output --dedupe

# Same, with a stricter dedupe threshold
loomersidian generate -i video.mp4 -t video.srt -o ./output --dedupe --dedupe-threshold 3
```

### Add a frame at a specific timestamp (zoom-in)

```bash
loomersidian enrich --video "inbox/<folder>/<video>.mp4" --timeline "output/<slug>/timeline.md" --timestamp 02:45
```

### Dedupe duplicate frames

When the presenter pauses on a screen, frame extraction yields a run of nearly-identical PNGs. The optional `dedupe` command collapses those runs in place using a perceptual hash (pHash) on adjacent frames, keeps only the first frame in each run, removes the `![[…]]` image link from the duplicate blocks (timestamp + transcript stay), and **moves the duplicate PNGs to `attachments/archive/`** so you can review and bulk-delete or restore.

```bash
# Preview without changing anything
loomersidian dedupe --timeline output/<slug>/timeline.md --dry-run

# Apply (default Hamming threshold = 5)
loomersidian dedupe --timeline output/<slug>/timeline.md

# Stricter (lower threshold = require closer match to call duplicate)
loomersidian dedupe --timeline output/<slug>/timeline.md --threshold 3

# Undo: move PNGs from attachments/archive/ back and re-link them
loomersidian dedupe --timeline output/<slug>/timeline.md --restore
```

Safety notes:

- Originals are never deleted — they live in `attachments/archive/` until you remove them manually.
- `--dry-run` and `--restore` are mutually exclusive; both are read-only by default for the timeline if you cancel.
- Dedupe is **opt-in**. The default `generate` flow does not dedupe automatically.
- Re-running `dedupe` on an already-deduped timeline is a no-op (idempotent).

## Proactive Inbox Processing

When the user asks to "process the inbox", "process new videos", "process this Loom", or names a single inbox folder:

1. **Verify env**: `source .venv/bin/activate && loomersidian --help && command -v ffmpeg`.
   - If `ffmpeg` is missing but `/opt/homebrew/bin/ffmpeg` exists → `export PATH="/opt/homebrew/bin:$PATH"`.
   - If `loomersidian` is missing → `bash scripts/bootstrap.sh && source .venv/bin/activate`.
2. **List inbox** (`ls inbox/`) to confirm the new folder(s) are present.
3. **Run** `bash scripts/process-inbox.sh` to process everything in one shot.
4. **Report** processed / skipped / failed counts and link to `output/<slug>/timeline.md` for each new item.

Do **not** wait for the user to name each folder individually — even when they mention only one new folder, just run the batch script. It auto-discovers, deduplicates, and reports.

### Recovering from a failed run (stale empty output stub)

If `process-inbox.sh` reports `SKIP: '<folder>' — already processed` but the user expected new work, a previous run likely failed mid-frame-extraction and left an **empty `output/<slug>/`** stub (just an empty `attachments/` subdir, no `timeline.md`). The script's "already processed" check is dir-existence based, so the stub blocks re-runs.

To recover:

1. `ls output/<slug>/` — if there's no `timeline.md`, it's a stub.
2. Remove it: `rm -rf output/<slug>` (run from a normal terminal; agents may need to ask the user to do this if their tooling restricts directory deletion).
3. Re-run `bash scripts/process-inbox.sh`.

The most common cause of this stub is `ffmpeg` not being on `PATH` (see env setup above).

## Folder structure

- `inbox/` — Drop video + transcript pairs here (gitignored)
- `output/` — Generated timelines with `timeline.md` + `attachments/` (gitignored)
- `scripts/` — Bootstrap and batch-processing helpers

## Supported transcript formats

- **Loom native** `.txt` — timestamp + text blocks
- **SRT** `.srt` — auto-detected

## Notes

- Both `inbox/` and `output/` are gitignored. Use `--verbose` to confirm processing.
- The `enrich` command inserts a single frame into an existing `timeline.md` at the given timestamp.
