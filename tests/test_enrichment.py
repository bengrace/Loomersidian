"""Tests for zoom-in enrichment."""

import pytest

from loomersidian.enrichment import (
    create_enriched_blocks,
    filter_blocks_in_range,
    parse_zoom_range,
    validate_range_against_video,
)
from loomersidian.timeline import TimeBlock
from loomersidian.transcript import TranscriptEntry


class TestParseZoomRange:
    """Tests for range parsing."""

    def test_valid_range_with_hyphen(self):
        start, end = parse_zoom_range("01:05-01:25")
        assert start == 65
        assert end == 85

    def test_valid_range_with_en_dash(self):
        start, end = parse_zoom_range("01:05\u201301:25")
        assert start == 65
        assert end == 85

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid range format"):
            parse_zoom_range("01:05")

    def test_invalid_timestamp(self):
        with pytest.raises(ValueError, match="Invalid timestamp"):
            parse_zoom_range("invalid-01:25")

    def test_end_before_start(self):
        with pytest.raises(ValueError, match="End time must be after"):
            parse_zoom_range("01:30-01:15")

    def test_whitespace_handling(self):
        start, end = parse_zoom_range("  01:05 - 01:25  ")
        assert start == 65
        assert end == 85


class TestValidateRangeAgainstVideo:
    """Tests for range validation against video duration."""

    def test_valid_range(self):
        # Should not raise
        validate_range_against_video(60, 120, 300.0)

    def test_negative_start(self):
        with pytest.raises(ValueError, match="cannot be negative"):
            validate_range_against_video(-10, 60, 300.0)

    def test_end_exceeds_duration(self):
        with pytest.raises(ValueError, match="exceeds video duration"):
            validate_range_against_video(60, 400, 300.0)


class TestFilterBlocksInRange:
    """Tests for filtering blocks by range."""

    def test_splits_correctly(self):
        blocks = [
            TimeBlock("00:00", "00:10", 0, 10, "A"),
            TimeBlock("00:10", "00:20", 10, 20, "B"),
            TimeBlock("00:20", "00:30", 20, 30, "C"),
            TimeBlock("00:30", "00:40", 30, 40, "D"),
            TimeBlock("00:40", "00:50", 40, 50, "E"),
        ]

        # Range 15-35 overlaps with B (10-20), C (20-30), and D (30-40)
        before, in_range, after = filter_blocks_in_range(blocks, 15, 35)

        assert len(before) == 1
        assert before[0].text == "A"
        assert len(in_range) == 3  # B, C, D all overlap with 15-35
        assert len(after) == 1
        assert after[0].text == "E"

    def test_empty_result(self):
        blocks = [
            TimeBlock("00:00", "00:10", 0, 10, "A"),
        ]

        before, in_range, after = filter_blocks_in_range(blocks, 20, 30)

        assert len(before) == 1
        assert len(in_range) == 0
        assert len(after) == 0


class TestCreateEnrichedBlocks:
    """Tests for creating enriched blocks."""

    def test_creates_finer_blocks(self):
        entries = [
            TranscriptEntry("00:10", 10, "Entry 1"),
            TranscriptEntry("00:12", 12, "Entry 2"),
            TranscriptEntry("00:14", 14, "Entry 3"),
            TranscriptEntry("00:16", 16, "Entry 4"),
        ]

        blocks = create_enriched_blocks(entries, 10, 20, target_duration=3)

        # Should create blocks with finer granularity
        assert len(blocks) >= 1
        # All text should be preserved
        all_text = " ".join(b.text for b in blocks)
        assert "Entry 1" in all_text
        assert "Entry 4" in all_text

    def test_filters_to_range(self):
        entries = [
            TranscriptEntry("00:00", 0, "Before"),
            TranscriptEntry("00:10", 10, "In range"),
            TranscriptEntry("00:20", 20, "After"),
        ]

        blocks = create_enriched_blocks(entries, 5, 15)

        # Should only include "In range"
        assert len(blocks) == 1
        assert "In range" in blocks[0].text
        assert "Before" not in blocks[0].text
        assert "After" not in blocks[0].text

    def test_empty_range(self):
        entries = [
            TranscriptEntry("00:00", 0, "Outside"),
        ]

        blocks = create_enriched_blocks(entries, 10, 20)

        assert len(blocks) == 0
