"""Command-line interface for Loomersidian."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from loomersidian import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="loomersidian",
        description="Convert Loom videos to LLM-ready Obsidian Markdown timelines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command (default behavior)
    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a new timeline from video + transcript",
        epilog="""
Examples:
  loomersidian generate -i video.mp4 -t video.txt -o ./output
  loomersidian generate -i video.mp4 -t video.txt -o ./output --zoom-range 01:05-01:25
        """,
    )
    generate_parser.add_argument(
        "-i", "--input",
        type=Path,
        required=True,
        metavar="VIDEO",
        help="Path to the Loom MP4 video file",
    )
    generate_parser.add_argument(
        "-t", "--transcript",
        type=Path,
        required=True,
        metavar="TRANSCRIPT",
        help="Path to the Loom transcript file (.txt or .srt)",
    )
    generate_parser.add_argument(
        "-o", "--output",
        type=Path,
        required=True,
        metavar="DIR",
        help="Output directory for generated timeline",
    )
    generate_parser.add_argument(
        "--zoom-range",
        type=str,
        metavar="START-END",
        help="Timestamp range for zoom-in enrichment (e.g., 01:05-01:25)",
    )
    generate_parser.add_argument(
        "--min-block",
        type=int,
        default=None,
        metavar="SECONDS",
        help=(
            "Minimum target block duration in seconds (default: 5). Larger "
            "values produce fewer, longer blocks and therefore fewer frames."
        ),
    )
    generate_parser.add_argument(
        "--max-block",
        type=int,
        default=None,
        metavar="SECONDS",
        help=(
            "Maximum target block duration in seconds (default: 15). Larger "
            "values produce fewer, longer blocks and therefore fewer frames."
        ),
    )
    generate_parser.add_argument(
        "--dedupe",
        action="store_true",
        help=(
            "After generation, run the dedupe pass to collapse runs of "
            "visually-identical adjacent frames. Equivalent to running "
            "`loomersidian dedupe --timeline <output>` afterwards."
        ),
    )
    generate_parser.add_argument(
        "--dedupe-threshold",
        type=int,
        default=None,
        metavar="N",
        help=(
            "pHash Hamming-distance threshold for --dedupe (default: 5). "
            "Lower = stricter (fewer dedupes). Ignored if --dedupe is not set."
        ),
    )
    generate_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    # Enrich command (add frame to existing timeline)
    enrich_parser = subparsers.add_parser(
        "enrich",
        help="Add a frame at a specific timestamp to an existing timeline",
        epilog="""
Examples:
  loomersidian enrich --video video.mp4 --timeline output/my-video/timeline.md --timestamp 00:03
        """,
    )
    enrich_parser.add_argument(
        "--video",
        type=Path,
        required=True,
        metavar="VIDEO",
        help="Path to the Loom MP4 video file",
    )
    enrich_parser.add_argument(
        "--timeline",
        type=Path,
        required=True,
        metavar="FILE",
        help="Path to the existing timeline.md file",
    )
    enrich_parser.add_argument(
        "--timestamp",
        type=str,
        required=True,
        metavar="MM:SS",
        help="Timestamp to extract frame at (e.g., 00:03)",
    )
    enrich_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    # Dedupe command (collapse runs of visually-identical frames)
    dedupe_parser = subparsers.add_parser(
        "dedupe",
        help="Collapse runs of visually-identical adjacent frames in an existing timeline",
        epilog="""
Examples:
  loomersidian dedupe --timeline output/my-video/timeline.md
  loomersidian dedupe --timeline output/my-video/timeline.md --threshold 3
  loomersidian dedupe --timeline output/my-video/timeline.md --dry-run
  loomersidian dedupe --timeline output/my-video/timeline.md --restore
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    dedupe_parser.add_argument(
        "--timeline",
        type=Path,
        required=True,
        metavar="FILE",
        help="Path to the existing timeline.md file",
    )
    dedupe_parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        metavar="N",
        help="pHash Hamming-distance threshold (lower = stricter; default 5)",
    )
    dedupe_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without modifying any files",
    )
    dedupe_parser.add_argument(
        "--restore",
        action="store_true",
        help="Move PNGs from attachments/archive/ back into attachments/ and re-link them",
    )
    dedupe_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser


