# Job 04: Rendering And Player Feedback

## Scope
Execute only Phase 4: Rendering And Player Feedback from `WORKFLOW.md`.

## Required Outcome
- complete the assigned phase scope only
- update `HANDOFF.md` and `STATUS.md` before stopping
- record blockers instead of drifting into later phases

## Phase Source

```markdown
### Phase 4: Rendering And Player Feedback
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
```
