"""Lightweight repo-native leaderboard / hall of fame.

Generates a Markdown leaderboard table from completed game data.
Designed to be appended to an issue or wiki page without external
databases — purely repo-native.

The leaderboard tracks wins only. A game result entry contains:
  - player: GitHub username
  - moves: number of moves taken
  - issue_number: the room issue number

Rendering produces a Markdown table suitable for a pinned issue or
wiki page.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LeaderboardEntry:
    """A single leaderboard entry for a completed winning game."""

    player: str
    moves: int
    issue_number: int


def render_leaderboard(entries: list[LeaderboardEntry], *, limit: int = 10) -> str:
    """Render a Markdown leaderboard table from entries.

    Entries are sorted by fewest moves (best first), then limited.
    """
    sorted_entries = sorted(entries, key=lambda e: e.moves)[:limit]

    if not sorted_entries:
        return (
            "## Minesweeper Hall of Fame\n\n"
            "No winners yet. Open an issue and be the first!"
        )

    lines = [
        "## Minesweeper Hall of Fame",
        "",
        "| Rank | Player | Moves | Room |",
        "|------|--------|-------|------|",
    ]
    for i, entry in enumerate(sorted_entries, 1):
        medal = _rank_medal(i)
        lines.append(
            f"| {medal} | @{entry.player} | {entry.moves} | #{entry.issue_number} |"
        )
    return "\n".join(lines)


def _rank_medal(rank: int) -> str:
    """Return a rank label with medal emoji for top 3."""
    medals = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}
    return medals.get(rank, str(rank))


def make_entry_from_state(state: dict) -> LeaderboardEntry | None:
    """Create a leaderboard entry from a terminal game state dict.

    Returns None if the game was not won.
    """
    if state.get("phase") != "won":
        return None
    return LeaderboardEntry(
        player=state["owner"],
        moves=state["seq"],
        issue_number=state["issue_number"],
    )
