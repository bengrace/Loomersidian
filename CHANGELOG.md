# Changelog

All notable changes to Loomersidian are documented here.

---

## [0.2.0] - 2026-05-05

### Added

**Frame deduplication** — collapse runs of visually-identical adjacent frames using a perceptual hash. When the presenter pauses on a screen, the timeline ends up with one frame per unique screen instead of one per transcript block.

- New `loomersidian dedupe` subcommand with `--threshold`, `--dry-run`, and `--restore` flags. Archives duplicate PNGs to `attachments/archive/` (never deleted) so they can be reviewed and either bulk-deleted or restored.
- New `--dedupe` and `--dedupe-threshold` flags on `loomersidian generate` to run dedupe automatically at the end of generation.
- Idempotent: re-running dedupe on an already-deduped timeline is a no-op.
- Reversible: `--restore` round-trips back to the original timeline byte-for-byte.

**Tunable frame cadence** — control how aggressively the transcript is merged into blocks before frame extraction.

- New `--min-block` and `--max-block` flags on `loomersidian generate` (defaults: 5 and 15 seconds). Larger values produce fewer, longer blocks and fewer extracted frames.

**Batch inbox processing** — `scripts/process-inbox.sh` iterates every subfolder in `inbox/`, finds the video + transcript pair, skips already-processed items, and runs `loomersidian generate` for each.

**Bootstrap script hardening**

- `scripts/bootstrap.sh` now detects a working Python (>=3.9), recreates `.venv` if broken or missing, and patches the venv's `activate` script to prepend Homebrew's `/opt/homebrew/bin` to `PATH` so `ffmpeg` is reachable in non-interactive shells (a common macOS gotcha).
- `scripts/process-inbox.sh` self-heals from failed prior runs by removing empty output stubs (which would otherwise be skipped as "already processed").

**Tooling**

- Added `ruff` as a dev dependency, configured a conservative high-signal lint rule set in `pyproject.toml`, and cleaned up the codebase to pass it.

### Changed

- `loomersidian/timeline.py:normalize_timeline` now accepts optional `min_block_duration` / `max_block_duration` overrides while preserving the previous defaults.
- `loomersidian/generator.py:parse_timeline_document` now tolerates blocks without an image link (the on-disk shape produced by `dedupe`). `render_block`, `generate_timeline_document`, and `update_timeline_document` accept `Optional[Path]` accordingly.

### Fixed

- Round-trip restore from `attachments/archive/` correctly handles frames past 1 minute. Frame filenames are `frame_<MMSS>.png` (zero-padded MM concatenated with SS), not `frame_<seconds>.png`; an integer-parsing approach silently failed for blocks past 60 s.

### Removed

- Stale unused imports in `loomersidian/cli.py` and `loomersidian/enrichment.py`.

---

## [0.1.0] - 2025-01-13

### Added

**Core Pipeline**
- Transcript parsing with auto-detection of SRT and Loom native formats
- Timeline normalization into 5-15 second blocks
- Frame extraction at block midpoints via ffmpeg
- Markdown generation with Obsidian-compatible `![[attachments/...]]` embeds

**CLI Commands**
- `loomersidian generate` - Create timeline from video + transcript
- `loomersidian enrich` - Add frames to existing timeline at specific timestamps
- `--zoom-range` flag for finer-grained frame extraction in a time range

**Output Format**
- Slugified output folders (lowercase, hyphens, no special chars)
- `timeline.md` with timestamp headers, embedded images, quoted transcript
- `attachments/` subfolder for frame PNGs

### Known Limitations
- Transcript extending beyond video duration may cause final frame extraction to fail silently
- Screenshots include browser chrome from Loom recordings (can be addressed via prompting)
