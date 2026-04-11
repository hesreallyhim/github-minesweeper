# Job 03: GitHub Issue Orchestration

## Scope
Execute only Phase 3: GitHub Issue Orchestration from `WORKFLOW.md`.

## Required Outcome
- complete the assigned phase scope only
- update `HANDOFF.md` and `STATUS.md` before stopping
- record blockers instead of drifting into later phases

## Phase Source

```markdown
### Phase 3: GitHub Issue Orchestration
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
```
