"""Command parsing for issue comment input.

Supports: /reveal, /flag, /unflag, /chord, /giveup
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Match the first /command in the text, with optional coordinate
_CMD_RE = re.compile(
    r"/(reveal|flag|unflag|chord|giveup)\b\s*(\S*)",
    re.IGNORECASE,
)


@dataclass
class ParsedCommand:
    """A parsed player command."""
    action: str          # reveal, flag, unflag, chord, giveup
    coordinate: str | None  # raw coordinate string, None for giveup


def parse_command(text: str) -> ParsedCommand | None:
    """Parse the first recognized command from comment text, or None.

    Commands are case-insensitive. Only the first match is honored.
    Returns None if no recognized command is found.
    """
    m = _CMD_RE.search(text)
    if not m:
        return None
    action = m.group(1).lower()
    raw_coord = m.group(2).strip() if m.group(2) else None
    if action == "giveup":
        return ParsedCommand(action=action, coordinate=None)
    if not raw_coord:
        return ParsedCommand(action=action, coordinate=None)
    return ParsedCommand(action=action, coordinate=raw_coord)
