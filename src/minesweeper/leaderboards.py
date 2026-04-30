"""Leaderboard summary and card rendering utilities.

Builds four leaderboard views from completed Minesweeper game records:
  1) Champions   - most wins
  2) Commitment  - most games completed
  3) Quick Clear - wins in fewest moves
  4) Consistency - highest win rate (with minimum games threshold)
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

MS_LEADERBOARD_START = "<!-- MS_LEADERBOARD_START -->"
MS_LEADERBOARD_END = "<!-- MS_LEADERBOARD_END -->"
GAME_RESULT_SCHEMA = "minesweeper-game-result-v1"
TOP_N = 10
CARD_TOP_N = 5
MIN_GAMES_FOR_RATE = 3


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_record(path: Path, data: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize one raw game record payload."""
    schema = str(data.get("schema", "")).strip()
    if schema and schema != GAME_RESULT_SCHEMA:
        return None

    issue = _safe_int(data.get("issue"), -1)
    if issue < 0:
        return None

    player = str(data.get("player", "")).strip().lower()
    if not player:
        return None

    result = str(data.get("result", "")).strip().lower()
    if result not in {"won", "lost", "given_up"}:
        return None

    moves = max(_safe_int(data.get("moves"), 0), 0)
    completed_at = str(data.get("completed_at", "")).strip()
    if not completed_at:
        completed_at = dt.datetime.fromtimestamp(
            path.stat().st_mtime,
            tz=dt.UTC,
        ).replace(microsecond=0).isoformat()

    return {
        "schema": GAME_RESULT_SCHEMA,
        "issue": issue,
        "player": player,
        "result": result,
        "moves": moves,
        "rows": _safe_int(data.get("rows"), 0),
        "cols": _safe_int(data.get("cols"), 0),
        "mines": _safe_int(data.get("mines"), 0),
        "completed_at": completed_at,
    }


def load_game_records(games_root: Path) -> list[dict[str, Any]]:
    """Load normalized terminal-game records from data/games."""
    if not games_root.exists():
        return []

    records: list[dict[str, Any]] = []
    for path in sorted(games_root.glob("*.json")):
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Skipping malformed JSON: {path}")
            continue
        if not isinstance(payload, dict):
            print(f"Skipping non-object record: {path}")
            continue

        normalized = normalize_record(path, payload)
        if normalized is None:
            print(f"Skipping invalid game record: {path}")
            continue
        records.append(normalized)

    return sorted(records, key=lambda r: (int(r["issue"]), str(r["completed_at"])))


