# WORKFLOW

## Execution Model

This project should progress through fresh-session factory jobs, not through
one long conversational thread.

Preferred execution substrate:

- the existing make-driven factory harness in
  `/Users/hesreallyhim/coding/projects/claude-code-containers/containers/rw-repo-tempfs-ro-rootfs-rust`
- specifically the linear `make factory-run` pattern already used for prepared
  sandbox jobs

This repository should therefore provide:

- durable workflow documents
- bounded job specs
- short handoff/state files

Do not replace the external container runner.

## Runner Notes

- Authoritative sandbox entrypoint: `make factory-run`
- Resume entrypoint: `make factory-run-resume RUN_DIR=...`
- Bootstrap is already complete in this repository.
- The sandbox wrapper should call `repo/factory/claude-linear.json`.
- Use one fresh agent run per job.

## Cold-Start Read Order

Every fresh execution should read:

1. `AGENTS.md`
2. `SPEC.md`
3. `docs/v1-game-contract.md`
4. `ROADMAP.md`
5. `HANDOFF.md`
6. `STATUS.md`
7. `BOOTSTRAP.md`
8. the assigned file in `factory-jobs/`

## Execution Rules

- update `HANDOFF.md` and `STATUS.md` before stopping
- preserve blockers and high-signal failure context
- prefer Makefile-managed repeated operations
- do not create commits from inside the job prompt unless explicitly instructed
- live GitHub end-to-end workflow validation is optional in this prepared pass
- local Docker validation, deterministic fixtures, and main-file preparation are
  still required

## Phases

### Phase 1: Repo Foundation And Rules Contract — `completed`
- **Objective**: Create a clean Python project skeleton, repository layout, and
  product-facing contracts for the game.
- **Inputs**: `AGENTS.md`, `SPEC.md`, `ROADMAP.md`, `Makefile`,
  `requirements.txt`, `config.yaml`, `docs/v1-game-contract.md`
- **Steps**:
  1. Create initial Python package and test directories.
  2. Add a repo-local docs structure for gameplay and operator notes.
  3. Create placeholder `.github` directories for issue templates and
     workflows.
  4. Align the package/file names with the contract in
     `docs/v1-game-contract.md`.
  5. Make the root `README.md` reflect the actual game concept rather than only
     the bootstrap note.
  6. Ensure local bootstrap commands are coherent and non-destructive before
     full implementation exists.
- **Outputs**:
  - base package layout under `src/`
  - base test layout under `tests/`
  - `.github/ISSUE_TEMPLATE/` and `.github/workflows/` scaffolding
  - upgraded repo README and docs shell
- **Checkpoint**: the repo structure is coherent and no longer just a document
  pile
- **Estimated tool calls**: 45

### Phase 2: Engine And Secure State Chain — `completed`
- **Objective**: Implement the Minesweeper rules engine, coordinate parsing,
  and hidden signed state lifecycle.
- **Inputs**: Phase 1 repo layout, `config.yaml`, product rules in `SPEC.md`
- **Steps**:
  1. Implement board generation with deterministic seeded layouts.
  2. Implement reveal, flood fill, flag, unflag, chord, win, and loss logic.
  3. Implement coordinate parsing and command normalization.
  4. Implement the HTML-comment hidden token contract from
     `docs/v1-game-contract.md`.
  5. Implement signed state encoding/decoding or equivalent integrity layer.
  6. Add tests for valid transitions, invalid commands, owner/replay safety
     data, and state tamper rejection.
- **Outputs**:
  - core engine modules
  - state token helpers
  - parser helpers
  - deterministic tests
- **Checkpoint**: core gameplay works locally without GitHub
- **Estimated tool calls**: 70

### Phase 3: GitHub Issue Orchestration — `completed`
- **Objective**: Build the GitHub-facing room lifecycle and comment command
  handling path.
- **Inputs**: working engine and state chain from Phase 2
- **Steps**:
  1. Create the room issue template and any supporting config.
  2. Define workflow triggers for issue open and issue comment events.
  3. Build event normalization and routing code for room initialization and move
     handling.
  4. Implement owner-only command application and replay-safe comment handling.
  5. Add fixture-based tests for issue-open and issue-comment payloads.
  6. Prefer stable fixture filenames that mirror the contract document.
- **Outputs**:
  - issue template
  - workflow files
  - orchestration entrypoints
  - event fixtures
  - fixture-driven tests
- **Checkpoint**: fixture replay can simulate a room being created and played
- **Estimated tool calls**: 80

### Phase 4: Rendering And Player Feedback — `completed`
- **Objective**: Make the room outputs readable, game-like, and aligned with
  the repo-native feel of `github-mastermind`.
- **Inputs**: working orchestration path from Phase 3
- **Steps**:
  1. Implement the fenced monospace board contract from
     `docs/v1-game-contract.md`.
  2. Implement board rendering for hidden, revealed, flagged, exploded, won,
     and lost states.
  3. Implement authored response templates for successful moves, malformed
     commands, non-owner interference, win, loss, and give-up.
  4. Add a lightweight hall-of-fame or leaderboard path only if it stays cheap
     and repo-native.
  5. Update the README and docs to explain the actual player loop.
  6. Add snapshot-style tests for rendered room outputs.
- **Outputs**:
  - renderer modules
  - response templates
  - optional leaderboard path
  - updated player-facing docs
- **Checkpoint**: a human can understand the room flow from rendered outputs
- **Estimated tool calls**: 65

### Phase 5: Docker Simulation And Launch Polish — `completed`
- **Objective**: Prepare the repo for local Docker validation and later launch.
- **Inputs**: main gameplay and GitHub-facing files from earlier phases
- **Steps**:
  1. Add a Dockerfile and local run story for replaying issue/comment fixtures.
  2. Implement `scripts/replay_fixture.py` or a coherent equivalent.
  3. Add make targets for bootstrap, tests, fixture replay, and Docker checks.
  4. Add a launch checklist and operator notes.
  5. Run the local validation path inside the repo's Docker setup when
     practical.
  6. Explicitly document what remains unvalidated against live GitHub.
- **Outputs**:
  - Dockerfile and optional compose file
  - operator docs
  - launch checklist
  - final handoff notes
- **Checkpoint**: the main files are prepared and locally runnable in Docker
    without requiring live GitHub workflow end-to-end validation
- **Estimated tool calls**: 60

## Failure Handling

On failure:

- preserve changed files
- update `HANDOFF.md` with the blocker
- update `STATUS.md`
- stop unless later jobs remain independently meaningful
