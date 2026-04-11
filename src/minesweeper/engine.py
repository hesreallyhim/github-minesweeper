"""Core Minesweeper rules engine.

Handles board generation, reveal, flood-fill, flag/unflag, chord,
win detection, and loss detection.
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Iterator


class Phase(str, Enum):
    """Room lifecycle phase."""
    PLAYING = "playing"
    WON = "won"
    LOST = "lost"
    GIVEN_UP = "given_up"


class CellState(str, Enum):
    HIDDEN = "hidden"
    REVEALED = "revealed"
    FLAGGED = "flagged"


class MoveResult(str, Enum):
    OK = "ok"
    WIN = "win"
    LOSS = "loss"
    NO_OP = "no_op"
    INVALID = "invalid"


class Board:
    """Represents a Minesweeper board with hidden mine layout."""

    def __init__(self, rows: int, cols: int, mines: int, seed: int) -> None:
        if mines >= rows * cols:
            raise ValueError("Too many mines for board size")
        if rows <= 0 or cols <= 0 or mines <= 0:
            raise ValueError("Rows, cols, and mines must be positive")

        self.rows = rows
        self.cols = cols
        self.num_mines = mines
        self.seed = seed
        self.phase = Phase.PLAYING

        # Generate mine positions deterministically
        rng = random.Random(seed)
        all_cells = [(r, c) for r in range(rows) for c in range(cols)]
        mine_cells = set(rng.sample(all_cells, mines))

        self.mine_grid: list[list[bool]] = [
            [False] * cols for _ in range(rows)
        ]
        for r, c in mine_cells:
            self.mine_grid[r][c] = True

        # Precompute adjacency counts
        self.adj_counts: list[list[int]] = [
            [0] * cols for _ in range(rows)
        ]
        for r in range(rows):
            for c in range(cols):
                if self.mine_grid[r][c]:
                    self.adj_counts[r][c] = -1  # mine sentinel
                else:
                    self.adj_counts[r][c] = sum(
                        1 for nr, nc in self._neighbors(r, c)
                        if self.mine_grid[nr][nc]
                    )

        self.cell_states: list[list[CellState]] = [
            [CellState.HIDDEN] * cols for _ in range(rows)
        ]

    def _neighbors(self, row: int, col: int) -> Iterator[tuple[int, int]]:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield (nr, nc)

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.cols

    @property
    def revealed_set(self) -> set[tuple[int, int]]:
        return {
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.cell_states[r][c] == CellState.REVEALED
        }

    @property
    def flagged_set(self) -> set[tuple[int, int]]:
        return {
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.cell_states[r][c] == CellState.FLAGGED
        }

    @property
    def mine_set(self) -> set[tuple[int, int]]:
        return {
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.mine_grid[r][c]
        }

    @property
    def safe_count(self) -> int:
        return self.rows * self.cols - self.num_mines

    def _check_win(self) -> bool:
        return len(self.revealed_set) == self.safe_count

    def reveal(self, row: int, col: int) -> MoveResult:
        """Reveal a cell. Returns the move result."""
        if self.phase != Phase.PLAYING:
            return MoveResult.INVALID
        if not self._in_bounds(row, col):
            return MoveResult.INVALID
        if self.cell_states[row][col] != CellState.HIDDEN:
            return MoveResult.NO_OP

        if self.mine_grid[row][col]:
            self.cell_states[row][col] = CellState.REVEALED
            self.phase = Phase.LOST
            return MoveResult.LOSS

        self._flood_fill(row, col)

        if self._check_win():
            self.phase = Phase.WON
            return MoveResult.WIN
        return MoveResult.OK

    def _flood_fill(self, row: int, col: int) -> None:
        """Reveal the cell and flood-fill if it has zero adjacent mines."""
        stack = [(row, col)]
        while stack:
            r, c = stack.pop()
            if self.cell_states[r][c] == CellState.REVEALED:
                continue
            if self.mine_grid[r][c]:
                continue
            self.cell_states[r][c] = CellState.REVEALED
            if self.adj_counts[r][c] == 0:
                for nr, nc in self._neighbors(r, c):
                    if self.cell_states[nr][nc] == CellState.HIDDEN:
                        stack.append((nr, nc))

    def flag(self, row: int, col: int) -> MoveResult:
        """Flag a hidden cell."""
        if self.phase != Phase.PLAYING:
            return MoveResult.INVALID
        if not self._in_bounds(row, col):
            return MoveResult.INVALID
        if self.cell_states[row][col] != CellState.HIDDEN:
            return MoveResult.NO_OP
        self.cell_states[row][col] = CellState.FLAGGED
        return MoveResult.OK

    def unflag(self, row: int, col: int) -> MoveResult:
        """Remove flag from a flagged cell."""
        if self.phase != Phase.PLAYING:
            return MoveResult.INVALID
        if not self._in_bounds(row, col):
            return MoveResult.INVALID
        if self.cell_states[row][col] != CellState.FLAGGED:
            return MoveResult.NO_OP
        self.cell_states[row][col] = CellState.HIDDEN
        return MoveResult.OK

    def chord(self, row: int, col: int) -> MoveResult:
        """Chord: if a revealed numbered cell has exactly that many adjacent
        flags, reveal all hidden neighbors. If any neighbor is a mine
        (incorrectly unflagged), the player loses.
        """
        if self.phase != Phase.PLAYING:
            return MoveResult.INVALID
        if not self._in_bounds(row, col):
            return MoveResult.INVALID
        if self.cell_states[row][col] != CellState.REVEALED:
            return MoveResult.NO_OP
        count = self.adj_counts[row][col]
        if count <= 0:
            return MoveResult.NO_OP

        adj_flags = sum(
            1 for nr, nc in self._neighbors(row, col)
            if self.cell_states[nr][nc] == CellState.FLAGGED
        )
        if adj_flags != count:
            return MoveResult.NO_OP

        hidden_neighbors = [
            (nr, nc) for nr, nc in self._neighbors(row, col)
            if self.cell_states[nr][nc] == CellState.HIDDEN
        ]
        if not hidden_neighbors:
            return MoveResult.NO_OP

        # Check for loss first
        for nr, nc in hidden_neighbors:
            if self.mine_grid[nr][nc]:
                self.cell_states[nr][nc] = CellState.REVEALED
                self.phase = Phase.LOST
                return MoveResult.LOSS

        # Safe to reveal all hidden neighbors
        for nr, nc in hidden_neighbors:
            self._flood_fill(nr, nc)

        if self._check_win():
            self.phase = Phase.WON
            return MoveResult.WIN
        return MoveResult.OK

    def give_up(self) -> MoveResult:
        """Player gives up."""
        if self.phase != Phase.PLAYING:
            return MoveResult.INVALID
        self.phase = Phase.GIVEN_UP
        return MoveResult.OK

    def get_cell_display(self, row: int, col: int, reveal_all: bool = False) -> str:
        """Return the display character for a cell.

        If reveal_all is True (game over), show mines.
        """
        state = self.cell_states[row][col]
        is_mine = self.mine_grid[row][col]

        if state == CellState.FLAGGED:
            return "flag"
        if state == CellState.HIDDEN:
            if reveal_all and is_mine:
                return "mine"
            return "hidden"
        # REVEALED
        if is_mine:
            return "exploded"
        count = self.adj_counts[row][col]
        if count == 0:
            return "empty"
        return str(count)

    @classmethod
    def from_state(
        cls,
        rows: int,
        cols: int,
        mines: int,
        seed: int,
        revealed: list[list[int]],
        flagged: list[list[int]],
        phase: str,
    ) -> Board:
        """Reconstruct a Board from serialized state fields."""
        board = cls(rows, cols, mines, seed)
        board.phase = Phase(phase)
        for r, c in revealed:
            board.cell_states[r][c] = CellState.REVEALED
        for r, c in flagged:
            board.cell_states[r][c] = CellState.FLAGGED
        return board

    def to_state_fields(self) -> dict:
        """Extract board state fields for serialization."""
        return {
            "rows": self.rows,
            "cols": self.cols,
            "mines": self.num_mines,
            "seed": self.seed,
            "revealed": sorted(self.revealed_set),
            "flagged": sorted(self.flagged_set),
            "phase": self.phase.value,
        }
