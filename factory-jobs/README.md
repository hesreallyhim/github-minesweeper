# Factory Jobs

These job specs are meant to be consumed by the linear factory runner in
`factory/run_sequence.sh`.

## Intended Runner

- authoritative sandbox entrypoint: `make factory-run`
- resume entrypoint: `make factory-run-resume RUN_DIR=.factory-runs/<run-dir>`
- global host entrypoint: `ccc factory-run /abs/path/to/repo-or-sandbox`
- preferred container family: `rw-repo-tempfs-ro-rootfs-rust`
- authoritative workflow source: `WORKFLOW.md`

## Sequence

- `01-repo-foundation-and-rules-contract.md`
- `02-engine-and-secure-state-chain.md`
- `03-github-issue-orchestration.md`
- `04-rendering-and-player-feedback.md`
- `05-docker-simulation-and-launch-polish.md`

## Cold-Start Read Order

Every fresh execution should read, when present:

1. `AGENTS.md`
2. `WORKFLOW.md`
3. `SPEC.md`
4. `docs/v1-game-contract.md`
5. `HANDOFF.md`
6. `STATUS.md`
7. `ROADMAP.md`
8. `BOOTSTRAP.md`
9. `factory-jobs/README.md`
10. the assigned job file
