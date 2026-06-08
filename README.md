# Loomersidian

> Turn a Loom recording into an LLM-ready Obsidian Markdown timeline — one frame per unique screen, every spoken word preserved.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](#requirements)
[![Tests: 104 passing](https://img.shields.io/badge/tests-104%20passing-brightgreen.svg)](#development)
[![Status: personal project](https://img.shields.io/badge/status-personal%20project-lightgrey.svg)](#issues-and-feedback)

> **Status**: this is a personal project I built for my own workflow and decided to share in case it's useful. It works for me; it may or may not work for you. See [Issues and feedback](#issues-and-feedback) below for what to expect in terms of support.

Loomersidian takes a Loom video + its transcript and produces a single `timeline.md` document where each spoken passage is paired with the screenshot that was on screen at the moment it was said. The output drops straight into [Obsidian](https://obsidian.md) and is also clean enough to paste into ChatGPT, Claude, or any other LLM as context for "what was actually shown in this demo".

```
output/<your-video>/
├── timeline.md              ← human-readable + LLM-friendly
└── attachments/
    ├── frame_0006.png       ← one image per unique screen
    ├── frame_0042.png
    └── archive/             ← duplicate frames, kept for review
```

---

## Why this exists

Loom gives you a video and a transcript, but neither one is great input for an LLM that wasn't there. Video is too big and opaque. Transcript loses all the visual context — half of "click this thing, see that thing happen" is the *thing*. Loomersidian stitches them back together: every passage of speech anchored to the screen you were showing.

It's optimised for **product demos, design walkthroughs, and tutorials** — videos where you spend time talking through a screen, then move to the next screen. For talking-head footage with no slides, it'll still work, but you'll get a frame per chunk of speech regardless.

## Features

- **Transcript-driven cadence.** Frames are placed at the midpoint of speech-aligned blocks (5–15 seconds by default), not on a fixed time interval. Talk fast → more granular timeline. Pause → fewer blocks.
- **Auto-detects transcript format.** Loom native `.txt` (timestamp + text) and `.srt` are both supported.
- **Obsidian-friendly output.** Uses `![[attachments/...]]` embeds so the timeline renders inline when opened as an Obsidian vault.
- **Optional frame deduplication.** Pause on a screen for 30 seconds and you'd normally get six near-identical PNGs. The `dedupe` pass collapses those runs using a perceptual hash; duplicates are moved to `attachments/archive/` for review (never deleted).
- **Optional cadence tuning.** Pass `--min-block` / `--max-block` to make blocks longer (fewer frames) or shorter (more granular) before generation.
- **Optional zoom-in enrichment.** After generation, add an extra frame at any timestamp with `loomersidian enrich --timestamp 02:45`.
- **Reversible everything.** Dedupe has `--restore`, frame extraction is idempotent, the original PNGs are always recoverable.

## Demo

Drop a Loom MP4 + its SRT into `inbox/<your-folder>/` and run:

```bash
bash scripts/process-inbox.sh
```

Output appears at `output/<slug>/timeline.md` with one frame per unique screen and the full transcript in context.

## Requirements

- **Python 3.9 or newer**
- **`ffmpeg`** (the binary, not the Python package — both will be installed)
  - macOS: `brew install ffmpeg`
  - Debian/Ubuntu: `sudo apt-get install ffmpeg`
  - Windows: [download from ffmpeg.org](https://ffmpeg.org/download.html) and add it to `PATH`

## Install

Clone, create a virtualenv, install:

```bash
git clone https://github.com/<your-username>/loomersidian.git
cd loomersidian
bash scripts/bootstrap.sh
source .venv/bin/activate
loomersidian --help
```

`bootstrap.sh` finds a working Python ≥3.9, builds a `.venv`, installs the package in editable mode, and verifies `ffmpeg` is reachable. It also patches the venv's activation script on macOS so Homebrew's `/opt/homebrew/bin/ffmpeg` is on `PATH` in non-interactive shells.

## Quickstart

### 1. Drop a recording into `inbox/`

```
inbox/
└── my-design-walkthrough/
    ├── recording.mp4
    └── recording.srt           # or recording.txt for Loom native format
```

### 2. Generate a timeline

Process every folder in `inbox/`:

```bash
bash scripts/process-inbox.sh
```

…or generate a single one:

```bash
loomersidian generate \
  -i "inbox/my-design-walkthrough/recording.mp4" \
  -t "inbox/my-design-walkthrough/recording.srt" \
  -o ./output \
  --verbose
```

### 3. (Optional) Dedupe runs of identical frames

If you paused on screens, collapse the duplicates:

```bash
loomersidian dedupe --timeline output/my-design-walkthrough/timeline.md
```

…or do it in one shot at generation time:

```bash
loomersidian generate ... --dedupe
```

### 4. (Optional) Add a frame at a specific moment

```bash
loomersidian enrich \
  --video "inbox/my-design-walkthrough/recording.mp4" \
  --timeline output/my-design-walkthrough/timeline.md \
  --timestamp 02:45
```

## CLI reference

### `loomersidian generate`

Build a timeline from a video + transcript pair.

| Flag | Default | Description |
|---|---|---|
| `-i`, `--input` | — | Path to the source `.mp4` (required) |
| `-t`, `--transcript` | — | Path to the `.srt` or Loom `.txt` transcript (required) |
| `-o`, `--output` | `./output` | Output root; results land in `<output>/<slug>/` |
| `--min-block` | `5` | Minimum target block duration in seconds — bigger = fewer frames |
| `--max-block` | `15` | Maximum target block duration in seconds — bigger = fewer frames |
| `--dedupe` | off | After generation, collapse runs of visually-identical frames |
| `--dedupe-threshold` | `5` | pHash Hamming distance threshold for `--dedupe` (lower = stricter) |
| `--zoom-range` | — | `START-END` timestamp range to add finer frames within |
| `-v`, `--verbose` | off | Verbose progress output |

### `loomersidian dedupe`

Collapse runs of visually-identical adjacent frames in an existing timeline.

| Flag | Default | Description |
|---|---|---|
| `--timeline` | — | Path to the existing `timeline.md` (required) |
| `--threshold` | `5` | pHash Hamming distance threshold (lower = stricter) |
| `--dry-run` | off | Report what would change without modifying any files |
| `--restore` | off | Move PNGs from `attachments/archive/` back and re-link them |
| `-v`, `--verbose` | off | Verbose progress output |

Originals are never deleted — duplicates live in `attachments/archive/` until you remove them. `--restore` round-trips the timeline back to its pre-dedupe state byte-for-byte.

### `loomersidian enrich`

Insert a single frame at a specific timestamp into an existing timeline.

| Flag | Default | Description |
|---|---|---|
| `--video` | — | Path to the source `.mp4` (required) |
| `--timeline` | — | Path to the existing `timeline.md` (required) |
| `--timestamp` | — | `MM:SS` or `HH:MM:SS` timestamp to extract (required) |
| `-v`, `--verbose` | off | Verbose progress output |

## How it works

1. **Parse** the transcript into time-coded entries (`.srt` or Loom `.txt`).
2. **Normalise** entries into 5–15 second `TimeBlock`s (configurable). Each block represents one passage of speech.
3. **Extract** one frame per block via `ffmpeg`, taken at the block's midpoint.
4. **Generate** `timeline.md` with `## MM:SS–MM:SS` headers, an `![[attachments/frame_<MMSS>.png]]` embed, and the spoken text as a quoted line.
5. **(Optional) Dedupe** adjacent frames via [`imagehash`](https://github.com/JohannesBuchner/imagehash) perceptual hashes. Duplicates are *moved*, not deleted.

The cadence is **driven by the transcript, not by a fixed time interval**, which is why dedupe is needed: when you stay on a screen for 30 seconds and keep talking, you get six speech-aligned blocks all sampling the same screen. Dedupe turns those six blocks-with-frames into one block-with-frame + five blocks-with-text-only.

## Output schema

```markdown
# <video name>

## 00:00–00:12
![[attachments/frame_0006.png]]
"Welcome — let me walk you through the new connector setup flow."

## 00:12–00:24
![[attachments/frame_0018.png]]
"First we'll click into the connector library and pick a source."

## 00:24–00:36
"…notice the layout stays the same as we paginate through results."
```

A block without an `![[...]]` line means dedupe found this frame to be visually identical to the previous one. The transcript text is always preserved.

## Development

```bash
# Run tests
pytest

# Lint
ruff check .

# Auto-fix lint issues that are safe to fix
ruff check . --fix
```

Tests use synthetic fixtures (no real video required) and run in under 2 seconds.

## Folder structure

```
loomersidian/         ← Python package
├── cli.py            ← argparse entry point (loomersidian generate|dedupe|enrich)
├── transcript.py     ← .srt / Loom .txt parsing
├── timeline.py       ← entry → TimeBlock normalisation
├── frames.py         ← ffmpeg frame extraction
├── generator.py      ← Markdown render + parse
├── enrichment.py     ← --zoom-range / enrich helpers
└── dedupe.py         ← perceptual-hash deduplication
scripts/
├── bootstrap.sh      ← create/repair .venv, install deps, verify ffmpeg
└── process-inbox.sh  ← batch-process every folder under inbox/
tests/                ← pytest suite (104 tests)
inbox/                ← drop video+transcript pairs here (gitignored)
output/               ← generated timelines (gitignored)
```

## Roadmap / non-goals

**Probably coming**
- A `--dedupe` flag on `process-inbox.sh` to enable the bundled flow for batch runs.
- Optional video-level scene-change detection as a second-pass *complement* to dedupe (not a replacement — see below).

**Probably not**
- Replacing transcript-driven cadence with video-driven cadence. Scene detection is brittle (per-recorder, per-app, per-content), and dedupe gives most of the same benefit with none of the fragility.
- A GUI. The output is plain Markdown for a reason.

## Issues and feedback

This is a personal project I built for my own workflow and decided to share in case it's useful to others. Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/<your-username>/loomersidian/issues), but I can't promise turnaround times.

I'm not actively soliciting pull requests. If you want to extend Loomersidian, the [MIT license](LICENSE) lets you fork it freely. If you do open a PR I'll take a look when I can, but I make no promises about merging — please don't sink significant effort into a contribution without checking with me first via an issue.

## License

[MIT](LICENSE) © Ben Grace.

## Acknowledgements

- [`ffmpeg`](https://ffmpeg.org/) does the actual frame extraction.
- [`imagehash`](https://github.com/JohannesBuchner/imagehash) powers the perceptual-hash dedupe.
- [Obsidian](https://obsidian.md) is the home most timelines end up in.
