# HANDOFF

## Incremental Updates (2026-04-16)

- Resolved `move N + 1` race by reconciling missing prior owner commands in
  `room_comment_entrypoint` before applying the current move. This prevents
  stale-state progression when workflow runs arrive out of order.
- Added `tests/test_entrypoints.py` regression coverage for:
  - replay of missing owner commands into prior state
  - full entrypoint processing that preserves `move N` in `move N+1` output
- Added `docs/low-latency-github-app-design.md` capturing the low-latency
  GitHub App webhook architecture, constraints, latency budget, and phased
  implementation plan.
- Added `src/minesweeper/webhook_app.py` and `tests/test_webhook_app.py`
  to scaffold low-latency webhook processing (signature verification, payload
  parsing, and routing through existing handlers via injectable effectors).
- Added `src/minesweeper/webhook_server.py`, `tests/test_webhook_server.py`,
  and `make webhook-serve` for a runnable `/webhook` HTTP path using the
  webhook processor scaffold.
- Added an experimental Cloudflare Worker runtime in `edge-worker/` with
  webhook signature verification, direct GitHub API comment/label updates,
  signed state-chain processing, and move reconciliation for race safety.
- Added `docs/cloudflare-worker-setup.md` for auth, secrets, deployment, and
  staged rollout guidance.

## Completed

- Phase 0 Planning Freeze: product control documents locked.
- Phase 0.5 Target Repo Bootstrap: control plane seeded.
- Phase 1 Repo Foundation And Rules Contract: complete.
  - Python package skeleton at `src/minesweeper/` with all contract modules
    (config, coords, engine, state, commands, render, github_events,
    room_service) — stubs raise `NotImplementedError` for later phases.
  - Test skeleton at `tests/` with placeholder tests for all modules (16
    tests pass).
  - GitHub fixtures at `tests/fixtures/github/` — issue-open, owner-reveal,
    owner-flag, non-owner-command, duplicate-delivery, win-path, loss-path.
  - `.github/ISSUE_TEMPLATE/minesweeper-room.yml` — room creation template.
  - `.github/workflows/` — placeholder workflows for room-open and
    room-comment events.
  - `scripts/replay_fixture.py` — placeholder replay tool.
  - `docs/gameplay.md` — player-facing gameplay guide.
  - `docs/operator-notes.md` — deployment and operations reference.
  - README upgraded to reflect the actual game concept.
  - All lint checks pass (`ruff check`).
  - Config loading works (`config.yaml` → `minesweeper.config`).
- Phase 2 Engine And Secure State Chain: complete.
  - `src/minesweeper/coords.py` — spreadsheet-style coordinate parsing
    (A1–I9), case-insensitive, whitespace-tolerant, with roundtrip
    `coord_to_label`.
  - `src/minesweeper/engine.py` — full Board class with deterministic seeded
    mine generation, reveal with flood-fill, flag, unflag, chord,
    win/loss/give-up detection, cell display helpers, and serialization
    roundtrip (`to_state_fields` / `from_state`). Enums for Phase,
    CellState, MoveResult.
  - `src/minesweeper/commands.py` — regex-based command parser for /reveal,
    /flag, /unflag, /chord, /giveup. Case-insensitive, first-match,
    whitespace-tolerant.
  - `src/minesweeper/state.py` — HMAC-SHA256 signed state tokens with
    base64url-encoded JSON payloads. Encode/decode/extract roundtrip,
    tamper rejection, initial state factory, room key derivation. HTML
    comment marker format: `<!-- MINESWEEPER_STATE_V1: payload.sig -->`.
  - 91 tests passing across coords (15), engine (28), commands (16),
    state (16), plus remaining Phase 1 tests.
  - All lint checks pass.
- Phase 3 GitHub Issue Orchestration: complete.
  - `src/minesweeper/room_service.py` — room creation (`create_room`),
    owner validation (`validate_owner`), move application (`apply_move`),
    state loading from bot comments (`load_state_from_comment`), game-over
    handling, result message generation, label management for win/loss/giveup.
  - `src/minesweeper/github_events.py` — event normalization and routing.
    `handle_issue_opened` initializes a room from an issue-opened payload.
    `handle_issue_comment` processes commands with owner-only enforcement,
    duplicate-delivery idempotency, tamper-resistant state chain, and
    terminal game state handling.
  - `src/minesweeper/render.py` — board rendering with fenced monospace
    output, symbol map per contract (⬜🚩💣💥·1-8), room status header,
    non-owner rejection message, malformed command help text.
  - `src/minesweeper/entrypoints.py` — CLI entrypoints for GitHub Actions
    workflows (`room_open_entrypoint`, `room_comment_entrypoint`). Loads
    event payloads from `GITHUB_EVENT_PATH`, posts comments and manages
    labels via the GitHub REST API.
  - `.github/workflows/minesweeper-room-open.yml` — finalized workflow with
    Python entrypoint, permissions, and secret refs.
  - `.github/workflows/minesweeper-room-comment.yml` — finalized workflow
    with bot-comment filtering, Python entrypoint, permissions.
  - 122 tests passing (up from 91). New orchestration tests cover:
    room creation, owner reveal/flag, non-owner rejection, duplicate
    delivery idempotency, state chain integrity, tampered state rejection,
    malformed commands, win path (full game), loss path, give-up, game-over
    rejection, render integration.
  - All lint checks pass (`ruff check`).
