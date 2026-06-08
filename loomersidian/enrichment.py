"""Zoom-in enrichment for Loomersidian timeline documents."""

import re
from typing import TYPE_CHECKING, List, Tuple

from loomersidian.timeline import TimeBlock

if TYPE_CHECKING:
    from loomersidian.transcript import TranscriptEntry


def parse_zoom_range(range_str: str) -> Tuple[int, int]:
    """Parse a timestamp range string into start and end seconds.

    Args:
        range_str: Range in format "MM:SS-MM:SS" or "MM:SS\u2013MM:SS"

    Returns:
        Tuple of (start_seconds, end_seconds)

    Raises:
        ValueError: If range format is invalid
    """
    # Support both hyphen and en-dash
    parts = re.split(r'[-\u2013]', range_str.strip())

    if len(parts) != 2:
        raise ValueError(
            f"Invalid range format: {range_str}. Expected MM:SS-MM:SS"
        )

    def parse_timestamp(ts: str) -> int:
        match = re.match(r'^(\d{1,2}):(\d{2})$', ts.strip())
        if not match:
            raise ValueError(f"Invalid timestamp: {ts}")
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        return minutes * 60 + seconds

    start_seconds = parse_timestamp(parts[0])
    end_seconds = parse_timestamp(parts[1])

    if end_seconds <= start_seconds:
        raise ValueError(
            f"End time must be after start time: {range_str}"
        )

    return start_seconds, end_seconds


def validate_range_against_video(
    start_seconds: int,
    end_seconds: int,
    video_duration: float
) -> None:
    """Validate that the zoom range is within video duration.

    Args:
        start_seconds: Start of zoom range
        end_seconds: End of zoom range
        video_duration: Total video duration in seconds

    Raises:
        ValueError: If range is outside video duration
    """
    if start_seconds < 0:
        raise ValueError("Start time cannot be negative")

    if end_seconds > video_duration:
        raise ValueError(
            f"End time ({end_seconds}s) exceeds video duration ({video_duration:.0f}s)"
        )


def filter_blocks_in_range(
    blocks: List[TimeBlock],
    start_seconds: int,
    end_seconds: int
) -> Tuple[List[TimeBlock], List[TimeBlock], List[TimeBlock]]:
    """Split blocks into before, in-range, and after the zoom range.

    Args:
        blocks: List of TimeBlock objects
        start_seconds: Start of zoom range
        end_seconds: End of zoom range

    Returns:
        Tuple of (before_blocks, in_range_blocks, after_blocks)
    """
    before = []
    in_range = []
    after = []

    for block in blocks:
        if block.end_seconds <= start_seconds:
            before.append(block)
        elif block.start_seconds >= end_seconds:
            after.append(block)
        else:
            in_range.append(block)

    return before, in_range, after


def create_enriched_blocks(
    entries: "List[TranscriptEntry]",
    start_seconds: int,
    end_seconds: int,
    target_duration: int = 3  # Finer granularity for zoom
) -> List[TimeBlock]:
    """Create finer-grained TimeBlocks for a specific range.

    Args:
        entries: Original transcript entries
        start_seconds: Start of zoom range
        end_seconds: End of zoom range
        target_duration: Target block duration (smaller = more detail)

    Returns:
        List of TimeBlock objects for the enriched range
    """
    from loomersidian.timeline import seconds_to_timestamp

    # Filter entries to those in range
    range_entries = [
        e for e in entries
        if start_seconds <= e.seconds < end_seconds
    ]

    if not range_entries:
        return []

    blocks = []
    current_texts = []
    current_start_seconds = range_entries[0].seconds
    current_start_time = range_entries[0].timestamp

    for i, entry in enumerate(range_entries):
        current_texts.append(entry.text)

        # Determine next boundary
        if i + 1 < len(range_entries):
            next_seconds = range_entries[i + 1].seconds
        else:
            next_seconds = min(entry.seconds + 5, end_seconds)

        current_duration = next_seconds - current_start_seconds

        # Create block with finer granularity
        should_create = (
            current_duration >= target_duration or
            i == len(range_entries) - 1
        )

        if should_create:
            blocks.append(TimeBlock(
                start_time=current_start_time,
                end_time=seconds_to_timestamp(next_seconds),
                start_seconds=current_start_seconds,
                end_seconds=next_seconds,
                text=' '.join(current_texts)
            ))

            current_texts = []
            if i + 1 < len(range_entries):
                current_start_seconds = range_entries[i + 1].seconds
                current_start_time = range_entries[i + 1].timestamp

    return blocks
