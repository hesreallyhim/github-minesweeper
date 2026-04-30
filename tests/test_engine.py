"""Tests for the Minesweeper rules engine."""

from __future__ import annotations

from minesweeper.engine import Board, CellState, MoveResult, Phase


SEED = 42
ROWS, COLS, MINES = 9, 9, 10


def make_board(seed: int = SEED) -> Board:
    return Board(rows=ROWS, cols=COLS, mines=MINES, seed=seed)


class TestBoardInit:
    def test_dimensions(self):
        b = make_board()
        assert b.rows == ROWS
        assert b.cols == COLS
        assert b.num_mines == MINES

    def test_correct_mine_count(self):
        b = make_board()
        assert len(b.mine_set) == MINES

    def test_deterministic(self):
        b1 = make_board(seed=1)
        b2 = make_board(seed=1)
        assert b1.mine_set == b2.mine_set

    def test_different_seeds_differ(self):
        b1 = make_board(seed=1)
        b2 = make_board(seed=2)
        assert b1.mine_set != b2.mine_set

    def test_all_cells_hidden(self):
        b = make_board()
        for r in range(b.rows):
            for c in range(b.cols):
                assert b.cell_states[r][c] == CellState.HIDDEN

    def test_phase_playing(self):
        b = make_board()
        assert b.phase == Phase.PLAYING

    def test_too_many_mines(self):
        import pytest
        with pytest.raises(ValueError):
            Board(rows=3, cols=3, mines=9, seed=0)

    def test_zero_rows(self):
        import pytest
        with pytest.raises(ValueError):
            Board(rows=0, cols=9, mines=1, seed=0)


class TestReveal:
    def test_reveal_safe_cell(self):
        b = make_board()
        # Find a safe cell
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c]:
                    result = b.reveal(r, c)
                    assert result in (MoveResult.OK, MoveResult.WIN)
                    assert b.cell_states[r][c] == CellState.REVEALED
                    return

    def test_reveal_mine_loses(self):
        b = make_board()
        mine_r, mine_c = next(iter(b.mine_set))
        result = b.reveal(mine_r, mine_c)
        assert result == MoveResult.LOSS
        assert b.phase == Phase.LOST

    def test_reveal_already_revealed_is_noop(self):
        b = make_board()
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c]:
                    b.reveal(r, c)
                    result = b.reveal(r, c)
                    assert result == MoveResult.NO_OP
                    return

    def test_reveal_flagged_is_noop(self):
        b = make_board()
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c]:
                    b.flag(r, c)
                    result = b.reveal(r, c)
                    assert result == MoveResult.NO_OP
                    return

    def test_reveal_out_of_bounds(self):
        b = make_board()
        assert b.reveal(-1, 0) == MoveResult.INVALID
        assert b.reveal(0, 99) == MoveResult.INVALID

    def test_reveal_after_game_over(self):
        b = make_board()
        mine_r, mine_c = next(iter(b.mine_set))
        b.reveal(mine_r, mine_c)
        assert b.reveal(0, 0) == MoveResult.INVALID


class TestFloodFill:
    def test_flood_fill_expands_zeros(self):
        # Use a small board with a known empty region
        b = Board(rows=4, cols=4, mines=1, seed=0)
        # Find a cell with adj_count 0
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c] and b.adj_counts[r][c] == 0:
                    b.reveal(r, c)
                    # Should have revealed more than just this cell
                    revealed = len(b.revealed_set)
                    assert revealed > 1
                    return


class TestFlag:
    def test_flag_hidden_cell(self):
        b = make_board()
        result = b.flag(0, 0)
        assert result == MoveResult.OK
        assert b.cell_states[0][0] == CellState.FLAGGED

    def test_flag_revealed_is_noop(self):
        b = make_board()
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c]:
                    b.reveal(r, c)
                    result = b.flag(r, c)
                    assert result == MoveResult.NO_OP
                    return

    def test_flag_already_flagged_is_noop(self):
        b = make_board()
        b.flag(0, 0)
        assert b.flag(0, 0) == MoveResult.NO_OP

    def test_flag_out_of_bounds(self):
        b = make_board()
        assert b.flag(-1, 0) == MoveResult.INVALID


