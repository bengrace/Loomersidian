"""Tests for transcript parsing."""


import pytest

from loomersidian.transcript import (
    TranscriptEntry,
    parse_timestamp,
    parse_transcript,
    parse_transcript_content,
)


class TestTranscriptEntry:
    """Tests for the TranscriptEntry dataclass."""

    def test_creation(self):
        entry = TranscriptEntry(timestamp="00:15", seconds=15, text="Hello world")
        assert entry.timestamp == "00:15"
        assert entry.seconds == 15
        assert entry.text == "Hello world"

    def test_string_representation(self):
        entry = TranscriptEntry(timestamp="01:30", seconds=90, text="Test message")
        assert str(entry) == "[01:30] Test message"


class TestParseTimestamp:
    """Tests for timestamp parsing."""

    def test_valid_single_digit_minute(self):
        ts, seconds = parse_timestamp("0:15")
        assert ts == "00:15"
        assert seconds == 15

    def test_valid_double_digit_minute(self):
        ts, seconds = parse_timestamp("05:30")
        assert ts == "05:30"
        assert seconds == 330

    def test_valid_large_minute(self):
        ts, seconds = parse_timestamp("12:45")
        assert ts == "12:45"
        assert seconds == 765

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_timestamp("invalid")

    def test_invalid_seconds(self):
        with pytest.raises(ValueError, match="Invalid seconds value"):
            parse_timestamp("00:65")

    def test_whitespace_handling(self):
        ts, seconds = parse_timestamp("  0:15  ")
        assert ts == "00:15"
        assert seconds == 15


class TestParseTranscriptContent:
    """Tests for transcript content parsing."""

    def test_valid_transcript(self, sample_transcript_content):
        entries = parse_transcript_content(sample_transcript_content)
        assert len(entries) == 11
        assert entries[0].timestamp == "00:00"
        assert entries[0].text == "Hey everyone, welcome to this quick design review."
        assert entries[-1].timestamp == "01:35"

    def test_empty_transcript(self, empty_transcript_content):
        with pytest.raises(ValueError, match="empty"):
            parse_transcript_content(empty_transcript_content)

    def test_no_timestamps(self, no_timestamps_content):
        with pytest.raises(ValueError, match="No valid transcript entries"):
            parse_transcript_content(no_timestamps_content)

    def test_chronological_order(self):
        content = """0:30
Second entry.

0:15
First entry - out of order.
"""
        with pytest.raises(ValueError, match="out of order"):
            parse_transcript_content(content)

    def test_empty_segment(self):
        content = """0:00
Valid text.

0:15

0:30
More text.
"""
        with pytest.raises(ValueError, match="Empty transcript segment"):
            parse_transcript_content(content)

    def test_multiline_text(self):
        content = """0:00
First line of text
Second line of text
Third line of text
"""
        entries = parse_transcript_content(content)
        assert len(entries) == 1
        assert "First line" in entries[0].text
        assert "Second line" in entries[0].text
        assert "Third line" in entries[0].text


class TestParseTranscript:
    """Tests for file-based transcript parsing."""

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_transcript(tmp_path / "nonexistent.txt")

    def test_valid_file(self, sample_transcript_path):
        entries = parse_transcript(sample_transcript_path)
        assert len(entries) == 11
        assert entries[0].timestamp == "00:00"

    def test_preserves_all_content(self, sample_transcript_content):
        entries = parse_transcript_content(sample_transcript_content)
        # Verify no text is dropped
        all_text = " ".join(e.text for e in entries)
        assert "sidebar" in all_text
        assert "header" in all_text
        assert "hierarchy" in all_text
