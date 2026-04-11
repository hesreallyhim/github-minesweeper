# Job 05: Docker Simulation And Launch Polish

## Scope
Execute only Phase 5: Docker Simulation And Launch Polish from `WORKFLOW.md`.

## Required Outcome
- complete the assigned phase scope only
- update `HANDOFF.md` and `STATUS.md` before stopping
- record blockers instead of drifting into later phases

## Phase Source

```markdown
### Phase 5: Docker Simulation And Launch Polish
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
```
