"""Tests for the lightweight leaderboard / hall of fame."""

from __future__ import annotations

from minesweeper.leaderboard import (
    LeaderboardEntry,
    make_entry_from_state,
    render_leaderboard,
)


class TestRenderLeaderboard:
    def test_empty_leaderboard(self):
        text = render_leaderboard([])
        assert "Hall of Fame" in text
        assert "No winners yet" in text

    def test_single_entry(self):
        entries = [LeaderboardEntry(player="alice", moves=15, issue_number=1)]
        text = render_leaderboard(entries)
        assert "| @alice |" in text
        assert "| 15 |" in text
        assert "| #1 |" in text

    def test_entries_sorted_by_moves(self):
        entries = [
            LeaderboardEntry(player="bob", moves=30, issue_number=2),
            LeaderboardEntry(player="alice", moves=15, issue_number=1),
            LeaderboardEntry(player="carol", moves=20, issue_number=3),
        ]
        text = render_leaderboard(entries)
        lines = text.strip().split("\n")
        # Data rows start at index 4 (header, blank, table header, separator)
        data_lines = lines[4:]
        assert "@alice" in data_lines[0]
        assert "@carol" in data_lines[1]
        assert "@bob" in data_lines[2]

    def test_limit_respected(self):
        entries = [
            LeaderboardEntry(player=f"p{i}", moves=i + 10, issue_number=i)
            for i in range(20)
        ]
        text = render_leaderboard(entries, limit=5)
        data_lines = [line for line in text.split("\n") if line.startswith("|") and "@" in line]
        assert len(data_lines) == 5

    def test_medals_for_top_3(self):
        entries = [
            LeaderboardEntry(player="gold", moves=10, issue_number=1),
            LeaderboardEntry(player="silver", moves=15, issue_number=2),
            LeaderboardEntry(player="bronze", moves=20, issue_number=3),
            LeaderboardEntry(player="fourth", moves=25, issue_number=4),
        ]
        text = render_leaderboard(entries)
        assert "\U0001f947" in text  # gold medal
        assert "\U0001f948" in text  # silver medal
        assert "\U0001f949" in text  # bronze medal

    def test_table_has_header(self):
        entries = [LeaderboardEntry(player="alice", moves=15, issue_number=1)]
        text = render_leaderboard(entries)
        assert "| Rank | Player | Moves | Room |" in text


class TestMakeEntryFromState:
    def test_creates_entry_from_won_state(self):
        state = {
            "phase": "won",
            "owner": "alice",
            "seq": 15,
            "issue_number": 42,
        }
        entry = make_entry_from_state(state)
        assert entry is not None
        assert entry.player == "alice"
        assert entry.moves == 15
        assert entry.issue_number == 42

    def test_returns_none_for_lost_state(self):
        state = {"phase": "lost", "owner": "bob", "seq": 5, "issue_number": 1}
        assert make_entry_from_state(state) is None

    def test_returns_none_for_playing_state(self):
        state = {"phase": "playing", "owner": "bob", "seq": 5, "issue_number": 1}
        assert make_entry_from_state(state) is None

    def test_returns_none_for_given_up_state(self):
        state = {"phase": "given_up", "owner": "bob", "seq": 5, "issue_number": 1}
        assert make_entry_from_state(state) is None
