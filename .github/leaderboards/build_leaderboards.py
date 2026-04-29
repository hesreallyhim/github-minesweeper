#!/usr/bin/env python3
"""Build Minesweeper leaderboards from terminal game records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from leaderboards import (
    build_leaderboard_summary,
    load_game_records,
    render_leaderboard_markdown,
    update_readme_block,
    write_leaderboard_cards,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--games-root",
        type=Path,
        required=True,
        help="Directory containing terminal game records.",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        required=True,
        help="README path with leaderboard marker block.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        required=True,
        help="Path to write machine-readable leaderboard summary JSON.",
    )
    parser.add_argument(
        "--cards-dir",
        type=Path,
        required=False,
        default=None,
        help="Optional directory to write README leaderboard cards.",
    )
    parser.add_argument(
        "--checked-at",
        required=False,
        default=None,
        help="UTC timestamp for when leaderboard sources were checked.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = load_game_records(args.games_root)
    summary = build_leaderboard_summary(records, checked_at=args.checked_at)
    markdown = render_leaderboard_markdown(summary)
    changed = update_readme_block(args.readme, markdown)

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    written_cards: list[str] = []
    if args.cards_dir is not None:
        written_cards = write_leaderboard_cards(summary, args.cards_dir)

    print(f"Loaded {len(records)} game records from {args.games_root}")
    print(f"README updated: {changed}")
    print(f"Wrote leaderboard JSON: {args.json_out}")
    if written_cards:
        print(f"Wrote leaderboard cards: {', '.join(written_cards)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
