"""Markdown generation for Loomersidian timeline documents."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loomersidian.timeline import TimeBlock


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: Input text to slugify

    Returns:
        Lowercase slug with hyphens instead of spaces/special chars
    """
    # Convert to lowercase
    slug = text.lower()
    # Replace spaces and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    # Remove special characters except hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    # Remove multiple consecutive hyphens
    slug = re.sub(r'-+', '-', slug)
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    return slug


def render_block(block: TimeBlock, frame_path: Optional[Path]) -> str:
    """Render a single TimeBlock to Markdown.

    Args:
        block: The TimeBlock to render
        frame_path: Path to the frame image (relative to document), or None
            to render the block without an image link (used by `dedupe`).

    Returns:
        Markdown string for the block
    """
    # Use en-dash for timestamp range as per schema
    timestamp_range = f"{block.start_time}\u2013{block.end_time}"

    lines = [f"## {timestamp_range}"]
    if frame_path is not None:
        # Frame filename for embedding (relative path from timeline.md)
        frame_filename = f"attachments/{frame_path.name}"
        lines.append(f"![[{frame_filename}]]")
    lines.extend([
        f'"{block.text}"',
        "",  # Blank line after block
    ])

    return "\n".join(lines)


def generate_timeline_document(
    blocks: List[TimeBlock],
    frame_map: Dict[TimeBlock, Optional[Path]],
    output_dir: Path,
    video_name: str
) -> Path:
    """Generate a complete timeline Markdown document.

    Args:
        blocks: List of TimeBlock objects in chronological order
        frame_map: Dictionary mapping TimeBlock to frame path. A value of
            None signals an image-less block (rendered without `![[…]]`).
        output_dir: Video-specific output directory (already created by CLI)
        video_name: Name of the source video (for title)

    Returns:
        Path to the generated timeline.md file
    """
    # Build document content
    lines = [
        f"# {video_name}",
        "",  # Blank line after title
    ]

    for block in blocks:
        if block not in frame_map:
            raise ValueError(f"No frame entry for block: {block.start_time}")

        block_md = render_block(block, frame_map[block])
        lines.append(block_md)

    # Write timeline.md
    timeline_path = output_dir / "timeline.md"
    timeline_path.write_text("\n".join(lines), encoding='utf-8')

    return timeline_path


