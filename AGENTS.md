# AGENTS.md

Treat this repository as the implementation target for a GitHub-native,
issue-based single-player Minesweeper game.

`docs/v1-game-contract.md` is the most concrete implementation contract. When
other planning files are ambiguous, follow that document.

## Product Direction

- Opening an issue starts a personal game room.
- Only the issue opener can affect that room.
- Gameplay happens through issue comments such as:
  - `/reveal B3`
  - `/flag H7`
  - `/chord C4`
  - `/giveup`
- The product should feel mechanically adjacent to `github-mastermind`:
  - issue rooms as the board
  - comment-driven turns
  - authored bot responses
  - hidden signed game state carried through bot output
  - one active room per player
- The board itself is Minesweeper, not Mastermind:
  - hidden minefield
  - numbered reveals
  - flagging
  - win on revealing all safe cells
  - fenced monospace board rendering in bot comments

## Repository Role

- This is the product repo, not the donor repo.
- The donor project is `github-mastermind`, used only as a mechanics reference.
- Keep this repo implementation-focused.

## Execution Model

- This repo is intended to be worked by unattended factory jobs.
- The outer runner owns commits.
- Job prompts must not create commits directly unless explicitly instructed.
- Update `HANDOFF.md` and `STATUS.md` during unattended jobs.

## Engineering Constraints

- Prefer Python for the initial engine and workflow tooling.
- Prefer Makefile-managed repeated operations.
- For Python work, prefer a `venv` named `venv`.
- Local development must have a Docker path, even if production runtime is
  GitHub Actions.
- Do not require live GitHub workflow end-to-end validation in the initial
  unattended pass.
- Real GitHub interactions may be validated through fixtures, replayable event
  payloads, and deterministic state tests.

## Game Integrity Constraints

- Hide the mine layout from the player.
- Use a signed, replay-safe state chain or equivalent integrity mechanism so
  issue comments cannot be forged into valid state transitions.
- Prefer the HTML comment marker shape described in
  `docs/v1-game-contract.md`.
- Prevent multiple simultaneous active rooms for the same player in v1.
- Reject or safely ignore commands from non-owners.
- Preserve a clear audit trail in bot comments and local tests.

## V1 Scope Boundaries

- Single-player only.
- One repository hosts the game.
- One issue represents one game room.
- Minimal leaderboard or hall-of-fame support is allowed, but broad social or
  multi-player systems are not required for v1.
- Do not add external databases or hosted services to the default path.
