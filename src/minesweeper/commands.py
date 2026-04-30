"""Command parsing for issue comment input.

Supports slash and non-slash commands with optional batching:
- reveal / guess
- flag
- unflag
- giveup

Examples:
- ``/flag A1 B2``
- ``guess A1 A2``
- ``A1 A2 B1`` (implicit reveal/guess)
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_ACTION_ALIASES: dict[str, str] = {
    "reveal": "reveal",
    "guess": "reveal",
    "flag": "flag",
    "unflag": "unflag",
    "giveup": "giveup",
}
_COORD_TOKEN_RE = re.compile(r"`?([A-Za-z]\d+|\d+[A-Za-z])`?$")


@dataclass
class ParsedCommand:
    """A parsed player command."""
    action: str          # reveal, flag, unflag, giveup
    coordinate: str | None  # raw coordinate string, None for giveup


@dataclass(frozen=True)
class ParsedTurn:
    """A parsed turn, potentially containing multiple commands."""

    commands: list[ParsedCommand]


def _parse_action_token(token: str) -> str | None:
    """Parse a command token with optional slash prefix."""
    raw = token.strip().lower()
    if raw.startswith("/"):
        raw = raw[1:]
    if not raw.isalpha():
        return None
    return _ACTION_ALIASES.get(raw)


def _parse_implicit_coordinate(token: str) -> str | None:
    """Parse an implicit coordinate token."""
    match = _COORD_TOKEN_RE.fullmatch(token.strip())
    if match is None:
        return None
    return match.group(1)


def parse_turn(text: str) -> ParsedTurn | None:
    """Parse a comment into one or more commands, or return None.

    The parser is line-oriented:
    - Explicit commands may be slash or non-slash (e.g. ``/flag`` or ``flag``).
    - Explicit commands may target multiple coordinates in one line.
    - Bare coordinate lists are treated as implicit reveal actions.
    """
    commands: list[ParsedCommand] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        action = _parse_action_token(tokens[0])
        if action is not None:
            if action == "giveup":
                if len(tokens) > 1:
                    return None
                commands.append(ParsedCommand(action="giveup", coordinate=None))
                continue

            if len(tokens) == 1:
                commands.append(ParsedCommand(action=action, coordinate=None))
                continue

            for token in tokens[1:]:
                # Enforce one action keyword per line. Mixed forms like
                # "flag A1 reveal B2" are treated as malformed input.
                if _parse_action_token(token) is not None:
                    return None
                coord = _parse_implicit_coordinate(token)
                if coord is None:
                    return None
                commands.append(
                    ParsedCommand(
                        action=action,
                        coordinate=coord,
                    )
                )
            continue

        implicit_coords: list[str] = []
        for token in tokens:
            coord = _parse_implicit_coordinate(token)
            if coord is None:
                return None
            implicit_coords.append(coord)
        commands.extend(
            ParsedCommand(action="reveal", coordinate=coord)
            for coord in implicit_coords
        )

    if not commands:
        return None
    return ParsedTurn(commands=commands)


def parse_command(text: str) -> ParsedCommand | None:
    """Backward-compatible single-command parser.

    Returns the first parsed command from :func:`parse_turn`, or None.
    """
    turn = parse_turn(text)
    if turn is None:
        return None
    if not turn.commands:
        return None
    return turn.commands[0]
