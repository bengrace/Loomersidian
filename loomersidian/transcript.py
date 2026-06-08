"""Transcript parsing and entry model for Loomersidian."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class TranscriptEntry:
    """A single timestamp + text pair from a Loom transcript.

    Attributes:
        timestamp: The timestamp in MM:SS format (normalized)
        seconds: The timestamp as total seconds (for calculations)
        text: The transcript text for this segment
    """
    timestamp: str
    seconds: int
    text: str

    def __str__(self) -> str:
        return f"[{self.timestamp}] {self.text}"


def parse_timestamp(ts: str) -> tuple[str, int]:
    """Parse a timestamp string and return normalized format and seconds.

    Args:
        ts: Timestamp in M:SS or MM:SS format

    Returns:
        Tuple of (normalized MM:SS string, total seconds)

    Raises:
        ValueError: If timestamp format is invalid
    """
    match = re.match(r'^(\d{1,2}):(\d{2})$', ts.strip())
    if not match:
        raise ValueError(f"Invalid timestamp format: {ts}")

    minutes = int(match.group(1))
    seconds = int(match.group(2))

    if seconds >= 60:
        raise ValueError(f"Invalid seconds value in timestamp: {ts}")

    total_seconds = minutes * 60 + seconds
    normalized = f"{minutes:02d}:{seconds:02d}"

    return normalized, total_seconds


def parse_transcript(path: Path) -> List[TranscriptEntry]:
    """Parse a Loom transcript file into TranscriptEntry objects.

    Args:
        path: Path to the transcript file

    Returns:
        List of TranscriptEntry objects in chronological order

    Raises:
        FileNotFoundError: If the transcript file doesn't exist
        ValueError: If the transcript format is invalid
    """
    if not path.exists():
        raise FileNotFoundError(f"Transcript file not found: {path}")

    content = path.read_text(encoding='utf-8')
    return parse_transcript_content(content)


def parse_srt_timestamp(ts: str) -> tuple[str, int]:
    """Parse an SRT timestamp (HH:MM:SS,mmm) and return normalized format and seconds.

    Args:
        ts: Timestamp in HH:MM:SS,mmm format

    Returns:
        Tuple of (normalized MM:SS string, total seconds)

    Raises:
        ValueError: If timestamp format is invalid
    """
    match = re.match(r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})$', ts.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp format: {ts}")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))

    total_minutes = hours * 60 + minutes
    total_seconds = total_minutes * 60 + seconds
    normalized = f"{total_minutes:02d}:{seconds:02d}"

    return normalized, total_seconds


def is_srt_format(content: str) -> bool:
    """Detect if content is in SRT (SubRip) format.

    SRT format has numbered entries with time ranges like:
    1
    00:00:00,011 --> 00:00:02,783
    Text here
    """
    srt_pattern = re.compile(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', re.MULTILINE)
    return bool(srt_pattern.search(content))


def parse_srt_content(content: str) -> List[TranscriptEntry]:
    """Parse SRT (SubRip) format content into TranscriptEntry objects.

    Args:
        content: The SRT file content

    Returns:
        List of TranscriptEntry objects in chronological order
    """
    blocks = re.split(r'\n\s*\n', content.strip())
    entries = []

    time_range_pattern = re.compile(
        r'^(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})$'
    )

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue

        # First line is sequence number (skip it)
        # Second line is time range
        time_line = lines[1].strip() if len(lines) > 1 else ''
        match = time_range_pattern.match(time_line)

        if not match:
            # Maybe first line is time range (no sequence number)
            time_line = lines[0].strip()
            match = time_range_pattern.match(time_line)
            if match:
                text_lines = lines[1:]
            else:
                continue
        else:
            text_lines = lines[2:]

        start_ts = match.group(1)
        text = ' '.join(line.strip() for line in text_lines if line.strip())

        if not text:
            continue

        normalized, seconds = parse_srt_timestamp(start_ts)
        entries.append(TranscriptEntry(
            timestamp=normalized,
            seconds=seconds,
            text=text
        ))

    if not entries:
        raise ValueError("No valid SRT entries found")

    return entries


def parse_transcript_content(content: str) -> List[TranscriptEntry]:
    """Parse transcript content string into TranscriptEntry objects.

    Automatically detects format (SRT or Loom native) and parses accordingly.

    Args:
        content: The transcript file content

    Returns:
        List of TranscriptEntry objects in chronological order

    Raises:
        ValueError: If the transcript format is invalid
    """
    if not content.strip():
        raise ValueError("Transcript file is empty")

    # Auto-detect and parse SRT format
    if is_srt_format(content):
        return parse_srt_content(content)

    # Parse Loom native format
    blocks = re.split(r'\n\s*\n', content.strip())

    entries = []
    timestamp_pattern = re.compile(r'^(\d{1,2}:\d{2})$')

    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue

        # First line should be timestamp
        first_line = lines[0].strip()
        match = timestamp_pattern.match(first_line)

        if not match:
            continue  # Skip blocks without timestamps

        timestamp_str = match.group(1)
        text_lines = lines[1:]

        if not text_lines:
            raise ValueError(f"Empty transcript segment at {timestamp_str}")

        text = ' '.join(line.strip() for line in text_lines if line.strip())

        if not text:
            raise ValueError(f"Empty transcript segment at {timestamp_str}")

        normalized, seconds = parse_timestamp(timestamp_str)
        entries.append(TranscriptEntry(
            timestamp=normalized,
            seconds=seconds,
            text=text
        ))

    if not entries:
        raise ValueError("No valid transcript entries found (no timestamps)")

    # Validate chronological order
    for i in range(1, len(entries)):
        if entries[i].seconds < entries[i-1].seconds:
            raise ValueError(
                f"Timestamps out of order: {entries[i-1].timestamp} -> {entries[i].timestamp}"
            )

    return entries
