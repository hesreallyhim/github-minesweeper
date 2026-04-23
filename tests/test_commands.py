"""Tests for turn parsing."""

from __future__ import annotations

from minesweeper.commands import ParsedCommand, parse_command, parse_turn


class TestParseTurn:
    def test_single_reveal_slash(self):
        turn = parse_turn("/reveal B3")
        assert turn is not None
        assert turn.commands == [ParsedCommand(action="reveal", coordinate="B3")]

    def test_single_guess_no_slash(self):
        turn = parse_turn("guess b3")
        assert turn is not None
        assert turn.commands == [ParsedCommand(action="reveal", coordinate="b3")]

    def test_commands_are_case_insensitive(self):
        turn = parse_turn("FlAg a1 B2")
        assert turn is not None
        assert turn.commands == [
            ParsedCommand(action="flag", coordinate="a1"),
            ParsedCommand(action="flag", coordinate="B2"),
        ]

    def test_flag_multiple_cells_same_line(self):
        turn = parse_turn("/flag A1 B2")
        assert turn is not None
        assert turn.commands == [
            ParsedCommand(action="flag", coordinate="A1"),
            ParsedCommand(action="flag", coordinate="B2"),
        ]

    def test_implicit_multi_cell_reveal(self):
        turn = parse_turn("A1 A2 B1")
        assert turn is not None
        assert turn.commands == [
            ParsedCommand(action="reveal", coordinate="A1"),
            ParsedCommand(action="reveal", coordinate="A2"),
            ParsedCommand(action="reveal", coordinate="B1"),
        ]

    def test_mixed_actions_in_one_turn(self):
        turn = parse_turn("/guess A1 A2\nflag B1")
        assert turn is not None
        assert turn.commands == [
            ParsedCommand(action="reveal", coordinate="A1"),
            ParsedCommand(action="reveal", coordinate="A2"),
            ParsedCommand(action="flag", coordinate="B1"),
        ]

    def test_rejects_mixed_actions_on_same_line(self):
        assert parse_turn("flag A1 A4 reveal B3") is None
        assert parse_turn("/flag A1 /guess B3") is None

    def test_rejects_non_parseable_token_in_explicit_command(self):
        assert parse_turn("reveal A1 B2 3") is None

    def test_command_without_coordinates_is_invalid_but_parsed(self):
        turn = parse_turn("flag")
        assert turn is not None
        assert turn.commands == [ParsedCommand(action="flag", coordinate=None)]

    def test_supports_unflag(self):
        turn = parse_turn("unflag H7 H8")
        assert turn is not None
        assert turn.commands == [
            ParsedCommand(action="unflag", coordinate="H7"),
            ParsedCommand(action="unflag", coordinate="H8"),
        ]

    def test_giveup_rejects_trailing_tokens(self):
        assert parse_turn("/giveup now please") is None

    def test_unknown_command_rejected(self):
        assert parse_turn("/explode B3") is None

    def test_implicit_requires_coordinate_tokens(self):
        assert parse_turn("I think B3 is safe") is None

    def test_chord_not_supported(self):
        assert parse_turn("/chord C4") is None
        assert parse_turn("chord C4") is None

    def test_empty_text_returns_none(self):
        assert parse_turn("") is None


class TestParseCommandCompatibility:
    def test_parse_command_returns_first_command(self):
        cmd = parse_command("/flag A1 B2")
        assert cmd is not None
        assert cmd.action == "flag"
        assert cmd.coordinate == "A1"

    def test_parse_command_preserves_implicit_single_cell(self):
        cmd = parse_command("B3")
        assert cmd is not None
        assert cmd.action == "reveal"
        assert cmd.coordinate == "B3"
