"""Tests for coordinate parsing and normalization."""

from __future__ import annotations

from minesweeper.coords import coord_to_label, parse_coord


class TestParseCoord:
    def test_valid_a1(self):
        assert parse_coord("A1", rows=9, cols=9) == (0, 0)

    def test_valid_i9(self):
        assert parse_coord("I9", rows=9, cols=9) == (8, 8)

    def test_valid_b3(self):
        assert parse_coord("B3", rows=9, cols=9) == (2, 1)

    def test_valid_row_col_3b(self):
        assert parse_coord("3B", rows=9, cols=9) == (2, 1)

    def test_case_insensitive(self):
        assert parse_coord("b3", rows=9, cols=9) == (2, 1)
        assert parse_coord("B3", rows=9, cols=9) == (2, 1)
        assert parse_coord("3b", rows=9, cols=9) == (2, 1)

    def test_whitespace_tolerance(self):
        assert parse_coord("  B3  ", rows=9, cols=9) == (2, 1)

    def test_out_of_bounds_col(self):
        assert parse_coord("J1", rows=9, cols=9) is None

    def test_out_of_bounds_row(self):
        assert parse_coord("A10", rows=9, cols=9) is None

    def test_row_zero_invalid(self):
        assert parse_coord("A0", rows=9, cols=9) is None

    def test_empty_string(self):
        assert parse_coord("", rows=9, cols=9) is None

    def test_garbage(self):
        assert parse_coord("xyz123", rows=9, cols=9) is None

    def test_number_only(self):
        assert parse_coord("3", rows=9, cols=9) is None

    def test_letter_only(self):
        assert parse_coord("B", rows=9, cols=9) is None

    def test_multi_letter(self):
        assert parse_coord("AB3", rows=9, cols=9) is None


class TestCoordToLabel:
    def test_origin(self):
        assert coord_to_label(0, 0) == "A1"

    def test_b3(self):
        assert coord_to_label(2, 1) == "B3"

    def test_i9(self):
        assert coord_to_label(8, 8) == "I9"

    def test_roundtrip(self):
        for r in range(9):
            for c in range(9):
                label = coord_to_label(r, c)
                assert parse_coord(label, rows=9, cols=9) == (r, c)
