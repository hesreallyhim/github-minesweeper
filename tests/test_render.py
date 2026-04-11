"""Tests for board and room status rendering.

Includes snapshot-style tests that verify exact rendered output for
various board states and response templates.
"""

from __future__ import annotations

from minesweeper.engine import Board, Phase
from minesweeper.render import (
    COMMAND_REMINDER,
    format_move_response,
    format_room_open,
    render_board,
    render_game_over_notice,
    render_malformed_command,
    render_non_owner_response,
    render_room_header,
    render_stats,
)

TEST_SEED = 42


class TestRenderBoard:
    def test_hidden_board(self):
        board = Board(9, 9, 10, TEST_SEED)
        text = render_board(board)
        assert "```" in text
        assert "A B C D E F G H I" in text
        assert "\u2b1c" in text  # hidden cells

    def test_board_dimensions(self):
        board = Board(9, 9, 10, TEST_SEED)
        text = render_board(board)
        lines = text.split("```")[1].strip().split("\n")
        assert len(lines) == 10  # header + 9 rows

    def test_revealed_cells_show_numbers(self):
        board = Board(9, 9, 10, TEST_SEED)
        # Reveal a safe cell
        safe_cells = [
            (r, c) for r in range(9) for c in range(9)
            if not board.mine_grid[r][c]
        ]
        r, c = safe_cells[0]
        board.reveal(r, c)
        text = render_board(board)
        # Should have at least one revealed cell (either number or dot)
        assert "\u00b7" in text or any(str(n) in text for n in range(1, 9))

    def test_reveal_all_shows_mines(self):
        board = Board(9, 9, 10, TEST_SEED)
        text = render_board(board, reveal_all=True)
        assert "\U0001f4a3" in text  # mine symbol

    def test_flagged_cell_shows_flag(self):
        board = Board(9, 9, 10, TEST_SEED)
        board.flag(0, 0)
        text = render_board(board)
        assert "\U0001f6a9" in text  # flag symbol


class TestRenderRoomHeader:
    def test_playing_header(self):
        header = render_room_header("player1", 42, Phase.PLAYING)
        assert "Minesweeper Room #42" in header
        assert "In Progress" in header

    def test_won_header(self):
        header = render_room_header("player1", 1, Phase.WON)
        assert "You Win!" in header

    def test_lost_header(self):
        header = render_room_header("player1", 1, Phase.LOST)
        assert "Game Over" in header

    def test_given_up_header(self):
        header = render_room_header("player1", 1, Phase.GIVEN_UP)
        assert "Abandoned" in header


class TestRenderMessages:
    def test_non_owner_response(self):
        msg = render_non_owner_response("interloper")
        assert "interloper" in msg
        assert "only the room owner" in msg

    def test_malformed_command(self):
        msg = render_malformed_command("gibberish")
        assert "/reveal" in msg
        assert "/flag" in msg
        assert "/giveup" in msg


class TestRenderStats:
    def test_initial_stats(self):
        board = Board(9, 9, 10, TEST_SEED)
        stats = render_stats(board)
        assert "Mines remaining: **10**" in stats
        assert "Cells revealed: **0/71**" in stats

    def test_stats_after_flag(self):
        board = Board(9, 9, 10, TEST_SEED)
        board.flag(0, 0)
        stats = render_stats(board)
        assert "Mines remaining: **9**" in stats

    def test_stats_after_reveal(self):
        board = Board(9, 9, 10, TEST_SEED)
        safe = next(
            (r, c) for r in range(9) for c in range(9)
            if not board.mine_grid[r][c]
        )
        board.reveal(*safe)
        stats = render_stats(board)
        revealed_count = len(board.revealed_set)
        assert f"Cells revealed: **{revealed_count}/71**" in stats


class TestRenderGameOverNotice:
    def test_won_notice(self):
        msg = render_game_over_notice(Phase.WON)
        assert "already **won**" in msg
        assert "new issue" in msg

    def test_lost_notice(self):
        msg = render_game_over_notice(Phase.LOST)
        assert "already **lost**" in msg

    def test_given_up_notice(self):
        msg = render_game_over_notice(Phase.GIVEN_UP)
        assert "already **given up**" in msg


class TestSnapshotRoomOpen:
    """Snapshot-style tests for the initial room creation output."""

    def test_room_open_structure(self):
        board = Board(9, 9, 10, TEST_SEED)
        header = render_room_header("alice", 7, Phase.PLAYING)
        board_text = render_board(board)
        stats = render_stats(board)
        body = format_room_open(header, board_text, stats, 10)

        # Verify all required sections are present in order
        sections = [
            "### Minesweeper Room #7",  # heading
            "Welcome to your Minesweeper room!",  # welcome
            "**10** hidden mines",  # mine count
            "```",  # board start
            "A B C D E F G H I",  # column headers
            "```",  # board end
            "Mines remaining: **10**",  # stats
            "Commands:",  # command reminder
        ]
        last_pos = -1
        for section in sections:
            pos = body.find(section, last_pos + 1)
            assert pos > last_pos, f"Section '{section}' not found after position {last_pos}"
            last_pos = pos

    def test_room_open_all_hidden(self):
        board = Board(9, 9, 10, TEST_SEED)
        board_text = render_board(board)
        # Every row should contain only hidden cells
        board_inner = board_text.split("```")[1].strip()
        for line in board_inner.split("\n")[1:]:  # skip header
            # Each cell should be the hidden symbol
            cells = line.split()[1:]  # skip row number
            for cell in cells:
                assert cell == "\u2b1c", f"Expected hidden cell, got {cell!r}"


