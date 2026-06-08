"""Tests for CLI interface."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from loomersidian.cli import create_parser, main, validate_enrich_inputs, validate_generate_inputs


class TestCreateParser:
    """Tests for argument parser creation."""

    def test_parser_has_generate_subcommand(self):
        parser = create_parser()

        # Parse with generate subcommand and all required args
        args = parser.parse_args([
            "generate",
            "-i", "video.mp4",
            "-t", "transcript.txt",
            "-o", "./output"
        ])

        assert args.command == "generate"
        assert args.input == Path("video.mp4")
        assert args.transcript == Path("transcript.txt")
        assert args.output == Path("./output")

    def test_long_form_arguments(self):
        parser = create_parser()

        args = parser.parse_args([
            "generate",
            "--input", "video.mp4",
            "--transcript", "transcript.txt",
            "--output", "./output"
        ])

        assert args.input == Path("video.mp4")
        assert args.transcript == Path("transcript.txt")
        assert args.output == Path("./output")

    def test_optional_zoom_range(self):
        parser = create_parser()

        args = parser.parse_args([
            "generate",
            "-i", "video.mp4",
            "-t", "transcript.txt",
            "-o", "./output",
            "--zoom-range", "01:05-01:25"
        ])

        assert args.zoom_range == "01:05-01:25"

    def test_optional_verbose(self):
        parser = create_parser()

        # Without verbose
        args = parser.parse_args([
            "generate",
            "-i", "video.mp4",
            "-t", "transcript.txt",
            "-o", "./output"
        ])
        assert args.verbose is False

        # With verbose
        args = parser.parse_args([
            "generate",
            "-i", "video.mp4",
            "-t", "transcript.txt",
            "-o", "./output",
            "-v"
        ])
        assert args.verbose is True

    def test_missing_required_argument(self):
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["generate", "-i", "video.mp4"])  # Missing -t and -o

    def test_enrich_subcommand(self):
        parser = create_parser()

        args = parser.parse_args([
            "enrich",
            "--video", "video.mp4",
            "--timeline", "timeline.md",
            "--timestamp", "00:03"
        ])

        assert args.command == "enrich"
        assert args.video == Path("video.mp4")
        assert args.timeline == Path("timeline.md")
        assert args.timestamp == "00:03"


class TestValidateGenerateInputs:
    """Tests for generate input validation."""

    @staticmethod
    def _make_args(video, transcript, **overrides):
        """Build a MagicMock args namespace with the new optional flags
        defaulted to None / False, mirroring argparse defaults."""
        args = MagicMock()
        args.input = video
        args.transcript = transcript
        args.min_block = overrides.get("min_block")
        args.max_block = overrides.get("max_block")
        args.dedupe = overrides.get("dedupe", False)
        args.dedupe_threshold = overrides.get("dedupe_threshold")
        return args

    def test_valid_inputs(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        transcript = tmp_path / "test.txt"
        transcript.write_text("0:00\nHello")

        args = self._make_args(video, transcript)

        error = validate_generate_inputs(args)
        assert error is None

    def test_video_not_found(self, tmp_path):
        transcript = tmp_path / "test.txt"
        transcript.write_text("0:00\nHello")

        args = self._make_args(tmp_path / "nonexistent.mp4", transcript)

        error = validate_generate_inputs(args)
        assert "Video file not found" in error

    def test_video_wrong_extension(self, tmp_path):
        video = tmp_path / "test.avi"
        video.write_bytes(b"fake video")
        transcript = tmp_path / "test.txt"
        transcript.write_text("0:00\nHello")

        args = self._make_args(video, transcript)

        error = validate_generate_inputs(args)
        assert "must be an MP4 file" in error

    def test_transcript_not_found(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")

        args = self._make_args(video, tmp_path / "nonexistent.txt")

        error = validate_generate_inputs(args)
        assert "Transcript file not found" in error

    # --- New flags: --min-block / --max-block / --dedupe-* -------------------

    def _valid_files(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        transcript = tmp_path / "test.txt"
        transcript.write_text("0:00\nHello")
        return video, transcript

    def test_min_block_must_be_positive(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(video, transcript, min_block=0)
        assert "must be > 0" in validate_generate_inputs(args)

    def test_max_block_must_be_positive(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(video, transcript, max_block=-1)
        assert "must be > 0" in validate_generate_inputs(args)

    def test_min_block_cannot_exceed_max_block(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(video, transcript, min_block=20, max_block=10)
        error = validate_generate_inputs(args)
        assert error is not None
        assert "must be <=" in error

    def test_block_overrides_accepted(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(video, transcript, min_block=10, max_block=30)
        assert validate_generate_inputs(args) is None

    def test_dedupe_threshold_requires_dedupe(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(video, transcript, dedupe_threshold=3)
        error = validate_generate_inputs(args)
        assert error == "--dedupe-threshold requires --dedupe"

    def test_dedupe_threshold_must_be_non_negative(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(
            video, transcript, dedupe=True, dedupe_threshold=-2
        )
        assert "must be >= 0" in validate_generate_inputs(args)

    def test_dedupe_with_threshold_is_valid(self, tmp_path):
        video, transcript = self._valid_files(tmp_path)
        args = self._make_args(
            video, transcript, dedupe=True, dedupe_threshold=3
        )
        assert validate_generate_inputs(args) is None


class TestValidateEnrichInputs:
    """Tests for enrich input validation."""

    def test_valid_inputs(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        timeline = tmp_path / "timeline.md"
        timeline.write_text("# Test")

        args = MagicMock()
        args.video = video
        args.timeline = timeline
        args.timestamp = "00:03"

        error = validate_enrich_inputs(args)
        assert error is None

    def test_invalid_timestamp_format(self, tmp_path):
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        timeline = tmp_path / "timeline.md"
        timeline.write_text("# Test")

        args = MagicMock()
        args.video = video
        args.timeline = timeline
        args.timestamp = "invalid"

        error = validate_enrich_inputs(args)
        assert "Invalid timestamp format" in error


class TestMain:
    """Tests for main entry point."""

    def test_returns_error_for_invalid_inputs(self, tmp_path, monkeypatch):
        # Simulate running with non-existent files
        monkeypatch.setattr(
            "sys.argv",
            ["loomersidian", "generate", "-i", "nonexistent.mp4", "-t", "transcript.txt", "-o", str(tmp_path)]
        )

        result = main()
        assert result == 1

    def test_returns_success_with_mocked_pipeline(self, tmp_path, monkeypatch):
        # Create valid input files
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        transcript = tmp_path / "test.txt"
        transcript.write_text("0:00\nHello world")
        output = tmp_path / "output"

        monkeypatch.setattr(
            "sys.argv",
            ["loomersidian", "generate", "-i", str(video), "-t", str(transcript), "-o", str(output)]
        )

        # Mock the pipeline components to avoid needing ffmpeg
        with patch("loomersidian.transcript.parse_transcript") as mock_parse:
            with patch("loomersidian.timeline.normalize_timeline") as mock_normalize:
                with patch("loomersidian.frames.extract_frames_batch") as mock_extract:
                    with patch("loomersidian.generator.generate_timeline_document") as mock_gen:
                        # Set up mock returns
                        mock_entry = MagicMock()
                        mock_entry.seconds = 0
                        mock_entry.timestamp = "00:00"
                        mock_entry.text = "Hello"
                        mock_parse.return_value = [mock_entry]

                        mock_block = MagicMock()
                        mock_normalize.return_value = [mock_block]

                        mock_extract.return_value = {mock_block: Path("frame.png")}

                        mock_gen.return_value = output / "timeline.md"

                        result = main()
                        assert result == 0

    def test_dedupe_flag_invokes_apply_dedupe(self, tmp_path, monkeypatch):
        """The --dedupe flag on `generate` should call apply_dedupe with the
        produced timeline path and the configured threshold."""
        video = tmp_path / "test.mp4"
        video.write_bytes(b"fake video")
        transcript = tmp_path / "test.txt"
        transcript.write_text("0:00\nHello world")
        output = tmp_path / "output"

        monkeypatch.setattr(
            "sys.argv",
            [
                "loomersidian", "generate",
                "-i", str(video),
                "-t", str(transcript),
                "-o", str(output),
                "--dedupe",
                "--dedupe-threshold", "3",
            ],
        )

        produced_timeline = output / "timeline.md"

        with patch("loomersidian.transcript.parse_transcript") as mock_parse, \
             patch("loomersidian.timeline.normalize_timeline") as mock_normalize, \
             patch("loomersidian.frames.extract_frames_batch") as mock_extract, \
             patch("loomersidian.generator.generate_timeline_document") as mock_gen, \
             patch("loomersidian.dedupe.apply_dedupe") as mock_dedupe:

            mock_entry = MagicMock(seconds=0, timestamp="00:00", text="Hello")
            mock_parse.return_value = [mock_entry]
            mock_block = MagicMock()
            mock_normalize.return_value = [mock_block]
            mock_extract.return_value = {mock_block: Path("frame.png")}
            mock_gen.return_value = produced_timeline

            # apply_dedupe returns a report-like object whose .format() prints
            mock_report = MagicMock()
            mock_report.format.return_value = "Dedupe summary"
            mock_dedupe.return_value = mock_report

            result = main()

        assert result == 0
        mock_dedupe.assert_called_once_with(produced_timeline, threshold=3)

    def test_no_command_shows_help(self, monkeypatch, capsys):
        monkeypatch.setattr("sys.argv", ["loomersidian"])
        result = main()
        assert result == 0


class TestZoomRangeIntegration:
    """Tests for zoom-range CLI integration."""

    def test_zoom_range_parsed_correctly(self):
        parser = create_parser()

        args = parser.parse_args([
            "generate",
            "-i", "video.mp4",
            "-t", "transcript.txt",
            "-o", "./output",
            "--zoom-range", "00:30-01:00"
        ])

        assert args.zoom_range == "00:30-01:00"

    def test_zoom_range_with_en_dash(self):
        parser = create_parser()

        args = parser.parse_args([
            "generate",
            "-i", "video.mp4",
            "-t", "transcript.txt",
            "-o", "./output",
            "--zoom-range", "00:30\u201301:00"  # en-dash
        ])

        assert args.zoom_range == "00:30\u201301:00"
