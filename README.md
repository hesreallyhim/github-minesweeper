# GitHub Issue Minesweeper

A GitHub-native single-player Minesweeper game. Open an issue to start a
room, play by commenting commands, and see the board rendered directly in
bot replies.

## Quick Start

1. Go to **Issues** > **New issue** > select **Minesweeper Room**.
2. Submit the issue. The bot posts a fresh 9x9 board:

```
   A B C D E F G H I
 1 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 2 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 3 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 ...
```

3. Comment a command to play your turn:

```
/reveal B3
```

4. The bot replies with the updated board, stats, and game status:

```
### Minesweeper Room #1 — ⛏️ In Progress

Revealed **B3**.

   A B C D E F G H I
 1 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 2 ⬜ 1 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 3 ⬜ · ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 ...

Mines remaining: **10** | Cells revealed: **5/71**
```

5. Keep revealing cells until you win — or hit a mine!

## Commands

| Command           | Effect                                |
|-------------------|---------------------------------------|
| `/reveal B3`      | Reveal a cell                         |
| `/flag H7`        | Flag a suspected mine                 |
| `/unflag H7`      | Remove a flag                         |
| `/chord C4`       | Chord-reveal around a numbered cell   |
| `/giveup`         | End the game and reveal the board     |

Coordinates are spreadsheet-style: column letter (A-I) + row number
(1-9). Case doesn't matter — `b3` and `B3` both work.

## Board Symbols

| Symbol | Meaning              |
|--------|----------------------|
| ⬜      | Hidden (unrevealed)  |
| 🚩      | Flagged              |
| ·      | Revealed, no mines nearby |
| 1-8    | Adjacent mine count  |
| 💣      | Mine (shown on loss) |
| 💥      | Exploded mine        |

## Room Rules

- Only the issue opener can play in their room.
- One active game per player at a time.
- Commands from other users are politely rejected.
- Each command is processed exactly once (duplicate-safe).
- Reveal all safe cells to win. You don't need to flag every mine.

## Project Structure

```
src/minesweeper/       # Game engine, state, commands, rendering
tests/                 # Unit tests and fixture-driven tests
tests/fixtures/github/ # Replayable GitHub event payloads
.github/workflows/     # GitHub Actions for room lifecycle
.github/ISSUE_TEMPLATE/# Issue template for starting a room
scripts/               # Local development and replay tools
docs/                  # Gameplay guide and operator notes
```

## Local Development

```bash
# Set up the virtual environment and install dependencies
make bootstrap

# Run the test suite
make test

# Run lint checks
make lint

# Build the Docker image
make docker-build
```

## Documentation

- [Gameplay Guide](docs/gameplay.md) — how to play
- [Operator Notes](docs/operator-notes.md) — deployment and operations
- [V1 Game Contract](docs/v1-game-contract.md) — implementation contract

## Design

The interaction model is inspired by
[github-mastermind](https://github.com/github-mastermind), adapted for
Minesweeper:

- Issue rooms as the board surface
- Comment commands as moves
- Hidden signed state preserves game integrity
- Authored bot comments provide the feedback loop

Game state is carried as a signed HMAC-SHA256 token embedded in an HTML
comment within bot replies, ensuring the mine layout stays hidden and
tamper-proof.
