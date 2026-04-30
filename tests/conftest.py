"""Shared pytest fixtures for the minesweeper test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "github"


@pytest.fixture
def fixture_dir() -> Path:
    """Return the path to the GitHub event fixtures directory."""
    return FIXTURES_DIR


def load_fixture(name: str) -> dict:
    """Load a JSON fixture by filename from the github fixtures directory."""
    with open(FIXTURES_DIR / name) as fh:
        return json.load(fh)
