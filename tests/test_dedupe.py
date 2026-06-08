"""Tests for frame deduplication."""

from pathlib import Path
from typing import List, Tuple

import pytest

PIL = pytest.importorskip("PIL")
imagehash = pytest.importorskip("imagehash")  # noqa: F841 — fail fast if missing

from PIL import Image, ImageDraw  # noqa: E402

from loomersidian.dedupe import (
    DEFAULT_THRESHOLD,
    apply_dedupe,
    find_duplicate_runs,
    restore_dedupe,
)
from loomersidian.generator import (
    generate_timeline_document,
    parse_timeline_document,
)
from loomersidian.timeline import TimeBlock

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_screen(variant: str, jitter: int = 0) -> Image.Image:
    """Generate a synthetic 'screenshot' that pHash will treat as a screen.

    Variants are chosen to be structurally distinct (different geometric
    layouts), because pHash is primarily a structure/luminance hash and is
    nearly invariant to flat color shifts.

    `jitter` shifts content a few pixels to simulate cursor blink / minor
    rendering jitter — small enough to stay below the default pHash threshold.
    """
    img = Image.new("RGB", (256, 256), color="white")
    draw = ImageDraw.Draw(img)

    if variant == "A":
        # Single dark block in upper-left, white below
        draw.rectangle(
            (10 + jitter, 10, 120 + jitter, 120),
            fill="black",
        )
    elif variant == "B":
        # Three vertical stripes
        draw.rectangle((0, 0, 80, 256), fill="black")
        draw.rectangle((90, 0, 170, 256), fill="gray")
        draw.rectangle((180, 0, 256, 256), fill="black")
    elif variant == "C":
        # Diagonal cross
        draw.line((0, 0, 256, 256), fill="black", width=20)
        draw.line((256, 0, 0, 256), fill="black", width=20)
    else:
        raise ValueError(f"unknown variant {variant!r}")
    return img


def _write_png(path: Path, img: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def _build_timeline(
    tmp_path: Path,
    screens: List[Tuple[str, Image.Image]],
) -> Path:
    """Build a fully-populated timeline in tmp_path and return timeline.md.

    Each `screens` entry is `(timestamp_str, image)` where `timestamp_str` is
    `MM:SS`. Blocks are 10 seconds long; the frame filename is
    `frame_<start_seconds:04d>.png` matching the production layout.
    """
    video_dir = tmp_path / "synthetic-video"
    attachments = video_dir / "attachments"
    attachments.mkdir(parents=True)

    blocks: List[TimeBlock] = []
    frame_map = {}
    for ts, img in screens:
        mm, ss = (int(p) for p in ts.split(":"))
        start = mm * 60 + ss
        end = start + 10
        block = TimeBlock(
            start_time=ts,
            end_time=f"{end // 60:02d}:{end % 60:02d}",
            start_seconds=start,
            end_seconds=end,
            text=f"Block at {ts}",
        )
        # Match production layout: filename uses MMSS midpoint, not seconds
        # (see TimeBlock.midpoint_timestamp and frames.extract_frames_batch).
        frame_path = attachments / f"frame_{block.midpoint_timestamp}.png"
        _write_png(frame_path, img)
        blocks.append(block)
        frame_map[block] = frame_path

    return generate_timeline_document(blocks, frame_map, video_dir, "Synthetic Video")


# --------------------------------------------------------------------------- #
# find_duplicate_runs
# --------------------------------------------------------------------------- #


class TestFindDuplicateRuns:
    def test_groups_adjacent_identical_frames(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("A")),
                ("00:20", _make_screen("A")),
                ("00:30", _make_screen("B")),
            ],
        )
        _, blocks_with_frames = parse_timeline_document(timeline)
        runs = find_duplicate_runs(blocks_with_frames)
        assert runs == [(0, [1, 2])]

    def test_no_duplicates_for_distinct_frames(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("B")),
                ("00:20", _make_screen("C")),
            ],
        )
        _, blocks_with_frames = parse_timeline_document(timeline)
        assert find_duplicate_runs(blocks_with_frames) == []

    def test_jitter_within_threshold_is_grouped(self, tmp_path):
        # Same screen with the label shifted 2px — should fall under threshold
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A", jitter=0)),
                ("00:10", _make_screen("A", jitter=2)),
            ],
        )
        _, blocks_with_frames = parse_timeline_document(timeline)
        runs = find_duplicate_runs(blocks_with_frames)
        assert runs == [(0, [1])]

    def test_block_without_frame_breaks_the_run(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("A")),
                ("00:20", _make_screen("A")),
            ],
        )
        # Drop the middle image manually to simulate an already-deduped block
        timeline.write_text(
            timeline.read_text().replace(
                "## 00:10\u201300:20\n![[attachments/frame_0015.png]]\n",
                "## 00:10\u201300:20\n",
            )
        )
        _, blocks_with_frames = parse_timeline_document(timeline)
        # Run is broken: 00:00 starts a run, 00:10 has no frame, 00:20 starts
        # a new "run" of one — neither group has duplicates to report.
        assert find_duplicate_runs(blocks_with_frames) == []