def _sort_counts(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def build_leaderboard_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the canonical leaderboard summary payload."""
    games_completed = Counter[str]()
    wins = Counter[str]()
    wins_by_moves: dict[int, Counter[str]] = defaultdict(Counter)
    player_games = Counter[str]()
    player_wins = Counter[str]()

    for record in records:
        player = str(record["player"])
        games_completed[player] += 1
        player_games[player] += 1

        if str(record["result"]) != "won":
            continue
        wins[player] += 1
        player_wins[player] += 1
        moves = _safe_int(record.get("moves"), 0)
        wins_by_moves[moves][player] += 1

    quick_clear: list[dict[str, Any]] = []
    for moves in sorted(wins_by_moves.keys()):
        for player, count in _sort_counts(wins_by_moves[moves]):
            quick_clear.append(
                {"player": player, "moves": moves, "wins": count}
            )

    consistency: list[dict[str, Any]] = []
    for player, games in player_games.items():
        if games < MIN_GAMES_FOR_RATE:
            continue
        wins_count = player_wins.get(player, 0)
        rate = wins_count / games
        consistency.append(
            {
                "player": player,
                "wins": wins_count,
                "games": games,
                "win_rate": round(rate, 4),
            }
        )
    consistency.sort(
        key=lambda row: (
            -float(row["win_rate"]),
            -int(row["wins"]),
            -int(row["games"]),
            str(row["player"]),
        )
    )

    generated_at = max(
        (str(record["completed_at"]) for record in records),
        default="n/a",
    )
    wins_by_moves_rows: list[dict[str, Any]] = []
    for moves in sorted(wins_by_moves.keys()):
        winners = [
            {"player": player, "wins": count}
            for player, count in _sort_counts(wins_by_moves[moves])
        ]
        wins_by_moves_rows.append({"moves": moves, "winners": winners})

    return {
        "generated_at": generated_at,
        "source_games": len(records),
        "min_games_for_rate": MIN_GAMES_FOR_RATE,
        "most_games_completed": [
            {"player": player, "games": games}
            for player, games in _sort_counts(games_completed)[:TOP_N]
        ],
        "most_wins": [
            {"player": player, "wins": count}
            for player, count in _sort_counts(wins)[:TOP_N]
        ],
        "wins_by_moves": wins_by_moves_rows,
        "quick_clear": quick_clear[:TOP_N],
        "consistency": consistency[:TOP_N],
    }


def _render_leaderboard_card_svg(
    *,
    title: str,
    subtitle: str,
    rows: list[tuple[str, str]],
) -> str:
    """Render one leaderboard card SVG for README embedding."""
    width = 760
    height = 390
    max_rows = CARD_TOP_N
    padded_rows = rows[:max_rows]
    if not padded_rows:
        padded_rows = [("No data yet", "--")]
    while len(padded_rows) < max_rows:
        padded_rows.append(("--", "--"))

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f"font-family=\"'SF Mono','Fira Code','Courier New',monospace\">",
        "  <defs>",
        '    <linearGradient id="card-bg" x1="0" y1="0" x2="0" y2="1">',
        '      <stop offset="0%" stop-color="#101820"/>',
        '      <stop offset="100%" stop-color="#0a0f14"/>',
        "    </linearGradient>",
        '    <linearGradient id="card-panel" x1="0" y1="0" x2="1" y2="1">',
        '      <stop offset="0%" stop-color="#1b3a2a"/>',
        '      <stop offset="100%" stop-color="#1a2630"/>',
        "    </linearGradient>",
        '    <linearGradient id="card-accent" x1="0" y1="0" x2="1" y2="0">',
        '      <stop offset="0%" stop-color="#4cc46f"/>',
        '      <stop offset="50%" stop-color="#f3f6f8"/>',
        '      <stop offset="100%" stop-color="#3ea6d1"/>',
        "    </linearGradient>",
        "  </defs>",
        '  <rect x="8" y="8" width="744" height="374" rx="20" fill="url(#card-bg)" stroke="#2c4a5e" stroke-width="3"/>',
        '  <rect x="22" y="22" width="716" height="92" rx="14" fill="url(#card-panel)" stroke="#31556b" stroke-width="2"/>',
        f'  <text x="{width // 2}" y="68" text-anchor="middle" fill="url(#card-accent)" '
        'font-size="40" font-weight="700" letter-spacing="1.8" '
        f'font-family="\'Cinzel\',\'Copperplate\',\'Times New Roman\',serif">{html.escape(title)}</text>',
        f'  <text x="{width // 2}" y="96" text-anchor="middle" fill="#c7d8e3" '
        'font-size="21" letter-spacing="0.8">'
        f"{html.escape(subtitle)}</text>",
    ]

    row_y = 128
    row_h = 48
    for idx, (label, value) in enumerate(padded_rows, start=1):
        fill = "#0f1820" if idx % 2 == 1 else "#0d141b"
        parts.extend(
            [
                f'  <rect x="24" y="{row_y}" width="712" height="44" rx="9" fill="{fill}" stroke="#25485f" stroke-width="1"/>',
                f'  <text x="42" y="{row_y + 30}" fill="#9fd8f1" font-size="24" font-weight="700">{idx}</text>',
                f'  <text x="88" y="{row_y + 30}" fill="#e6eef3" font-size="22">{html.escape(label)}</text>',
                f'  <text x="716" y="{row_y + 30}" text-anchor="end" fill="#e6eef3" font-size="22" font-weight="700">'
                f"{html.escape(value)}</text>",
            ]
        )
        row_y += row_h

    parts.append("</svg>")
    return "\n".join(parts)


def write_leaderboard_cards(summary: dict[str, Any], cards_dir: Path) -> list[str]:
    """Generate and write all four README leaderboard cards."""
    cards_dir.mkdir(parents=True, exist_ok=True)

    champions_rows = [
        (f"@{row['player']}", f"{row['wins']} wins")
        for row in list(summary.get("most_wins", []))[:CARD_TOP_N]
    ]
    commitment_rows = [
        (f"@{row['player']}", f"{row['games']} games")
        for row in list(summary.get("most_games_completed", []))[:CARD_TOP_N]
    ]
    quick_clear_rows = [
        (f"@{row['player']}", f"{row['moves']} moves")
        for row in list(summary.get("quick_clear", []))[:CARD_TOP_N]
    ]
    consistency_rows = [
        (
            f"@{row['player']}",
            f"{float(row['win_rate']) * 100:.1f}% ({row['wins']}/{row['games']})",
        )
        for row in list(summary.get("consistency", []))[:CARD_TOP_N]
    ]

    cards = {
        "readme-leaderboard-card-champions.svg": _render_leaderboard_card_svg(
            title="CHAMPIONS",
            subtitle="Most Wins",
            rows=champions_rows,
        ),
        "readme-leaderboard-card-commitment.svg": _render_leaderboard_card_svg(
            title="COMMITMENT",
            subtitle="Most Games Completed",
            rows=commitment_rows,
        ),
        "readme-leaderboard-card-quick-clear.svg": _render_leaderboard_card_svg(
            title="QUICK CLEAR",
            subtitle="Wins in Fewest Moves",
            rows=quick_clear_rows,
        ),
        "readme-leaderboard-card-consistency.svg": _render_leaderboard_card_svg(
            title="CONSISTENCY",
            subtitle=f"Best Win Rate (Min {MIN_GAMES_FOR_RATE} Games)",
            rows=consistency_rows,
        ),
    }

    written: list[str] = []
    for filename, content in cards.items():
        path = cards_dir / filename
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return written


def render_leaderboard_markdown(summary: dict[str, Any]) -> str:
    """Render README leaderboard block between marker comments."""
    generated_at = str(summary["generated_at"])
    source_games = _safe_int(summary["source_games"], 0)
    has_data = source_games > 0

    lines = [
        "### Leaderboards",
        f"_As of (UTC): {generated_at or 'n/a'} from {source_games} completed games_",
        "(Leaderboards update every 15 minutes)",
        "",
        '<table align="center">',
        "  <tr>",
        '    <td><picture><img src="assets/readme-leaderboard-card-champions.svg" alt="Champions Card" width="460" /></picture></td>',
        '    <td><picture><img src="assets/readme-leaderboard-card-commitment.svg" alt="Commitment Card" width="460" /></picture></td>',
        "  </tr>",
        "  <tr>",
        '    <td><picture><img src="assets/readme-leaderboard-card-quick-clear.svg" alt="Quick Clear Card" width="460" /></picture></td>',
        '    <td><picture><img src="assets/readme-leaderboard-card-consistency.svg" alt="Consistency Card" width="460" /></picture></td>',
        "  </tr>",
        "</table>",
    ]
    if not has_data:
        lines.append("")
        lines.append("<em>No completed games yet.</em>")
    return "\n".join(lines)


def update_readme_block(readme_path: Path, block: str) -> bool:
    """Replace the leaderboard marker block in README."""
    content = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"{re.escape(MS_LEADERBOARD_START)}\n.*?\n{re.escape(MS_LEADERBOARD_END)}",
        flags=re.DOTALL,
    )
    replacement = f"{MS_LEADERBOARD_START}\n{block}\n{MS_LEADERBOARD_END}"
    updated, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise RuntimeError(
            f"Could not locate unique leaderboard marker block in {readme_path}"
        )
    if updated == content:
        return False
    readme_path.write_text(updated, encoding="utf-8")
    return True
