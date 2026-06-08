"""Tests for Markdown generation."""


from loomersidian.generator import (
    generate_timeline_document,
    render_block,
    slugify,
    validate_timeline_document,
)
from loomersidian.timeline import TimeBlock


class TestSlugify:
    """Tests for text slugification."""

    def test_simple_text(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert slugify("Design Review: Phase 2!") == "design-review-phase-2"

    def test_underscores(self):
        assert slugify("my_video_file") == "my-video-file"

    def test_multiple_spaces(self):
        assert slugify("too   many    spaces") == "too-many-spaces"

    def test_leading_trailing(self):
        assert slugify("  spaced  ") == "spaced"

    def test_numbers(self):
        assert slugify("Version 2.0") == "version-20"


class TestRenderBlock:
    """Tests for single block rendering."""

    def test_basic_render(self, tmp_path):
        block = TimeBlock(
            start_time="00:30",
            end_time="00:40",
            start_seconds=30,
            end_seconds=40,
            text="This is the transcript text."
        )
        frame_path = tmp_path / "frame_0035.png"

        result = render_block(block, frame_path)

        # Check timestamp header with en-dash
        assert "## 00:30\u201300:40" in result
        # Check image embed
        assert "![[attachments/frame_0035.png]]" in result
        # Check quoted transcript
        assert '"This is the transcript text."' in result

    def test_uses_en_dash(self, tmp_path):
        block = TimeBlock(
            start_time="01:00",
            end_time="01:10",
            start_seconds=60,
            end_seconds=70,
            text="Test"
        )
        frame_path = tmp_path / "frame_0105.png"

        result = render_block(block, frame_path)

        # Verify en-dash (not hyphen) is used
        assert "\u2013" in result
        assert "01:00-01:10" not in result  # No regular hyphen


class TestGenerateTimelineDocument:
    """Tests for full document generation."""

    def test_creates_timeline_in_provided_folder(self, tmp_path):
        """Test that generate_timeline_document writes to the provided folder."""
        blocks = [
            TimeBlock(
                start_time="00:00",
                end_time="00:10",
                start_seconds=0,
                end_seconds=10,
                text="First block"
            )
        ]

        # Simulate CLI behavior: create video folder with attachments
        video_dir = tmp_path / "test-video"
        video_dir.mkdir()
        attachments = video_dir / "attachments"
        attachments.mkdir()
        frame_path = attachments / "frame_0005.png"
        frame_path.write_bytes(b"fake png")

        frame_map = {blocks[0]: frame_path}

        output_path = generate_timeline_document(
            blocks, frame_map, video_dir, "Test Video"
        )

        # Check timeline.md was created in the provided folder
        assert output_path == video_dir / "timeline.md"
        assert output_path.exists()

    def test_document_has_title(self, tmp_path):
        blocks = [
            TimeBlock(
                start_time="00:00",
                end_time="00:10",
                start_seconds=0,
                end_seconds=10,
                text="Content"
            )
        ]

        # Simulate CLI behavior: video folder already exists with attachments
        video_dir = tmp_path / "my-design-review"
        video_dir.mkdir()
        attachments = video_dir / "attachments"
        attachments.mkdir()
        frame_path = attachments / "frame_0005.png"
        frame_path.write_bytes(b"fake png")

        frame_map = {blocks[0]: frame_path}

        output_path = generate_timeline_document(
            blocks, frame_map, video_dir, "My Design Review"
        )

        content = output_path.read_text()
        assert content.startswith("# My Design Review")


class TestValidateTimelineDocument:
    """Tests for document validation."""

    def test_missing_file(self, tmp_path):
        errors = validate_timeline_document(tmp_path / "nonexistent.md")
        assert "does not exist" in errors[0]

    def test_valid_document(self, tmp_path):
        doc_dir = tmp_path / "test-doc"
        doc_dir.mkdir()
        attachments = doc_dir / "attachments"
        attachments.mkdir()

        # Create frame file
        (attachments / "frame_0035.png").write_bytes(b"fake png")

        # Create valid document
        doc_content = """# Test Document

## 00:30\u201300:40
![[attachments/frame_0035.png]]
"Transcript text here."

"""
        doc_path = doc_dir / "timeline.md"
        doc_path.write_text(doc_content)

        errors = validate_timeline_document(doc_path)
        assert len(errors) == 0

    def test_missing_title(self, tmp_path):
        doc_dir = tmp_path / "test-doc"
        doc_dir.mkdir()

        doc_content = """## 00:30\u201300:40
![[attachments/frame_0035.png]]
"Text"
"""
        doc_path = doc_dir / "timeline.md"
        doc_path.write_text(doc_content)

        errors = validate_timeline_document(doc_path)
        assert any("title" in e.lower() for e in errors)