def validate_generate_inputs(args: argparse.Namespace) -> Optional[str]:
    """Validate inputs for generate command."""
    if not args.input.exists():
        return f"Video file not found: {args.input}"

    if not args.input.suffix.lower() == ".mp4":
        return f"Video must be an MP4 file: {args.input}"

    if not args.transcript.exists():
        return f"Transcript file not found: {args.transcript}"

    if args.min_block is not None and args.min_block <= 0:
        return f"--min-block must be > 0 (got {args.min_block})"
    if args.max_block is not None and args.max_block <= 0:
        return f"--max-block must be > 0 (got {args.max_block})"
    if (
        args.min_block is not None
        and args.max_block is not None
        and args.min_block > args.max_block
    ):
        return (
            f"--min-block ({args.min_block}) must be <= --max-block ({args.max_block})"
        )
    if args.dedupe_threshold is not None and args.dedupe_threshold < 0:
        return f"--dedupe-threshold must be >= 0 (got {args.dedupe_threshold})"
    if args.dedupe_threshold is not None and not args.dedupe:
        # Quietly tolerate? No — surface the silent-flag bug to the user.
        return "--dedupe-threshold requires --dedupe"

    return None


def validate_enrich_inputs(args: argparse.Namespace) -> Optional[str]:
    """Validate inputs for enrich command."""
    if not args.video.exists():
        return f"Video file not found: {args.video}"

    if not args.video.suffix.lower() == ".mp4":
        return f"Video must be an MP4 file: {args.video}"

    if not args.timeline.exists():
        return f"Timeline file not found: {args.timeline}"

    # Validate timestamp format
    import re
    if not re.match(r'^\d{1,2}:\d{2}$', args.timestamp):
        return f"Invalid timestamp format: {args.timestamp}. Expected MM:SS"

    return None


