# V1 Game Contract

This document is the concrete implementation contract for the unattended
factory run.

When product docs are vague, this file wins.

## Product Frame

Build a GitHub-native, single-player Minesweeper game where:

- opening an issue starts a room
- the issue opener is the room owner
- gameplay happens through issue comments
- bot responses are the board surface
- hidden signed state preserves integrity across turns

The intended feel is mechanically adjacent to `github-mastermind`, but the game
rules are Minesweeper.

## V1 Board Preset

Start with one canonical preset and make it work well before generalizing:

- rows: `9`
- cols: `9`
- mines: `10`
- coordinate style: spreadsheet-style (`A1` through `I9`)

Support for alternative presets can be designed later, but v1 should fully
implement the beginner board first.

## Canonical Commands

The engine must support these commands:

- `/reveal <cell>`
- `/flag <cell>`
- `/unflag <cell>`
- `/chord <cell>`
- `/giveup`

Parsing rules:

- commands are case-insensitive
- coordinates are case-insensitive
- surrounding whitespace is ignored
- only the first recognized command in a comment needs to be honored in v1
- malformed commands should receive an authored help response, not a crash

## Room Ownership And Safety

- only the issue opener can change room state
- comments from other users should produce either a polite no-op response or be
  silently ignored in a consistent way
- one active room per player in v1
- duplicate webhook/comment deliveries must be idempotent
- already-processed comment ids must not advance state twice

## Hidden State Contract

The preferred state marker is an HTML comment embedded in bot output:

```html
<!-- MINESWEEPER_STATE_V1: <payload>.<sig> -->
```

The token should be a signed payload in the spirit of `github-mastermind`.

Required payload fields:

- `schema`
- `version`
- `room_key`
- `issue_number`
- `owner`
- `rows`
- `cols`
- `mines`
- `seed` or equivalent deterministic board derivation input
- `revealed`
- `flagged`
- `phase`
- `seq`
- `processed_comment_ids`

Rules:

- tampered tokens must be rejected
- stale state should not be allowed to move backward
- a valid transition may increment `seq` by at most one logical move
- the mine layout must never be rendered directly unless the room is lost or
  given up

## Repository Surfaces To Produce

These are the main files and directories the unattended run should aim to
prepare:

- `src/minesweeper/`
  - `config.py`
  - `coords.py`
  - `engine.py`
  - `state.py`
  - `commands.py`
  - `render.py`
  - `github_events.py`
  - `room_service.py`
- `tests/`
  - engine tests
  - state tests
  - orchestration tests
  - renderer tests
- `tests/fixtures/github/`
  - issue-open payload
  - owner reveal payload
  - owner flag payload
  - non-owner command payload
  - duplicate delivery payload
  - win-path payload
  - loss-path payload
- `.github/ISSUE_TEMPLATE/minesweeper-room.yml`
- `.github/workflows/minesweeper-room-open.yml`
- `.github/workflows/minesweeper-room-comment.yml`
- `scripts/replay_fixture.py`
- `Dockerfile`

Exact filenames may vary slightly when justified, but the repo should land on a
coherent equivalent of the list above.

## Rendering Contract

Use a fenced monospace board for predictable GitHub alignment.

Preferred shape:

```text
   A B C D E F G H I
 1 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 2 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
 3 ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜ ⬜
```

Recommended symbols:

- hidden: `⬜`
- flagged: `🚩`
- mine: `💣`
- exploded mine: `💥`
- empty revealed cell: `·`
- numbered cells: plain digits `1` through `8`

Bot response sections should be stable and authored:

1. room/status heading
2. result sentence for the move
3. rendered board
4. short command reminder when useful
5. hidden state marker comment

## Event Handling Contract

Issue opened event:

- initializes the room
- posts the first board comment
- writes the signed hidden state
- applies active-room labeling

Issue comment event:

- loads the latest valid room state
- ignores comments from bots as needed
- parses one command
- applies the transition if valid
- posts the updated board/status comment
- updates labels on win/loss/give-up

## Local Validation Contract

The unattended pass does not need live GitHub end-to-end validation.

It does need:

- deterministic unit tests for engine/state logic
- fixture-driven tests for issue-open and issue-comment orchestration
- a local replay tool, ideally `scripts/replay_fixture.py`
- a Docker path that can run the core local checks

The minimum acceptable local commands are:

- `make test`
- `make simulate-room`
- `make docker-build`

## Acceptance Boundary For The Prepared Run

This prepared run is successful when:

- the main implementation files exist
- the game contract is encoded in code and tests
- Docker-local validation is practical
- the repository is ready for a later live GitHub validation pass

This prepared run does not fail merely because live GitHub workflow execution
was not exercised yet.
