"""Game configuration loaded from config.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and return the game configuration dictionary."""
    cfg_path = path or Path(os.environ.get("MINESWEEPER_CONFIG", str(_CONFIG_PATH)))
    with open(cfg_path) as fh:
        return yaml.safe_load(fh)


# V1 board preset defaults (from config.yaml / v1-game-contract)
DEFAULT_ROWS = 9
DEFAULT_COLS = 9
DEFAULT_MINES = 10
