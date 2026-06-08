"""Pytest fixtures for Loomersidian tests."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_transcript_path(fixtures_dir: Path) -> Path:
    """Return the path to the sample transcript fixture."""
    return fixtures_dir / "sample.transcript"


@pytest.fixture
def sample_transcript_content() -> str:
    """Return sample transcript content for testing."""
    return """0:00
Hey everyone, welcome to this quick design review.

0:08
So I want to walk through the dashboard changes we discussed last week.

0:15
Starting with the sidebar here, you can see it feels pretty heavy.

0:23
I think we need to reduce the number of items visible by default.

0:35
Moving on to the header, the hierarchy is unclear here.

0:45
Users might not know where to click for the main navigation.

0:55
I think we need a clear visual distinction between primary and secondary actions.

1:05
Let me show you what I mean by that.

1:15
See how the buttons here all look the same? That's confusing.

1:25
We should consider icon treatment and color differentiation.

1:35
Alright, that wraps up my feedback for now.
"""


@pytest.fixture
def empty_transcript_content() -> str:
    """Return empty transcript content for testing error handling."""
    return ""


@pytest.fixture
def no_timestamps_content() -> str:
    """Return transcript content without timestamps."""
    return """Just some text without any timestamps.
This should be rejected by the parser.
"""


@pytest.fixture
def malformed_timestamp_content() -> str:
    """Return transcript content with malformed timestamps."""
    return """invalid:timestamp
Some text here.

0:15
Valid timestamp text.
"""
