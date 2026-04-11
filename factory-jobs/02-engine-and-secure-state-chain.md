# Job 02: Engine And Secure State Chain

## Scope
Execute only Phase 2: Engine And Secure State Chain from `WORKFLOW.md`.

## Required Outcome
- complete the assigned phase scope only
- update `HANDOFF.md` and `STATUS.md` before stopping
- record blockers instead of drifting into later phases

## Phase Source

```markdown
### Phase 2: Engine And Secure State Chain
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
```