def validate_timeline_document(doc_path: Path) -> List[str]:
    """Validate a timeline document against the schema contract.

    Args:
        doc_path: Path to the timeline.md file

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not doc_path.exists():
        return ["Timeline document does not exist"]

    content = doc_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Check for title (H1)
    if not lines or not lines[0].startswith('# '):
        errors.append("Missing document title (H1 header)")

    # Check for timestamp blocks
    timestamp_pattern = re.compile(r'^## (\d{2}:\d{2})\u2013(\d{2}:\d{2})$')
    image_pattern = re.compile(r'^!\[\[attachments/frame_\d{4}\.png\]\]$')
    quote_pattern = re.compile(r'^".*"$')

    in_block = False
    block_start = None
    has_image = False
    has_quote = False
    prev_end_seconds = -1

    attachments_dir = doc_path.parent / "attachments"

    for i, line in enumerate(lines):
        ts_match = timestamp_pattern.match(line)
        if ts_match:
            # Validate previous block completeness
            if in_block:
                if not has_image:
                    errors.append(f"Block at line {block_start} missing image embed")
                if not has_quote:
                    errors.append(f"Block at line {block_start} missing quoted transcript")

            # Start new block
            in_block = True
            block_start = i + 1
            has_image = False
            has_quote = False

            # Check chronological order
            start_time = ts_match.group(1)
            start_parts = start_time.split(':')
            start_seconds = int(start_parts[0]) * 60 + int(start_parts[1])

            if start_seconds < prev_end_seconds:
                errors.append(f"Blocks not in chronological order at line {i + 1}")

            end_time = ts_match.group(2)
            end_parts = end_time.split(':')
            prev_end_seconds = int(end_parts[0]) * 60 + int(end_parts[1])

        elif image_pattern.match(line):
            has_image = True
            # Extract frame filename and check it exists
            frame_match = re.search(r'frame_\d{4}\.png', line)
            if frame_match:
                frame_file = attachments_dir / frame_match.group(0)
                if not frame_file.exists():
                    errors.append(f"Referenced frame does not exist: {frame_file}")

        elif quote_pattern.match(line):
            has_quote = True

    # Check final block
    if in_block:
        if not has_image:
            errors.append(f"Block at line {block_start} missing image embed")
        if not has_quote:
            errors.append(f"Block at line {block_start} missing quoted transcript")

    return errors


def parse_timeline_document(doc_path: Path) -> Tuple[str, List[Tuple[TimeBlock, Optional[Path]]]]:
    """Parse an existing timeline document into its components.

    Args:
        doc_path: Path to the timeline.md file

    Returns:
        Tuple of (title, list of (TimeBlock, frame_path) tuples)

    Raises:
        FileNotFoundError: If document doesn't exist
        ValueError: If document format is invalid
    """
    if not doc_path.exists():
        raise FileNotFoundError(f"Timeline document not found: {doc_path}")

    content = doc_path.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Extract title
    if not lines or not lines[0].startswith('# '):
        raise ValueError("Missing document title (H1 header)")
    title = lines[0][2:].strip()

    attachments_dir = doc_path.parent / "attachments"

    # Parse blocks
    timestamp_pattern = re.compile(r'^## (\d{2}:\d{2})\u2013(\d{2}:\d{2})$')
    image_pattern = re.compile(r'^!\[\[attachments/(frame_\d{4}\.png)\]\]$')
    quote_pattern = re.compile(r'^"(.*)"$')

    # NOTE: blocks may legitimately have no image line after a `dedupe` pass
    # (the image is moved to attachments/archive/ and the link is removed).
    # We therefore keep blocks where current_frame_path is None and represent
    # them with frame_path == None in the returned list.
    blocks_with_frames: List[Tuple[TimeBlock, Optional[Path]]] = []
    current_start_time = None
    current_end_time = None
    current_frame_path: Optional[Path] = None
    current_text = None

    def _flush() -> None:
        if current_start_time is None:
            return
        start_parts = current_start_time.split(':')
        start_seconds = int(start_parts[0]) * 60 + int(start_parts[1])
        end_parts = current_end_time.split(':')
        end_seconds = int(end_parts[0]) * 60 + int(end_parts[1])
        block = TimeBlock(
            start_time=current_start_time,
            end_time=current_end_time,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            text=current_text or "",
        )
        blocks_with_frames.append((block, current_frame_path))

    for line in lines:
        ts_match = timestamp_pattern.match(line)
        if ts_match:
            _flush()
            current_start_time = ts_match.group(1)
            current_end_time = ts_match.group(2)
            current_frame_path = None
            current_text = None

        elif (img_match := image_pattern.match(line)):
            frame_name = img_match.group(1)
            current_frame_path = attachments_dir / frame_name

        elif (quote_match := quote_pattern.match(line)):
            current_text = quote_match.group(1)

    _flush()

    return title, blocks_with_frames


def update_timeline_document(
    doc_path: Path,
    blocks: List[TimeBlock],
    frame_map: Dict[TimeBlock, Optional[Path]],
    title: str
) -> Path:
    """Update an existing timeline document with new blocks.

    Args:
        doc_path: Path to the timeline.md file
        blocks: List of TimeBlock objects in chronological order
        frame_map: Dictionary mapping TimeBlock to frame path. A value of
            None signals an image-less block (rendered without `![[…]]`),
            which is the on-disk shape produced by `loomersidian dedupe`.
        title: Document title

    Returns:
        Path to the updated timeline.md file
    """
    # Build document content
    lines = [
        f"# {title}",
        "",  # Blank line after title
    ]

    for block in blocks:
        if block not in frame_map:
            raise ValueError(f"No frame entry for block: {block.start_time}")

        block_md = render_block(block, frame_map[block])
        lines.append(block_md)

    # Write back to timeline.md
    doc_path.write_text("\n".join(lines), encoding='utf-8')

    return doc_path
