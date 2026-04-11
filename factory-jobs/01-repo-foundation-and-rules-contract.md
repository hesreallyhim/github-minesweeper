# Job 01: Repo Foundation And Rules Contract

## Scope
Execute only Phase 1: Repo Foundation And Rules Contract from `WORKFLOW.md`.

## Required Outcome
- complete the assigned phase scope only
- update `HANDOFF.md` and `STATUS.md` before stopping
- record blockers instead of drifting into later phases

## Phase Source

```markdown
### Phase 1: Repo Foundation And Rules Contract
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
```
