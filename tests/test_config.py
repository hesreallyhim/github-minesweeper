"""Tests for game configuration loading."""

from __future__ import annotations

from minesweeper.config import DEFAULT_COLS, DEFAULT_MINES, DEFAULT_ROWS, load_config


def test_load_config_returns_dict():
    cfg = load_config()
    assert isinstance(cfg, dict)
    assert "game" in cfg


def test_config_board_defaults():
    cfg = load_config()
    board = cfg["game"]["board"]
    assert board["rows"] == DEFAULT_ROWS
    assert board["cols"] == DEFAULT_COLS
    assert board["mines"] == DEFAULT_MINES


def test_default_constants():
    assert DEFAULT_ROWS == 9
    assert DEFAULT_COLS == 9
    assert DEFAULT_MINES == 10
