"""Frame deduplication for Loomersidian timelines.

When a presenter pauses on a screen, frame extraction (which samples once per
block) yields a run of nearly-identical PNGs. This module identifies such runs
using a perceptual hash (pHash), keeps only the first frame in each run, and
moves the rest to ``attachments/archive/`` so they can be reviewed and either
deleted or restored.

Restoration is symmetric: ``restore_dedupe`` walks ``attachments/archive/``,
moves PNGs back into ``attachments/``, and re-inserts the corresponding
``![[attachments/…]]`` lines into the timeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loomersidian.generator import (
    parse_timeline_document,
    update_timeline_document,
)
from loomersidian.timeline import TimeBlock

# Default Hamming-distance threshold for pHash equality. With pHash's 64-bit
# default hash size, ~5 bits of difference reliably catches "same screen with
# cursor moved / blink / scroll-bar twitch" while leaving real UI changes
# (modal opened, panel switched) above the threshold.
DEFAULT_THRESHOLD = 5


@dataclass
class DedupeReport:
    """Result of an ``apply_dedupe`` (or ``--dry-run``) pass."""

    timeline_path: Path
    archive_dir: Path
    threshold: int
    total_blocks: int
    blocks_with_images_before: int
    kept: int
    archived: List[Path] = field(default_factory=list)
    dry_run: bool = False

    @property
    def removed_image_lines(self) -> int:
        return len(self.archived)

    def format(self) -> str:
        prefix = "Dedupe (dry-run)" if self.dry_run else "Dedupe summary"
        rel_archive = self.archive_dir
        try:
            rel_archive = self.archive_dir.relative_to(Path.cwd())
        except ValueError:
            pass
        lines = [
            prefix,
            f"  Threshold: {self.threshold} (Hamming distance)",
            f"  Kept:      {self.kept} frames",
            f"  Archived:  {self.removed_image_lines} frames -> {rel_archive}/",
            f"  Timeline:  {self.total_blocks} blocks, {self.removed_image_lines} image lines removed",
        ]
        if not self.dry_run and self.removed_image_lines:
            lines.append(
                f"  Undo:      loomersidian dedupe --timeline {self.timeline_path} --restore"
            )
        return "\n".join(lines)


@dataclass
class RestoreReport:
    """Result of a ``restore_dedupe`` pass."""

    timeline_path: Path
    archive_dir: Path
    restored: List[Path] = field(default_factory=list)
    skipped_no_block: List[Path] = field(default_factory=list)

    def format(self) -> str:
        lines = [
            "Restore summary",
            f"  Restored: {len(self.restored)} frames -> {self.archive_dir.parent}/",
            f"  Timeline: image links re-inserted into {self.timeline_path}",
        ]
        if self.skipped_no_block:
            lines.append(
                f"  Skipped:  {len(self.skipped_no_block)} archived frames had no matching block in the timeline"
            )
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #


def compute_phash(image_path: Path):
    """Return the perceptual hash of an image.

    Imports are local so importing this module does not pay the Pillow /
    numpy / scipy cost unless dedupe is actually invoked.
    """

    import imagehash  # type: ignore[import-not-found]
    from PIL import Image  # type: ignore[import-not-found]

    with Image.open(image_path) as img:
        return imagehash.phash(img)


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #


def find_duplicate_runs(
    blocks_with_frames: List[Tuple[TimeBlock, Optional[Path]]],
    threshold: int = DEFAULT_THRESHOLD,
) -> List[Tuple[int, List[int]]]:
    """Identify runs of visually-identical adjacent frames.

    Each frame is compared against the *kept* frame of the current run, not
    the raw previous frame. This means brief one-frame anomalies (cursor
    blink, scroll-bar appearance) do not reset the dedupe streak.

    Args:
        blocks_with_frames: As returned by ``parse_timeline_document``. Blocks
            whose frame_path is ``None`` (already deduped) or missing on disk
            are treated as run-breakers.
        threshold: Maximum Hamming distance between two pHashes for the
            frames to be considered "the same". Defaults to ``DEFAULT_THRESHOLD``.

    Returns:
        List of ``(kept_index, [duplicate_indices])`` tuples, one per run that
        has at least one duplicate. ``kept_index`` and the duplicate indices
        are positions in ``blocks_with_frames``.
    """

    runs: List[Tuple[int, List[int]]] = []
    current_kept_idx: Optional[int] = None
    current_kept_hash = None
    current_duplicates: List[int] = []

    def _close_run() -> None:
        nonlocal current_kept_idx, current_kept_hash, current_duplicates
        if current_kept_idx is not None and current_duplicates:
            runs.append((current_kept_idx, current_duplicates))
        current_kept_idx = None
        current_kept_hash = None
        current_duplicates = []

    for idx, (_, frame_path) in enumerate(blocks_with_frames):
        if frame_path is None or not frame_path.exists():
            _close_run()
            continue

        try:
            this_hash = compute_phash(frame_path)
        except Exception:
            # Unreadable frame — break the run, do not group it.
            _close_run()
            continue

        if current_kept_hash is None:
            current_kept_idx = idx
            current_kept_hash = this_hash
            current_duplicates = []
            continue

        distance = this_hash - current_kept_hash
        if distance <= threshold:
            current_duplicates.append(idx)
        else:
            _close_run()
            current_kept_idx = idx
            current_kept_hash = this_hash
            current_duplicates = []

    _close_run()
    return runs


# --------------------------------------------------------------------------- #
# Apply / restore
# --------------------------------------------------------------------------- #


def apply_dedupe(
    timeline_path: Path,
    threshold: int = DEFAULT_THRESHOLD,
    dry_run: bool = False,
) -> DedupeReport:
    """Run the full dedupe pass against an existing timeline.

    Args:
        timeline_path: Path to the ``timeline.md`` to operate on.
        threshold: pHash Hamming distance threshold (lower = stricter).
        dry_run: When True, compute the report but make no filesystem changes.

    Returns:
        A :class:`DedupeReport` summarizing the run.
    """

    title, blocks_with_frames = parse_timeline_document(timeline_path)
    archive_dir = timeline_path.parent / "attachments" / "archive"

    blocks_with_images_before = sum(1 for _, f in blocks_with_frames if f is not None)
    runs = find_duplicate_runs(blocks_with_frames, threshold=threshold)
    duplicate_indices = {idx for _, dups in runs for idx in dups}

    archived_paths: List[Path] = []
    new_pairs: List[Tuple[TimeBlock, Optional[Path]]] = []

    if not dry_run and duplicate_indices:
        archive_dir.mkdir(parents=True, exist_ok=True)

    for idx, (block, frame_path) in enumerate(blocks_with_frames):
        if idx in duplicate_indices and frame_path is not None:
            target = archive_dir / frame_path.name
            archived_paths.append(target)
            if not dry_run and frame_path.exists():
                # Move the PNG. If the destination already exists from a prior
                # partial run, overwrite it — the source is the source of truth.
                if target.exists():
                    target.unlink()
                frame_path.rename(target)
            new_pairs.append((block, None))
        else:
            new_pairs.append((block, frame_path))

    if not dry_run and duplicate_indices:
        blocks = [b for b, _ in new_pairs]
        frame_map: Dict[TimeBlock, Optional[Path]] = dict(new_pairs)
        update_timeline_document(timeline_path, blocks, frame_map, title)

    kept = blocks_with_images_before - len(archived_paths)
    return DedupeReport(
        timeline_path=timeline_path,
        archive_dir=archive_dir,
        threshold=threshold,
        total_blocks=len(blocks_with_frames),
        blocks_with_images_before=blocks_with_images_before,
        kept=kept,
        archived=archived_paths,
        dry_run=dry_run,
    )


def restore_dedupe(timeline_path: Path) -> RestoreReport:
    """Undo a dedupe pass: move archived PNGs back and re-link them.

    For each PNG in ``attachments/archive/`` we look up the block whose
    ``start_seconds`` matches the frame index encoded in the filename
    (``frame_<seconds>.png``), move the PNG back to ``attachments/``, and
    set its frame_path on the block.

    Args:
        timeline_path: Path to the ``timeline.md`` to restore.

    Returns:
        A :class:`RestoreReport` summarizing the run.
    """

    title, blocks_with_frames = parse_timeline_document(timeline_path)
    attachments_dir = timeline_path.parent / "attachments"
    archive_dir = attachments_dir / "archive"

    if not archive_dir.exists():
        return RestoreReport(timeline_path=timeline_path, archive_dir=archive_dir)

    # Build an index from the expected frame filename to the block's position.
    # Frame filenames are ``frame_<midpoint_timestamp>.png`` where
    # midpoint_timestamp is the block's midpoint expressed as ``MMSS`` (see
    # TimeBlock.midpoint_timestamp). We use the literal string match rather
    # than parsing back to an integer because ``MMSS`` is not the same as the
    # midpoint in seconds for blocks past 1 minute.
    block_index_by_filename: Dict[str, int] = {}
    for idx, (block, _) in enumerate(blocks_with_frames):
        block_index_by_filename.setdefault(f"frame_{block.midpoint_timestamp}.png", idx)

    restored: List[Path] = []
    skipped: List[Path] = []
    new_pairs: List[Tuple[TimeBlock, Optional[Path]]] = [
        (b, f) for b, f in blocks_with_frames
    ]

    for archived_png in sorted(archive_dir.glob("frame_*.png")):
        block_idx = block_index_by_filename.get(archived_png.name)
        if block_idx is None:
            skipped.append(archived_png)
            continue

        target = attachments_dir / archived_png.name
        if target.exists():
            # Live frame already present (manual edit?) — drop the archived copy
            # rather than overwrite the user's work.
            archived_png.unlink()
        else:
            archived_png.rename(target)
        new_pairs[block_idx] = (new_pairs[block_idx][0], target)
        restored.append(target)

    blocks = [b for b, _ in new_pairs]
    frame_map: Dict[TimeBlock, Optional[Path]] = dict(new_pairs)
    update_timeline_document(timeline_path, blocks, frame_map, title)

    # Best-effort: remove the archive dir if we emptied it.
    try:
        if not any(archive_dir.iterdir()):
            archive_dir.rmdir()
    except OSError:
        pass

    return RestoreReport(
        timeline_path=timeline_path,
        archive_dir=archive_dir,
        restored=restored,
        skipped_no_block=skipped,
    )