# --------------------------------------------------------------------------- #
# apply_dedupe
# --------------------------------------------------------------------------- #


class TestApplyDedupe:
    def test_archives_duplicates_and_rewrites_markdown(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("A")),
                ("00:20", _make_screen("A")),
                ("00:30", _make_screen("B")),
            ],
        )

        report = apply_dedupe(timeline)

        assert report.kept == 2  # one canonical A, one B
        assert report.removed_image_lines == 2
        assert report.threshold == DEFAULT_THRESHOLD

        attachments = timeline.parent / "attachments"
        archive = attachments / "archive"
        # Frame filenames use the MMSS midpoint:
        # 00:00–00:10 → midpoint 00:05 → frame_0005.png (kept)
        # 00:10–00:20 → midpoint 00:15 → frame_0015.png (archived)
        # 00:20–00:30 → midpoint 00:25 → frame_0025.png (archived)
        # 00:30–00:40 → midpoint 00:35 → frame_0035.png (kept; new run)
        assert (archive / "frame_0015.png").exists()
        assert (archive / "frame_0025.png").exists()
        assert (attachments / "frame_0005.png").exists()
        assert (attachments / "frame_0035.png").exists()
        assert not (attachments / "frame_0015.png").exists()
        assert not (attachments / "frame_0025.png").exists()

        markdown = timeline.read_text()
        # Image links for the dropped frames are gone, but the timestamps remain
        assert "![[attachments/frame_0015.png]]" not in markdown
        assert "![[attachments/frame_0025.png]]" not in markdown
        assert "## 00:10\u201300:20" in markdown
        assert "## 00:20\u201300:30" in markdown
        # Quotes preserved
        assert '"Block at 00:10"' in markdown
        assert '"Block at 00:20"' in markdown

    def test_dry_run_changes_nothing(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("A")),
            ],
        )
        original = timeline.read_text()

        report = apply_dedupe(timeline, dry_run=True)
        assert report.dry_run is True
        assert report.removed_image_lines == 1
        # Disk untouched
        assert timeline.read_text() == original
        attachments = timeline.parent / "attachments"
        # 00:10–00:20 → midpoint 00:15 → frame_0015.png
        assert (attachments / "frame_0015.png").exists()
        assert not (attachments / "archive").exists()

    def test_idempotent(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("A")),
                ("00:20", _make_screen("A")),
            ],
        )
        first = apply_dedupe(timeline)
        assert first.removed_image_lines == 2

        second = apply_dedupe(timeline)
        assert second.removed_image_lines == 0
        assert second.kept == 1


# --------------------------------------------------------------------------- #
# restore_dedupe
# --------------------------------------------------------------------------- #


class TestRestoreDedupe:
    def test_round_trip(self, tmp_path):
        timeline = _build_timeline(
            tmp_path,
            [
                ("00:00", _make_screen("A")),
                ("00:10", _make_screen("A")),
                ("00:20", _make_screen("B")),
            ],
        )
        original_markdown = timeline.read_text()

        apply_dedupe(timeline)
        restore_report = restore_dedupe(timeline)

        assert len(restore_report.restored) == 1
        assert restore_report.skipped_no_block == []

        attachments = timeline.parent / "attachments"
        # Both frames live under attachments/ again
        assert (attachments / "frame_0015.png").exists()
        # Archive cleaned up
        assert not (attachments / "archive").exists()
        # Markdown matches the original byte-for-byte
        assert timeline.read_text() == original_markdown

    def test_round_trip_past_one_minute(self, tmp_path):
        """Regression: filenames are MMSS, not seconds — must round-trip past 60s.

        For a block at 01:10–01:20, the frame is `frame_0115.png` (midpoint
        timestamp = 0115). An earlier implementation parsed that as the integer
        115 and looked it up against `start_seconds=70`, failing to restore.
        """
        timeline = _build_timeline(
            tmp_path,
            [
                ("01:10", _make_screen("A")),
                ("01:20", _make_screen("A")),
                ("01:30", _make_screen("B")),
            ],
        )
        original_markdown = timeline.read_text()
        # Sanity-check the filename shape that triggered the bug
        assert "frame_0115.png" in original_markdown

        apply_dedupe(timeline)
        restore_report = restore_dedupe(timeline)

        assert len(restore_report.restored) == 1
        assert restore_report.skipped_no_block == []
        assert timeline.read_text() == original_markdown
