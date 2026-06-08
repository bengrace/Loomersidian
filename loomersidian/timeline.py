"""Timeline normalization and TimeBlock model for Loomersidian."""

from dataclasses import dataclass
from typing import List, Optional

from loomersidian.transcript import TranscriptEntry

# Target block duration range in seconds.
#
# These are the defaults used when callers do not pass overrides. The
# normalize_timeline function exposes both as parameters so the CLI can let
# users tune cadence per-video (`--min-block`, `--max-block`).
#
# Larger values -> fewer, longer blocks -> fewer extracted frames. Useful when
# the presenter pauses on screens for a long time. Combine with `dedupe` for
# the strongest dedup of paused-on-screen segments.
MIN_BLOCK_DURATION = 5
MAX_BLOCK_DURATION = 15


@dataclass(frozen=True)
class TimeBlock:
    """A merged time block containing multiple transcript entries.

    Attributes:
        start_time: Start timestamp in MM:SS format
        end_time: End timestamp in MM:SS format
        start_seconds: Start time in total seconds
        end_seconds: End time in total seconds
        text: Combined transcript text for the block
    """
    start_time: str
    end_time: str
    start_seconds: int
    end_seconds: int
    text: str

    @property
    def duration(self) -> int:
        """Duration of the block in seconds."""
        return self.end_seconds - self.start_seconds

    @property
    def midpoint_seconds(self) -> int:
        """Midpoint of the block in seconds (for frame extraction)."""
        return self.start_seconds + (self.duration // 2)

    @property
    def midpoint_timestamp(self) -> str:
        """Midpoint timestamp in MMSS format (for frame filename)."""
        mid = self.midpoint_seconds
        minutes = mid // 60
        seconds = mid % 60
        return f"{minutes:02d}{seconds:02d}"

    def __str__(self) -> str:
        return f"[{self.start_time}-{self.end_time}] {self.text[:50]}..."


def seconds_to_timestamp(seconds: int) -> str:
    """Convert total seconds to MM:SS format."""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def normalize_timeline(
    entries: List[TranscriptEntry],
    min_block_duration: Optional[int] = None,
    max_block_duration: Optional[int] = None,
) -> List[TimeBlock]:
    """Merge adjacent transcript entries into TimeBlocks.

    Groups entries to achieve a target block duration. Preserves all
    transcript content without dropping.

    Args:
        entries: List of TranscriptEntry objects in chronological order.
        min_block_duration: Minimum target block duration in seconds. Defaults
            to ``MIN_BLOCK_DURATION``. Larger values -> fewer, longer blocks.
        max_block_duration: Maximum target block duration in seconds. Defaults
            to ``MAX_BLOCK_DURATION``. Larger values -> fewer, longer blocks.

    Returns:
        List of TimeBlock objects.

    Raises:
        ValueError: If durations are non-positive or min > max.
    """
    min_duration = MIN_BLOCK_DURATION if min_block_duration is None else min_block_duration
    max_duration = MAX_BLOCK_DURATION if max_block_duration is None else max_block_duration

    if min_duration <= 0 or max_duration <= 0:
        raise ValueError(
            f"Block durations must be positive (got min={min_duration}, max={max_duration})"
        )
    if min_duration > max_duration:
        raise ValueError(
            f"min_block_duration ({min_duration}) must be <= max_block_duration ({max_duration})"
        )

    if not entries:
        return []

    blocks = []
    current_texts = []
    current_start_seconds = entries[0].seconds
    current_start_time = entries[0].timestamp

    for i, entry in enumerate(entries):
        current_texts.append(entry.text)

        # Determine end time - either next entry's start or estimate based on entry
        if i + 1 < len(entries):
            next_seconds = entries[i + 1].seconds
        else:
            # Last entry: estimate 10 seconds duration
            next_seconds = entry.seconds + 10

        current_duration = next_seconds - current_start_seconds

        # Check if adding the next entry would exceed max_duration
        would_exceed_max = (
            i + 1 < len(entries) and
            entries[i + 1].seconds - current_start_seconds > max_duration
        )

        # Create block if:
        # 1. Duration is in target range (>= min), or
        # 2. Next entry would push us over max duration, or
        # 3. This is the last entry
        should_create_block = (
            current_duration >= min_duration or
            would_exceed_max or
            i == len(entries) - 1
        )

        if should_create_block:
            # Combine texts
            combined_text = ' '.join(current_texts)

            blocks.append(TimeBlock(
                start_time=current_start_time,
                end_time=seconds_to_timestamp(next_seconds),
                start_seconds=current_start_seconds,
                end_seconds=next_seconds,
                text=combined_text
            ))

            # Reset for next block
            current_texts = []
            if i + 1 < len(entries):
                current_start_seconds = entries[i + 1].seconds
                current_start_time = entries[i + 1].timestamp

    return blocks


def insert_block_sorted(blocks: List[TimeBlock], new_block: TimeBlock) -> List[TimeBlock]:
    """Insert a new block into a list maintaining chronological order.

    Args:
        blocks: Existing list of TimeBlock objects (assumed sorted)
        new_block: New TimeBlock to insert

    Returns:
        New list with the block inserted at the correct position
    """
    result = list(blocks)

    # Find insertion point by start_seconds
    insert_idx = 0
    for i, block in enumerate(result):
        if new_block.start_seconds < block.start_seconds:
            insert_idx = i
            break
        insert_idx = i + 1

    result.insert(insert_idx, new_block)
    return result
