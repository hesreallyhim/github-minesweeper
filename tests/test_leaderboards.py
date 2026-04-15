"""Tests for multi-card leaderboard summary/build helpers."""

from __future__ import annotations

from pathlib import Path

from minesweeper.leaderboards import (
    MS_LEADERBOARD_END,
    MS_LEADERBOARD_START,
    build_leaderboard_summary,
    render_leaderboard_markdown,
    update_readme_block,
    write_leaderboard_cards,
)


def _record(
    *,
    issue: int,
    player: str,
    result: str,
    moves: int,
    completed_at: str,
) -> dict:
    return {
        "schema": "minesweeper-game-result-v1",
        "issue": issue,
        "player": player,
        "result": result,
        "moves": moves,
        "rows": 9,
        "cols": 9,
        "mines": 10,
        "completed_at": completed_at,
    }


class TestBuildLeaderboardSummary:
    def test_empty_summary(self):
        summary = build_leaderboard_summary([])
        assert summary["source_games"] == 0
        assert summary["most_wins"] == []
        assert summary["quick_clear"] == []
        assert summary["consistency"] == []

    def test_summary_metrics(self):
        records = [
            _record(issue=1, player="alice", result="won", moves=12, completed_at="2026-01-01T00:00:00+00:00"),
            _record(issue=2, player="alice", result="won", moves=10, completed_at="2026-01-02T00:00:00+00:00"),
            _record(issue=3, player="alice", result="lost", moves=8, completed_at="2026-01-03T00:00:00+00:00"),
            _record(issue=4, player="bob", result="won", moves=9, completed_at="2026-01-04T00:00:00+00:00"),
            _record(issue=5, player="bob", result="given_up", moves=3, completed_at="2026-01-05T00:00:00+00:00"),
            _record(issue=6, player="carol", result="won", moves=14, completed_at="2026-01-06T00:00:00+00:00"),
            _record(issue=7, player="carol", result="won", moves=11, completed_at="2026-01-07T00:00:00+00:00"),
            _record(issue=8, player="carol", result="won", moves=11, completed_at="2026-01-08T00:00:00+00:00"),
        ]
        summary = build_leaderboard_summary(records)

        assert summary["source_games"] == 8
        assert summary["most_wins"][0]["player"] == "carol"
        assert summary["most_wins"][0]["wins"] == 3
        assert summary["most_games_completed"][0]["player"] == "alice"
        assert summary["most_games_completed"][0]["games"] == 3
        assert summary["quick_clear"][0]["player"] == "bob"
        assert summary["quick_clear"][0]["moves"] == 9

        # Consistency requires at least 3 games. Alice 2/3 beats Carol 3/3? no.
        # Carol should be first at 100%.
        assert summary["consistency"][0]["player"] == "carol"
        assert summary["consistency"][0]["win_rate"] == 1.0


class TestLeaderboardMarkdownAndCards:
    def test_markdown_block_has_four_cards(self):
        summary = build_leaderboard_summary([])
        md = render_leaderboard_markdown(summary)
        assert "readme-leaderboard-card-champions.svg" in md
        assert "readme-leaderboard-card-commitment.svg" in md
        assert "readme-leaderboard-card-quick-clear.svg" in md
        assert "readme-leaderboard-card-consistency.svg" in md

    def test_update_readme_block(self, tmp_path: Path):
        readme = tmp_path / "README.md"
        readme.write_text(
            "\n".join(
                [
                    "# Demo",
                    MS_LEADERBOARD_START,
                    "old block",
                    MS_LEADERBOARD_END,
                ]
            ),
            encoding="utf-8",
        )
        changed = update_readme_block(readme, "new block")
        assert changed is True
        content = readme.read_text(encoding="utf-8")
        assert "new block" in content
        assert "old block" not in content

    def test_write_leaderboard_cards(self, tmp_path: Path):
        summary = build_leaderboard_summary([])
        written = write_leaderboard_cards(summary, tmp_path)
        assert len(written) == 4
        for path in written:
            text = Path(path).read_text(encoding="utf-8")
            assert text.startswith("<svg")
