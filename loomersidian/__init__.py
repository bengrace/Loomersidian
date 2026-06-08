"""Loomersidian: Convert Loom videos to LLM-ready Obsidian Markdown timelines."""

__version__ = "0.2.0"
__author__ = "Ben Grace"

# Core models and parsing
# Zoom-in enrichment
from loomersidian.enrichment import (
    create_enriched_blocks,
    filter_blocks_in_range,
    parse_zoom_range,
    validate_range_against_video,
)

# Frame extraction
from loomersidian.frames import extract_frame, extract_frames_batch, get_video_duration

# Document generation
from loomersidian.generator import (
    generate_timeline_document,
    render_block,
    slugify,
    validate_timeline_document,
)
from loomersidian.timeline import TimeBlock, normalize_timeline, seconds_to_timestamp
from loomersidian.transcript import TranscriptEntry, parse_transcript

__all__ = [
    # Core
    "TranscriptEntry",
    "parse_transcript",
    "TimeBlock",
    "normalize_timeline",
    "seconds_to_timestamp",
    # Frames
    "extract_frame",
    "extract_frames_batch",
    "get_video_duration",
    # Generator
    "render_block",
    "generate_timeline_document",
    "validate_timeline_document",
    "slugify",
    # Enrichment
    "parse_zoom_range",
    "validate_range_against_video",
    "filter_blocks_in_range",
    "create_enriched_blocks",
]
