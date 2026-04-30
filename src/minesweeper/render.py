"""Board and room status rendering for GitHub issue comments.

Produces fenced monospace board output and authored response templates
per the rendering contract in docs/v1-game-contract.md.

Bot response sections:
  1. Room/status heading
  2. Result sentence for the move
  3. Rendered board
  4. Stats line (mines remaining, cells revealed)
  5. Short command reminder (when useful)
  6. Hidden state marker comment (appended by room_service)
"""

from __future__ import annotations

from typing import Callable

from minesweeper.coords import coord_to_label
from minesweeper.engine import Board, Phase

# Symbol map per v1-game-contract rendering contract
SYMBOLS = {
    "hidden": "\u2b1c",   # ⬜ white square
    "flag": "\U0001f6a9",     # 🚩 flag
    "mine": "\U0001f4a3",     # 💣 bomb
    "exploded": "\U0001f4a5", # 💥 explosion
    "empty": "\u00b7",    # · middle dot
}

COMMAND_REMINDER = (
    "**Commands:** `A1 B2` \u00b7 `flag H7 H8` \u00b7 "
    "`unflag H7` \u00b7 `giveup`"
)


def render_board(board: Board, *, reveal_all: bool = False) -> str:
    """Render the board as a fenced code block for GitHub comments.

    When reveal_all is True (game over), mines are shown.
    """
    cols = board.cols
    # Column headers: A B C ...
    col_headers = " ".join(chr(65 + c) for c in range(cols))
    # Pad row numbers to 2 chars for alignment
    lines = [f"   {col_headers}"]
    for r in range(board.rows):
        row_label = f"{r + 1:2d}"
        cells = []
        for c in range(cols):
            display = board.get_cell_display(r, c, reveal_all=reveal_all)
            cells.append(_symbol(display))
        lines.append(f"{row_label} {' '.join(cells)}")
    board_text = "\n".join(lines)
    return f"```\n{board_text}\n```"


def render_board_table(
    board: Board,
    *,
    reveal_all: bool = False,
    hidden_cell_link: Callable[[str], str] | None = None,
) -> str:
    """Render the board as a GitHub Markdown table.

    If ``hidden_cell_link`` is provided, hidden cells become clickable links.
    """
    headers = [chr(65 + c) for c in range(board.cols)]
    lines = [
        "|   | " + " | ".join(headers) + " |",
        "|" + "---|" * (board.cols + 1),
    ]
    for r in range(board.rows):
        row_cells: list[str] = []
        for c in range(board.cols):
            display = board.get_cell_display(r, c, reveal_all=reveal_all)
            label = coord_to_label(r, c)
            row_cells.append(_table_cell(display, label, hidden_cell_link))
        lines.append(f"| {r + 1} | " + " | ".join(row_cells) + " |")
    return "\n".join(lines)


def _table_cell(
    display: str,
    label: str,
    hidden_cell_link: Callable[[str], str] | None,
) -> str:
    """Render one table cell for issue-comment Markdown."""
    if display == "hidden":
        if hidden_cell_link is not None:
            return f"[`{label}`]({hidden_cell_link(label)})"
        return f"`{label}`"
    if display == "empty":
        return "·"
    if display == "flag":
        return "\U0001f6a9"
    if display == "mine":
        return "\U0001f4a3"
    if display == "exploded":
        return "\U0001f4a5"
    # Numbered cells: "1" through "8"
    return f"**{display}**"


def _symbol(display: str) -> str:
    """Map a cell display string to its rendering symbol."""
    if display in SYMBOLS:
        return SYMBOLS[display]
    # Numbered cells: display is "1" through "8"
    return display


def render_room_header(owner: str, issue_number: int, phase: Phase) -> str:
    """Render the room status heading."""
    phase_labels = {
        Phase.PLAYING: "\u26cf\ufe0f In Progress",
        Phase.WON: "\U0001f3c6 You Win!",
        Phase.LOST: "\U0001f4a5 Game Over",
        Phase.GIVEN_UP: "\U0001f3f3\ufe0f Abandoned",
    }
    status = phase_labels.get(phase, "Unknown")
    return f"### Minesweeper Room #{issue_number} \u2014 {status}"


def render_stats(board: Board) -> str:
    """Render a stats line showing mines remaining and cells revealed."""
    flag_count = len(board.flagged_set)
    mines_remaining = board.num_mines - flag_count
    revealed_count = len(board.revealed_set)
    return (
        f"Mines remaining: **{mines_remaining}** | "
        f"Cells revealed: **{revealed_count}**"
    )


def render_non_owner_response(sender: str) -> str:
    """Render a polite rejection for a non-owner command."""
    return (
        f"Sorry @{sender}, only the room owner can play in this game. "
        "Open your own issue to start a new room!"
    )


def render_malformed_command(text: str) -> str:
    """Render help text for an unrecognized command."""
    return (
        "I didn't recognize a valid command. Available commands:\n\n"
        "- `A1 B2` or `guess A1 A2` \u2014 reveal cell(s)\n"
        "- `flag H7 H8` \u2014 flag suspected mine(s)\n"
        "- `unflag H7` \u2014 remove flag(s)\n"
        "- `giveup` \u2014 end the game\n\n"
        "Use one action per line (e.g. `flag A1 A4` on one line, "
        "`reveal B3` on the next).\n"
        "Any unrecognized token invalidates the whole turn.\n"
        "Slash prefixes are optional (for example, `/flag A1`)."
    )


def render_game_over_notice(phase: Phase) -> str:
    """Render a notice for commands on a finished game."""
    phase_labels = {
        Phase.WON: "won",
        Phase.LOST: "lost",
        Phase.GIVEN_UP: "given up",
    }
    phase_str = phase_labels.get(phase, "over")
    return (
        f"This game is already **{phase_str}**. "
        "Open a new issue to start another game."
    )


def format_room_open(
    header: str,
    board_text: str,
    stats: str,
    mines: int,
) -> str:
    """Assemble the full bot comment for a new room (no state token yet)."""
    return (
        f"{header}\n\n"
        f"Welcome to your Minesweeper room! A **9\u00d79** board with "
        f"**{mines}** hidden mines has been generated.\n\n"
        f"{board_text}\n\n"
        f"{stats}\n\n"
        f"{COMMAND_REMINDER}"
    )


def format_move_response(
    header: str,
    message: str,
    board_text: str,
    stats: str,
    phase: Phase,
) -> str:
    """Assemble the full bot comment for a move response (no state token yet)."""
    parts = [header, "", message, "", board_text, "", stats]
    # Show command reminder only while the game is still active
    if phase == Phase.PLAYING:
        parts.extend(["", COMMAND_REMINDER])
    return "\n".join(parts)