class TestSnapshotMoveResponse:
    """Snapshot-style tests for move response outputs."""

    def test_reveal_response_structure(self):
        board = Board(9, 9, 10, TEST_SEED)
        safe = next(
            (r, c) for r in range(9) for c in range(9)
            if not board.mine_grid[r][c]
        )
        board.reveal(*safe)
        header = render_room_header("alice", 7, Phase.PLAYING)
        board_text = render_board(board)
        stats = render_stats(board)
        body = format_move_response(
            header, "Revealed **A1**.", board_text, stats, Phase.PLAYING
        )

        assert "### Minesweeper Room #7" in body
        assert "Revealed **A1**." in body
        assert "```" in body
        assert "Mines remaining:" in body
        assert "Commands:" in body  # reminder present during play

    def test_loss_response_no_command_reminder(self):
        board = Board(9, 9, 10, TEST_SEED)
        mine = next(
            (r, c) for r in range(9) for c in range(9)
            if board.mine_grid[r][c]
        )
        board.reveal(*mine)
        header = render_room_header("alice", 7, Phase.LOST)
        board_text = render_board(board, reveal_all=True)
        stats = render_stats(board)
        body = format_move_response(
            header, "BOOM!", board_text, stats, Phase.LOST
        )

        assert "Game Over" in body
        assert "BOOM!" in body
        assert COMMAND_REMINDER not in body  # no reminder on game over

    def test_win_response_no_command_reminder(self):
        header = render_room_header("alice", 7, Phase.WON)
        stats = "Mines remaining: **0** | Cells revealed: **71/71**"
        body = format_move_response(
            header, "You win!", "```\nboard\n```", stats, Phase.WON
        )

        assert "You Win!" in body
        assert COMMAND_REMINDER not in body

    def test_giveup_response_no_command_reminder(self):
        header = render_room_header("alice", 7, Phase.GIVEN_UP)
        stats = "Mines remaining: **10** | Cells revealed: **0/71**"
        body = format_move_response(
            header, "You gave up.", "```\nboard\n```", stats, Phase.GIVEN_UP
        )

        assert "Abandoned" in body
        assert COMMAND_REMINDER not in body


class TestSnapshotBoardStates:
    """Snapshot-style tests for specific board rendering states."""

    def test_exploded_mine_rendering(self):
        board = Board(9, 9, 10, TEST_SEED)
        mine = next(
            (r, c) for r in range(9) for c in range(9)
            if board.mine_grid[r][c]
        )
        board.reveal(*mine)
        text = render_board(board, reveal_all=True)
        assert "\U0001f4a5" in text  # exploded mine
        assert "\U0001f4a3" in text  # remaining mines shown

    def test_mixed_board_state(self):
        board = Board(9, 9, 10, TEST_SEED)
        safe_cells = [
            (r, c) for r in range(9) for c in range(9)
            if not board.mine_grid[r][c]
        ]
        # Reveal one cell first
        board.reveal(*safe_cells[0])
        # Flag a cell that is still hidden after the flood fill
        flagged = False
        for r, c in safe_cells:
            from minesweeper.engine import CellState
            if board.cell_states[r][c] == CellState.HIDDEN:
                board.flag(r, c)
                flagged = True
                break
        assert flagged, "Need at least one hidden cell to flag"
        text = render_board(board)
        # Board should have a mix of hidden, revealed, and flagged cells
        assert "\u2b1c" in text  # hidden
        assert "\U0001f6a9" in text  # flagged
        # Should have at least one revealed indicator
        assert "\u00b7" in text or any(str(n) in text for n in range(1, 9))

    def test_full_board_column_headers(self):
        board = Board(9, 9, 10, TEST_SEED)
        text = render_board(board)
        board_inner = text.split("```")[1].strip()
        header_line = board_inner.split("\n")[0].strip()
        assert header_line == "A B C D E F G H I"

    def test_full_board_row_labels(self):
        board = Board(9, 9, 10, TEST_SEED)
        text = render_board(board)
        board_inner = text.split("```")[1].strip()
        rows = board_inner.split("\n")[1:]  # skip header
        for i, row in enumerate(rows):
            expected_label = f"{i + 1:2d}"
            assert row.startswith(expected_label), (
                f"Row {i} should start with '{expected_label}', got '{row[:3]}'"
            )
