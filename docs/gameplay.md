# Gameplay Guide

## Starting a Game

1. Navigate to the **Issues** tab in this repository.
2. Click **New issue** and select the **Minesweeper Room** template.
3. Submit the issue. The bot replies with your room:

```md
### Minesweeper Room #1 — ⛏️ In Progress

Welcome to your Minesweeper room! A 9×9 board with 10 hidden mines
has been generated.

|   | A | B | C |
|---|---|---|---|
| 1 | `A1` | `B1` | `C1` |
| 2 | `A2` | `B2` | `C2` |
| 3 | `A3` | `B3` | `C3` |

Mines remaining: 10 | Cells revealed: 0/71
```

## Playing

Post a comment on your room issue with one of these commands:

| Command           | Effect                                          |
|-------------------|-------------------------------------------------|
| `/reveal B3`      | Reveal the cell at column B, row 3              |
| `/flag H7`        | Place a flag on a suspected mine                |
| `/unflag H7`      | Remove a flag                                   |
| `/chord C4`       | Reveal all unflagged neighbors of a number cell |
| `/giveup`         | End the game and reveal the full board          |

After each move, the bot replies with:
1. A status heading showing the game phase
2. A result sentence describing what happened
3. The updated board
4. Stats (mines remaining, cells revealed)
5. A command reminder (while the game is active)

If click-relay mode is enabled, hidden cells are rendered as clickable links
that trigger `/reveal` via `repository_dispatch`. Slash commands remain
supported as a fallback.

### Coordinate Format

Coordinates use spreadsheet-style notation: a **column letter** (A-I)
followed by a **row number** (1-9).

- `A1` is the top-left cell.
- `I9` is the bottom-right cell.
- Case does not matter: `b3` and `B3` are equivalent.

### Reveal

Revealing a cell uncovers it:

- If the cell is a mine, the game is lost.
- If the cell has no adjacent mines, it flood-fills to reveal neighboring
  empty cells automatically.
- If the cell has adjacent mines, a number (1-8) is shown.

### Flag / Unflag

Flagging marks a cell you suspect is a mine. Flagged cells cannot be
revealed until unflagged. Use `/unflag` to remove a flag.

The stats line tracks how many mines remain unflagged.

### Chord

Chording applies to a revealed numbered cell. If the number of adjacent
flags matches the cell's number, all remaining unflagged neighbors are
revealed. If the flags are wrong, this may trigger a loss.

### Give Up

`/giveup` ends the game immediately and reveals the full mine layout.

## Winning

Reveal all non-mine cells to win. You do not need to flag every mine.

When you win, the bot posts a final board with a victory message:

```
### Minesweeper Room #1 — 🏆 You Win!

🏆 You win! All safe cells have been revealed. Congratulations!
```

## Board Symbols

| Symbol | Meaning                    |
|--------|----------------------------|
| `A1`   | Hidden cell (coordinate shown) |
| 🚩      | Flagged                    |
| ·      | Revealed, no mines nearby  |
| 1-8    | Adjacent mine count        |
| 💣      | Mine (shown on loss/giveup)|
| 💥      | Exploded mine (hit by you) |

## Room Rules

- Only the issue opener can play in their room.
- One active game room per player at a time.
- Commands from other users are politely rejected.
- Each command is processed exactly once (duplicate deliveries are safe).
- Once a game ends (win, loss, or give-up), no more moves are accepted.
  Open a new issue to play again.