class TestUnflag:
    def test_unflag_flagged_cell(self):
        b = make_board()
        b.flag(0, 0)
        result = b.unflag(0, 0)
        assert result == MoveResult.OK
        assert b.cell_states[0][0] == CellState.HIDDEN

    def test_unflag_hidden_is_noop(self):
        b = make_board()
        assert b.unflag(0, 0) == MoveResult.NO_OP

    def test_unflag_out_of_bounds(self):
        b = make_board()
        assert b.unflag(0, 99) == MoveResult.INVALID


class TestChord:
    def test_chord_on_hidden_is_noop(self):
        b = make_board()
        assert b.chord(0, 0) == MoveResult.NO_OP

    def test_chord_on_zero_cell_is_noop(self):
        b = make_board()
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c] and b.adj_counts[r][c] == 0:
                    b.reveal(r, c)
                    result = b.chord(r, c)
                    assert result == MoveResult.NO_OP
                    return

    def test_chord_with_correct_flags(self):
        # Build a small board and set up a valid chord scenario
        b = Board(rows=3, cols=3, mines=1, seed=0)
        mine_pos = next(iter(b.mine_set))
        # Find a revealed cell adjacent to the mine with count 1
        for r in range(b.rows):
            for c in range(b.cols):
                if (
                    not b.mine_grid[r][c]
                    and b.adj_counts[r][c] == 1
                ):
                    b.cell_states[r][c] = CellState.REVEALED
                    b.cell_states[mine_pos[0]][mine_pos[1]] = CellState.FLAGGED
                    result = b.chord(r, c)
                    assert result in (MoveResult.OK, MoveResult.WIN)
                    return

    def test_chord_wrong_flag_count_is_noop(self):
        b = Board(rows=3, cols=3, mines=1, seed=0)
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c] and b.adj_counts[r][c] == 1:
                    b.cell_states[r][c] = CellState.REVEALED
                    # Don't flag anything — count mismatch
                    result = b.chord(r, c)
                    assert result == MoveResult.NO_OP
                    return


class TestGiveUp:
    def test_give_up(self):
        b = make_board()
        result = b.give_up()
        assert result == MoveResult.OK
        assert b.phase == Phase.GIVEN_UP

    def test_give_up_twice(self):
        b = make_board()
        b.give_up()
        assert b.give_up() == MoveResult.INVALID


class TestWin:
    def test_win_by_revealing_all_safe(self):
        b = Board(rows=3, cols=3, mines=1, seed=0)
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c]:
                    b.reveal(r, c)
        assert b.phase == Phase.WON


class TestSerialization:
    def test_to_state_fields(self):
        b = make_board()
        fields = b.to_state_fields()
        assert fields["rows"] == ROWS
        assert fields["cols"] == COLS
        assert fields["mines"] == MINES
        assert fields["seed"] == SEED
        assert fields["phase"] == "playing"
        assert fields["revealed"] == []
        assert fields["flagged"] == []

    def test_from_state_roundtrip(self):
        b1 = make_board()
        b1.reveal(0, 0)
        b1.flag(1, 1)
        fields = b1.to_state_fields()

        b2 = Board.from_state(
            rows=fields["rows"],
            cols=fields["cols"],
            mines=fields["mines"],
            seed=fields["seed"],
            revealed=fields["revealed"],
            flagged=fields["flagged"],
            phase=fields["phase"],
        )
        assert b2.mine_set == b1.mine_set
        assert b2.revealed_set == b1.revealed_set
        assert b2.flagged_set == b1.flagged_set
        assert b2.phase == b1.phase

    def test_cell_display_hidden(self):
        b = make_board()
        assert b.get_cell_display(0, 0) == "hidden"

    def test_cell_display_flag(self):
        b = make_board()
        b.flag(0, 0)
        assert b.get_cell_display(0, 0) == "flag"

    def test_cell_display_revealed(self):
        b = make_board()
        for r in range(b.rows):
            for c in range(b.cols):
                if not b.mine_grid[r][c]:
                    b.reveal(r, c)
                    disp = b.get_cell_display(r, c)
                    assert disp in ("empty", "1", "2", "3", "4", "5", "6", "7", "8")
                    return

    def test_cell_display_mine_reveal_all(self):
        b = make_board()
        mine_r, mine_c = next(iter(b.mine_set))
        assert b.get_cell_display(mine_r, mine_c, reveal_all=True) == "mine"