def run_generate(args: argparse.Namespace) -> int:
    """Run the generate pipeline."""
    from loomersidian.enrichment import (
        create_enriched_blocks,
        filter_blocks_in_range,
        parse_zoom_range,
        validate_range_against_video,
    )
    from loomersidian.frames import extract_frames_batch, get_video_duration
    from loomersidian.generator import generate_timeline_document, slugify
    from loomersidian.timeline import normalize_timeline
    from loomersidian.transcript import parse_transcript

    try:
        if args.verbose:
            print(f"Processing video: {args.input}")
            print(f"Using transcript: {args.transcript}")

        # Step 1: Parse transcript
        if args.verbose:
            print("Parsing transcript...")
        entries = parse_transcript(args.transcript)
        if args.verbose:
            print(f"  Found {len(entries)} transcript entries")

        # Step 2: Normalize into time blocks
        if args.verbose:
            cadence_note = ""
            if args.min_block is not None or args.max_block is not None:
                cadence_note = (
                    f" (min={args.min_block}, max={args.max_block})"
                )
            print(f"Normalizing timeline...{cadence_note}")
        blocks = normalize_timeline(
            entries,
            min_block_duration=args.min_block,
            max_block_duration=args.max_block,
        )
        if args.verbose:
            print(f"  Created {len(blocks)} time blocks")

        # Step 2.5: Apply zoom-range enrichment if specified
        if args.zoom_range:
            if args.verbose:
                print(f"Applying zoom enrichment: {args.zoom_range}")

            zoom_start, zoom_end = parse_zoom_range(args.zoom_range)
            video_duration = get_video_duration(args.input)
            validate_range_against_video(zoom_start, zoom_end, video_duration)

            before, in_range, after = filter_blocks_in_range(blocks, zoom_start, zoom_end)
            enriched = create_enriched_blocks(entries, zoom_start, zoom_end)

            if args.verbose:
                print(f"  Enriched {len(in_range)} blocks into {len(enriched)} finer blocks")

            blocks = before + enriched + after

        # Step 3: Create video-specific output folder
        folder_name = slugify(args.input.stem)
        video_output_dir = args.output / folder_name
        video_output_dir.mkdir(parents=True, exist_ok=True)

        # Step 4: Extract frames
        if args.verbose:
            print("Extracting frames...")
        frame_map = extract_frames_batch(args.input, blocks, video_output_dir)
        if args.verbose:
            print(f"  Extracted {len(frame_map)} frames")

        # Step 5: Generate markdown
        if args.verbose:
            print("Generating timeline document...")
        output_path = generate_timeline_document(blocks, frame_map, video_output_dir, args.input.stem)
        print(f"Timeline generated: {output_path}")

        # Step 6 (optional): Dedupe runs of visually-identical adjacent frames.
        # We import lazily so users who never use --dedupe pay no startup cost
        # for Pillow / imagehash.
        if args.dedupe:
            from loomersidian.dedupe import DEFAULT_THRESHOLD, apply_dedupe

            threshold = (
                args.dedupe_threshold
                if args.dedupe_threshold is not None
                else DEFAULT_THRESHOLD
            )
            if args.verbose:
                print(f"Deduping (threshold={threshold})...")
            report = apply_dedupe(output_path, threshold=threshold)
            print(report.format())

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def run_enrich(args: argparse.Namespace) -> int:
    """Run the enrich pipeline to add a frame to existing timeline."""
    from loomersidian.frames import extract_frame
    from loomersidian.generator import parse_timeline_document, update_timeline_document
    from loomersidian.timeline import TimeBlock, insert_block_sorted

    try:
        if args.verbose:
            print(f"Enriching timeline: {args.timeline}")
            print(f"Adding frame at: {args.timestamp}")

        # Parse timestamp
        parts = args.timestamp.split(':')
        target_seconds = int(parts[0]) * 60 + int(parts[1])
        target_timestamp = f"{int(parts[0]):02d}:{int(parts[1]):02d}"

        # Parse existing timeline
        if args.verbose:
            print("Parsing existing timeline...")
        title, blocks_with_frames = parse_timeline_document(args.timeline)

        # Check for duplicate timestamp
        for block, _ in blocks_with_frames:
            if block.start_seconds == target_seconds:
                print(f"Error: Block already exists at {target_timestamp}", file=sys.stderr)
                return 1

        # Extract blocks and frame_map
        blocks = [b for b, _ in blocks_with_frames]
        frame_map = dict(blocks_with_frames)

        if args.verbose:
            print(f"  Found {len(blocks)} existing blocks")

        # Extract single frame
        attachments_dir = args.timeline.parent / "attachments"
        frame_path = attachments_dir / f"frame_{target_seconds:04d}.png"

        if args.verbose:
            print(f"Extracting frame at {target_timestamp}...")
        extract_frame(args.video, target_seconds, frame_path)

        # Create new block with placeholder text
        new_block = TimeBlock(
            start_time=target_timestamp,
            end_time=target_timestamp,
            start_seconds=target_seconds,
            end_seconds=target_seconds,
            text=f"Screenshot at {target_timestamp}"
        )

        # Insert block in sorted order
        blocks = insert_block_sorted(blocks, new_block)
        frame_map[new_block] = frame_path

        # Update timeline document
        if args.verbose:
            print("Updating timeline document...")
        update_timeline_document(args.timeline, blocks, frame_map, title)

        print(f"Added frame at {target_timestamp} to {args.timeline}")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def validate_dedupe_inputs(args: argparse.Namespace) -> Optional[str]:
    """Validate inputs for dedupe command."""
    if not args.timeline.exists():
        return f"Timeline file not found: {args.timeline}"
    if args.threshold is not None and args.threshold < 0:
        return f"--threshold must be >= 0 (got {args.threshold})"
    if args.dry_run and args.restore:
        return "--dry-run and --restore are mutually exclusive"
    return None


def run_dedupe(args: argparse.Namespace) -> int:
    """Run the dedupe pipeline (or its inverse, --restore)."""
    from loomersidian.dedupe import (
        DEFAULT_THRESHOLD,
        apply_dedupe,
        restore_dedupe,
    )

    try:
        if args.restore:
            if args.verbose:
                print(f"Restoring archived frames into {args.timeline.parent}/attachments/")
            report = restore_dedupe(args.timeline)
            print(report.format())
            return 0

        threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLD
        if args.verbose:
            mode = "DRY-RUN" if args.dry_run else "applying"
            print(f"Deduping {args.timeline} ({mode}, threshold={threshold})...")

        report = apply_dedupe(
            args.timeline,
            threshold=threshold,
            dry_run=args.dry_run,
        )
        print(report.format())
        return 0

    except Exception as e:  # noqa: BLE001 — surface any failure to stderr cleanly
        print(f"Error: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # No command specified - show help
    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "generate":
        error = validate_generate_inputs(args)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        return run_generate(args)

    elif args.command == "enrich":
        error = validate_enrich_inputs(args)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        return run_enrich(args)

    elif args.command == "dedupe":
        error = validate_dedupe_inputs(args)
        if error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
        return run_dedupe(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
