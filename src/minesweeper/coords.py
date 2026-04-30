"""Spreadsheet-style coordinate parsing and normalization.

Coordinates use the form <column-letter><row-number>, e.g. B3 or h10.
Column A = 0, Row 1 = 0 internally.
"""

from __future__ import annotations

import re

_COL_ROW_RE = re.compile(r"^([A-Za-z])(\d+)$")
_ROW_COL_RE = re.compile(r"^(\d+)([A-Za-z])$")


def parse_coord(raw: str, rows: int, cols: int) -> tuple[int, int] | None:
    """Parse a coordinate string into (row, col) or return None if invalid.

    Accepts formats like 'B3', '3B', 'a1', '1a', 'I9'. Column letters are
    mapped A=0, B=1, ... and row numbers are 1-indexed (1=row 0 internally).
    Returns None for out-of-bounds or malformed input.
    """
    raw = raw.strip()
    col_row = _COL_ROW_RE.match(raw)
    row_col = _ROW_COL_RE.match(raw)
    if col_row:
        col = ord(col_row.group(1).upper()) - ord("A")
        row = int(col_row.group(2)) - 1
    elif row_col:
        row = int(row_col.group(1)) - 1
        col = ord(row_col.group(2).upper()) - ord("A")
    else:
        return None
    if row < 0 or row >= rows or col < 0 or col >= cols:
        return None
    return (row, col)


def coord_to_label(row: int, col: int) -> str:
    """Convert internal (row, col) back to a display label like 'B3'."""
    return f"{chr(ord('A') + col)}{row + 1}"
