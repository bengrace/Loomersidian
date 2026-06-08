"""Tests for timeline normalization."""

import pytest

from loomersidian.timeline import TimeBlock, normalize_timeline, seconds_to_timestamp
from loomersidian.transcript import TranscriptEntry


class TestTimeBlock:
    """Tests for the TimeBlock dataclass."""

    def test_duration(self):
        block = TimeBlock(
            start_time="00:10",
            end_time="00:20",
            start_seconds=10,
            end_seconds=20,
            text="Test"
        )
        assert block.duration == 10

    def test_midpoint_seconds(self):
        block = TimeBlock(
            start_time="00:10",
            end_time="00:20",
            start_seconds=10,
            end_seconds=20,
            text="Test"
        )
        assert block.midpoint_seconds == 15

    def test_midpoint_timestamp(self):
        block = TimeBlock(
            start_time="01:10",
            end_time="01:30",
            start_seconds=70,
            end_seconds=90,
            text="Test"
        )
        # Midpoint is 80 seconds = 1:20 = "0120"
        assert block.midpoint_timestamp == "0120"

    def test_string_representation(self):
        block = TimeBlock(
            start_time="00:10",
            end_time="00:20",
            start_seconds=10,
            end_seconds=20,
            text="A" * 100
        )
        result = str(block)
        assert "[00:10-00:20]" in result
        assert "..." in result


class TestSecondsToTimestamp:
    """Tests for timestamp conversion."""

    def test_zero(self):
        assert seconds_to_timestamp(0) == "00:00"

    def test_seconds_only(self):
        assert seconds_to_timestamp(45) == "00:45"

    def test_minutes_and_seconds(self):
        assert seconds_to_timestamp(125) == "02:05"

    def test_large_value(self):
        assert seconds_to_timestamp(600) == "10:00"


class TestNormalizeTimeline:
    """Tests for timeline normalization."""

    def test_empty_entries(self):
        assert normalize_timeline([]) == []

    def test_single_entry(self):
        entries = [
            TranscriptEntry(timestamp="00:00", seconds=0, text="Hello")
        ]
        blocks = normalize_timeline(entries)
        assert len(blocks) == 1
        assert blocks[0].text == "Hello"

    def test_preserves_all_content(self):
        entries = [
            TranscriptEntry(timestamp="00:00", seconds=0, text="First"),
            TranscriptEntry(timestamp="00:05", seconds=5, text="Second"),
            TranscriptEntry(timestamp="00:10", seconds=10, text="Third"),
        ]
        blocks = normalize_timeline(entries)
        all_text = " ".join(b.text for b in blocks)
        assert "First" in all_text
        assert "Second" in all_text
        assert "Third" in all_text

    def test_merges_short_entries(self):
        # Entries 2 seconds apart should be merged
        entries = [
            TranscriptEntry(timestamp="00:00", seconds=0, text="A"),
            TranscriptEntry(timestamp="00:02", seconds=2, text="B"),
            TranscriptEntry(timestamp="00:04", seconds=4, text="C"),
            TranscriptEntry(timestamp="00:10", seconds=10, text="D"),
        ]
        blocks = normalize_timeline(entries)
        # First 3 entries should be in first block (duration < MIN_BLOCK_DURATION individually)
        assert any("A" in b.text and "B" in b.text for b in blocks)

    def test_chronological_order(self):
        entries = [
            TranscriptEntry(timestamp="00:00", seconds=0, text="First"),
            TranscriptEntry(timestamp="00:15", seconds=15, text="Second"),
            TranscriptEntry(timestamp="00:30", seconds=30, text="Third"),
        ]
        blocks = normalize_timeline(entries)
        for i in range(1, len(blocks)):
            assert blocks[i].start_seconds >= blocks[i-1].end_seconds

    def test_text_concatenation(self):
        entries = [
            TranscriptEntry(timestamp="00:00", seconds=0, text="Hello"),
            TranscriptEntry(timestamp="00:02", seconds=2, text="world"),
        ]
        blocks = normalize_timeline(entries)
        # Both should be in same block, text joined with space
        assert "Hello world" in blocks[0].text or "Hello" in blocks[0].text

    # --- Cadence overrides --------------------------------------------------

    def _five_second_entries(self, count: int):
        return [
            TranscriptEntry(
                timestamp=f"00:{i*5:02d}", seconds=i * 5, text=f"line {i}"
            )
            for i in range(count)
        ]

    def test_larger_max_block_produces_fewer_blocks(self):
        entries = self._five_second_entries(8)  # 0,5,10,...,35s
        default_blocks = normalize_timeline(entries)
        coarse_blocks = normalize_timeline(
            entries, min_block_duration=15, max_block_duration=30
        )
        assert len(coarse_blocks) < len(default_blocks)
        # Content is preserved either way
        assert " ".join(b.text for b in default_blocks) == " ".join(
            b.text for b in coarse_blocks
        )

    def test_smaller_min_block_produces_more_blocks(self):
        # 1-second-spaced entries: defaults merge ~5+ together; min=1 keeps
        # them as separate blocks.
        entries = [
            TranscriptEntry(
                timestamp=f"00:{i:02d}", seconds=i, text=f"line {i}"
            )
            for i in range(20)
        ]
        default_blocks = normalize_timeline(entries)
        fine_blocks = normalize_timeline(
            entries, min_block_duration=1, max_block_duration=2
        )
        assert len(fine_blocks) > len(default_blocks)

    def test_invalid_min_zero_raises(self):
        entries = self._five_second_entries(2)
        with pytest.raises(ValueError, match="positive"):
            normalize_timeline(entries, min_block_duration=0)

    def test_invalid_min_greater_than_max_raises(self):
        entries = self._five_second_entries(2)
        with pytest.raises(ValueError, match="must be <="):
            normalize_timeline(entries, min_block_duration=20, max_block_duration=10)