- Phase 4 Rendering And Player Feedback: complete.
  - `src/minesweeper/render.py` — polished with authored response templates.
    Structured response assembly via `format_room_open` and
    `format_move_response`. Room headers with phase-specific emoji
    (⛏️/🏆/💥/🏳️). Stats line (mines remaining, cells revealed).
    Command reminder shown only during active play. Game-over notice
    via `render_game_over_notice`. All contract sections: heading,
    result sentence, board, stats, command reminder.
  - `src/minesweeper/room_service.py` — upgraded to use render module's
    structured assembly functions. Richer result messages with emoji for
    win (🏆), loss (💥), flag (🚩), give-up (🏳️).
  - `src/minesweeper/leaderboard.py` — lightweight repo-native hall of
    fame. `LeaderboardEntry` dataclass, `render_leaderboard` produces a
    Markdown table sorted by fewest moves with medal emoji for top 3,
    `make_entry_from_state` creates entries from terminal game state.
  - README upgraded with quick-start walkthrough showing actual bot
    output format, board symbols table, room rules.
  - `docs/gameplay.md` upgraded with rendered output examples showing
    room creation and win scenarios, stats line docs, game-over behavior.
  - 148 tests passing (up from 122).
  - All lint checks pass (`ruff check`).
- Phase 5 Docker Simulation And Launch Polish: complete.
  - `scripts/replay_fixture.py` — full fixture replay tool. Supports single
    fixture, multi-fixture chained sequence, and directory glob modes.
    Chains state between events (prior bot comment body passed to next
    event). Prints rendered board output, action labels, label changes,
    and a summary with pass/fail status.
  - `Dockerfile` — `python:3.11-slim` based image with all source, tests,
    fixtures, and scripts. Pre-sets `PYTHONPATH`, `PYTHONIOENCODING`, and
    dev signing secret. Default command runs `pytest tests -q`.
  - Makefile targets updated:
    - `simulate-room` — replays issue-open → owner-reveal → owner-flag
      sequence through the local engine.
    - `docker-build` — builds the `gh-issue-minesweeper` Docker image.
    - `docker-test` — runs the test suite inside Docker.
    - `docker-replay` — replays the fixture sequence inside Docker.
  - `docs/launch-checklist.md` — complete pre-launch checklist covering
    repository setup, secrets, labels, local validation, live smoke test,
    and explicitly documents what is NOT validated locally.
  - `docs/operator-notes.md` — updated with Docker usage, replay script
    usage, and launch checklist reference.
  - Fixed surrogate-pair emoji encoding in `render.py`, `room_service.py`,
    and corresponding tests (Python `\ud83d\udea9` surrogates replaced with
    proper `\U0001f6a9` codepoints). This was a pre-existing issue from
    Phase 4 that prevented emoji from rendering correctly in non-UTF-16
    environments.
  - 148 tests passing. All lint checks pass.

## Current Focus

Phase 5 is complete. All five implementation phases are done.

## Next Recommended Action

1. Run `make docker-build && make docker-test` in a Docker-enabled
   environment to validate the full Docker path.
2. Follow `docs/launch-checklist.md` to deploy to a live GitHub repository.
3. Perform the live smoke test described in the checklist.

## What Remains Unvalidated Against Live GitHub

- Webhook delivery and event payload shape from real GitHub triggers.
- `GITHUB_TOKEN` permissions and API rate limits in production.
- Real issue comment posting and label management via the GitHub API.
- Concurrent webhook delivery and race condition handling.
- Issue template rendering in the GitHub UI.
- One-active-room-per-player enforcement across multiple issues.

## Important Constraints

- The factory pass does not need live end-to-end validation against real
  GitHub workflows.
- The repo prepares main implementation files, tests, fixtures, and a
  local Docker simulation path.
- Gameplay is single-player in v1.
- Issue-room ownership is strict.
- No external infrastructure in the happy path.
