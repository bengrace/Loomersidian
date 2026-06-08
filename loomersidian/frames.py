"""Frame extraction from video files for Loomersidian."""

import shutil
from pathlib import Path
from typing import Dict, List

from loomersidian.timeline import TimeBlock


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available on the system."""
    return shutil.which("ffmpeg") is not None


def _import_ffmpeg():
    """Import ffmpeg-python with a helpful error message if not installed."""
    try:
        import ffmpeg
        return ffmpeg
    except ImportError as err:
        raise RuntimeError(
            "ffmpeg-python package not found. Please install it:\n"
            "  pip install ffmpeg-python\n\n"
            "Note: This is different from the ffmpeg binary. You need both:\n"
            "  1. ffmpeg binary: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)\n"
            "  2. ffmpeg-python: pip install ffmpeg-python"
        ) from err


def extract_frame(
    video_path: Path,
    timestamp_seconds: int,
    output_path: Path
) -> Path:
    """Extract a single frame from a video at the specified timestamp.

    Args:
        video_path: Path to the input video file
        timestamp_seconds: Timestamp in seconds to extract frame from
        output_path: Path to save the extracted frame

    Returns:
        Path to the extracted frame

    Raises:
        FileNotFoundError: If video file doesn't exist
        RuntimeError: If ffmpeg fails or is not installed
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    if not check_ffmpeg():
        raise RuntimeError(
            "ffmpeg not found. Please install ffmpeg:\n"
            "  macOS: brew install ffmpeg\n"
            "  Linux: apt-get install ffmpeg"
        )

    ffmpeg = _import_ffmpeg()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Format timestamp for ffmpeg (HH:MM:SS)
    hours = timestamp_seconds // 3600
    minutes = (timestamp_seconds % 3600) // 60
    seconds = timestamp_seconds % 60
    timestamp_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    try:
        (
            ffmpeg
            .input(str(video_path), ss=timestamp_str)
            .output(str(output_path), vframes=1, format='image2', vcodec='png')
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffmpeg error extracting frame: {e}") from e

    return output_path


def extract_frames_batch(
    video_path: Path,
    blocks: List[TimeBlock],
    output_dir: Path
) -> Dict[TimeBlock, Path]:
    """Extract frames for a batch of TimeBlocks.

    Extracts one frame per block at the midpoint timestamp.

    Args:
        video_path: Path to the input video file
        blocks: List of TimeBlock objects
        output_dir: Base output directory

    Returns:
        Dictionary mapping TimeBlock to extracted frame path
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    # Create attachments directory
    attachments_dir = output_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    frame_map: Dict[TimeBlock, Path] = {}

    for block in blocks:
        frame_filename = f"frame_{block.midpoint_timestamp}.png"
        frame_path = attachments_dir / frame_filename

        extract_frame(video_path, block.midpoint_seconds, frame_path)
        frame_map[block] = frame_path

    return frame_map


def get_video_duration(video_path: Path) -> float:
    """Get the duration of a video file in seconds.

    Args:
        video_path: Path to the video file

    Returns:
        Duration in seconds

    Raises:
        FileNotFoundError: If video file doesn't exist
        RuntimeError: If ffprobe fails
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ffmpeg = _import_ffmpeg()

    try:
        probe = ffmpeg.probe(str(video_path))
        duration = float(probe['format']['duration'])
        return duration
    except ffmpeg.Error as e:
        raise RuntimeError(f"ffprobe error: {e}") from e
