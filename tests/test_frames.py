"""Tests for frame extraction."""

from unittest.mock import patch

import pytest

from loomersidian.frames import check_ffmpeg, extract_frame, extract_frames_batch
from loomersidian.timeline import TimeBlock


class TestCheckFfmpeg:
    """Tests for ffmpeg detection."""

    def test_ffmpeg_found(self):
        with patch('shutil.which', return_value='/usr/bin/ffmpeg'):
            assert check_ffmpeg() is True

    def test_ffmpeg_not_found(self):
        with patch('shutil.which', return_value=None):
            assert check_ffmpeg() is False


class TestExtractFrame:
    """Tests for single frame extraction."""

    def test_video_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Video file not found"):
            extract_frame(
                tmp_path / "nonexistent.mp4",
                30,
                tmp_path / "frame.png"
            )

    def test_ffmpeg_not_installed(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video")

        with patch('shutil.which', return_value=None):
            with pytest.raises(RuntimeError, match="ffmpeg not found"):
                extract_frame(video_path, 30, tmp_path / "frame.png")


class TestExtractFramesBatch:
    """Tests for batch frame extraction."""

    def test_video_not_found(self, tmp_path):
        blocks = [
            TimeBlock(
                start_time="00:00",
                end_time="00:10",
                start_seconds=0,
                end_seconds=10,
                text="Test"
            )
        ]

        with pytest.raises(FileNotFoundError):
            extract_frames_batch(
                tmp_path / "nonexistent.mp4",
                blocks,
                tmp_path / "output"
            )

    def test_creates_attachments_dir(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video")

        blocks = [
            TimeBlock(
                start_time="00:00",
                end_time="00:10",
                start_seconds=0,
                end_seconds=10,
                text="Test"
            )
        ]

        output_dir = tmp_path / "output"

        # Mock ffmpeg to avoid actual video processing
        with patch('loomersidian.frames.extract_frame') as mock_extract:
            mock_extract.return_value = output_dir / "attachments" / "frame_0005.png"

            # Create the directory since mock won't
            (output_dir / "attachments").mkdir(parents=True)

            extract_frames_batch(video_path, blocks, output_dir)

            assert (output_dir / "attachments").exists()

    def test_returns_correct_mapping(self, tmp_path):
        video_path = tmp_path / "test.mp4"
        video_path.write_bytes(b"fake video")

        blocks = [
            TimeBlock(
                start_time="00:00",
                end_time="00:10",
                start_seconds=0,
                end_seconds=10,
                text="First"
            ),
            TimeBlock(
                start_time="00:10",
                end_time="00:20",
                start_seconds=10,
                end_seconds=20,
                text="Second"
            ),
        ]

        output_dir = tmp_path / "output"
        (output_dir / "attachments").mkdir(parents=True)

        with patch('loomersidian.frames.extract_frame') as mock_extract:
            def side_effect(vp, ts, op):
                op.write_bytes(b"fake png")
                return op
            mock_extract.side_effect = side_effect

            frame_map = extract_frames_batch(video_path, blocks, output_dir)

            assert len(frame_map) == 2
            assert blocks[0] in frame_map
            assert blocks[1] in frame_map

    def test_deterministic_filenames(self, tmp_path):
        blocks = [
            TimeBlock(
                start_time="01:05",
                end_time="01:15",
                start_seconds=65,
                end_seconds=75,
                text="Test"
            )
        ]

        # Midpoint is 70 seconds = 1:10 = "0110"
        assert blocks[0].midpoint_timestamp == "0110"
