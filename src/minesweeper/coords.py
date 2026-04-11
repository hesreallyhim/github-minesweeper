"""Spreadsheet-style coordinate parsing and normalization.

Coordinates use the form <column-letter><row-number>, e.g. B3 or h10.
Column A = 0, Row 1 = 0 internally.
"""

from __future__ import annotations

import re

_COORD_RE = re.compile(r"^([A-Za-z])(\d+)$")


def parse_coord(raw: str, rows: int, cols: int) -> tuple[int, int] | None:
    """Parse a coordinate string into (row, col) or return None if invalid.

    Accepts formats like 'B3', 'a1', 'I9'. Column letters are mapped
    A=0, B=1, ... and row numbers are 1-indexed (1=row 0 internally).
    Returns None for out-of-bounds or malformed input.
    """
    raw = raw.strip()
    m = _COORD_RE.match(raw)
    if not m:
        return None
    col = ord(m.group(1).upper()) - ord("A")
    row = int(m.group(2)) - 1
    if row < 0 or row >= rows or col < 0 or col >= cols:
        return None
    return (row, col)


def coord_to_label(row: int, col: int) -> str:
    """Convert internal (row, col) back to a display label like 'B3'."""
    return f"{chr(ord('A') + col)}{row + 1}"
