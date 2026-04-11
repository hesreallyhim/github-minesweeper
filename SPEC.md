# SPEC

## Project

Build a GitHub-native single-player Minesweeper game where each issue is a
private-feeling public room, comment commands are moves, and GitHub itself is
the board surface.

This repository is the implementation target for that product.

## Product Goal

A player should be able to:

1. open a new issue from the room template
2. receive a fresh concealed board
3. play by commenting commands such as `/reveal B3`
4. see the room update in authored GitHub comments
5. finish a complete game without leaving GitHub

## Primary User

A technically curious GitHub user who enjoys repo-native interaction patterns,
is willing to play inside issue comments, and values mechanical clarity over a
custom web frontend.

## Core Gameplay Loop

- opening an issue initializes a game room
- the room owner is the only effective player for that room
- the engine interprets comment commands
- the bot evaluates the move against hidden state
- the bot posts an updated board and status
- the game ends in win, loss, or give-up

The concrete v1 command, rendering, and hidden-state contract is defined in
`docs/v1-game-contract.md`.

## Command Surface

### Required commands

- `/reveal <cell>`
- `/flag <cell>`
- `/unflag <cell>`
- `/chord <cell>`
- `/giveup`

### Coordinate rules

- coordinates are spreadsheet-style, such as `B3` or `H10`
- command parsing should tolerate surrounding whitespace and case variance
- malformed commands should receive authored help feedback

## Room Rules

- one active room per player in v1
- only the room opener can affect the board
- non-owner comments may be ignored or gently rejected
- spam and replay safety should be handled predictably

## Core Architecture

- Python engine for rules and state transitions
- GitHub issue and issue-comment workflows as the production runtime
- deterministic local fixture replay for development
- Docker-local execution path for the repo's main validation loop
- hidden signed state token or equivalent integrity chain embedded in bot output

## Hidden State Strategy

The mine layout must remain hidden from the player while still allowing the
workflow to validate future moves without trusting mutable issue text alone.

The preferred v1 shape is:

- derive a room key from repository, issue number, and owner
- maintain a signed state payload that includes:
  - board dimensions
  - mine positions or a seed sufficient to derive them
  - revealed cells
  - flagged cells
  - move sequence
  - room phase
  - processed comment ids
- embed the signed token in bot output in a machine-readable but unobtrusive
  way

The preferred marker format is:

```html
<!-- MINESWEEPER_STATE_V1: <payload>.<sig> -->
```

This mirrors the spirit of `github-mastermind` without copying its game rules.

## V1 Included

- issue template for starting a room
- command parser
- core Minesweeper engine
- board and status renderer for GitHub comments
- deterministic tests and replay fixtures
- Docker-local development path
- lightweight hall-of-fame or leaderboard support if it remains repo-native and
  cheap

## V1 Excluded

- multi-player collaboration
- external databases
- custom hosted web UI
- mandatory live GitHub end-to-end workflow validation
- broad moderation or anti-abuse systems beyond basic owner and replay guards

## Success Criteria

- the main implementation files are present and coherent
- the core game loop is testable locally
- Docker can run the primary local validation path
- issue/comment fixtures demonstrate correct room behavior
- the repo is ready for a later live GitHub validation pass if desired
- the implementation materially conforms to `docs/v1-game-contract.md`
