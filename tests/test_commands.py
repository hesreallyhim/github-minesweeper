"""Tests for command parsing."""

from __future__ import annotations

from minesweeper.commands import ParsedCommand, parse_command


class TestParseCommand:
    def test_reveal(self):
        cmd = parse_command("/reveal B3")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"

    def test_flag(self):
        cmd = parse_command("/flag A1")
        assert cmd is not None
        assert cmd.action == "flag"
        assert cmd.coordinate == "A1"

    def test_unflag(self):
        cmd = parse_command("/unflag C5")
        assert cmd is not None
        assert cmd.action == "unflag"
        assert cmd.coordinate == "C5"

    def test_chord(self):
        cmd = parse_command("/chord D4")
        assert cmd is not None
        assert cmd.action == "chord"
        assert cmd.coordinate == "D4"

    def test_giveup(self):
        cmd = parse_command("/giveup")
        assert cmd is not None
        assert cmd.action == "giveup"
        assert cmd.coordinate is None

    def test_case_insensitive(self):
        cmd = parse_command("/REVEAL b3")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "b3"

    def test_extra_whitespace(self):
        cmd = parse_command("  /reveal   B3  ")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"

    def test_command_in_sentence(self):
        cmd = parse_command("I want to /reveal B3 please")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"

    def test_implicit_reveal_coordinate_only(self):
        cmd = parse_command("B3")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"

    def test_implicit_reveal_row_col_coordinate(self):
        cmd = parse_command("3B")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "3B"

    def test_implicit_reveal_backticked_coordinate(self):
        cmd = parse_command("`h7`")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "h7"

    def test_implicit_reveal_backticked_row_col_coordinate(self):
        cmd = parse_command("`7h`")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "7h"

    def test_implicit_reveal_requires_coordinate_only_comment(self):
        assert parse_command("I think B3 is safe") is None

    def test_slash_reveal_accepts_row_col_input(self):
        cmd = parse_command("/reveal 3B")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "3B"

    def test_no_command(self):
        assert parse_command("just a regular comment") is None

    def test_empty_string(self):
        assert parse_command("") is None

    def test_unknown_command(self):
        assert parse_command("/explode B3") is None

    def test_first_command_wins(self):
        cmd = parse_command("/reveal B3\n/flag A1")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"

    def test_missing_coordinate(self):
        cmd = parse_command("/reveal")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate is None

    def test_giveup_ignores_trailing(self):
        cmd = parse_command("/giveup now")
        assert cmd is not None
        assert cmd.action == "giveup"
        assert cmd.coordinate is None

    def test_parsed_command_dataclass(self):
        cmd = ParsedCommand(action="reveal", coordinate="B3")
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"
