# BOOTSTRAP

## Purpose

Prepare the clean target repository before starting the unattended factory run.

This bootstrap is already complete for this prepared sandbox. Keep this file as
the contract for reproducing the bootstrap if needed.

## Target Repo

- repository shell in use: `github-issue-minesweeper`
- local directory:
  `/workspaces/repo/repo`

## Bootstrap Principle

Seed only the control plane first.

Do not pre-copy the gameplay engine, GitHub workflow implementation, rendering
logic, or Docker runtime code into the repo. That is the factory's job.

## What Was Seeded Into This Repo

- `AGENTS.md`
- `SPEC.md`
- `ROADMAP.md`
- `HANDOFF.md`
- `STATUS.md`
- `WORKFLOW.md`
- `BOOTSTRAP.md`
- `.gitignore`
- `README.md`
- `Makefile`
- `requirements.txt`
- `config.yaml`
- `factory/`
- `factory-jobs/`

## What Was Intentionally Not Seeded

- final gameplay engine modules
- final GitHub Actions workflow files
- final issue templates
- final rendering assets
- final Docker runtime files
- live GitHub credentials or secrets

## Initial Target Repo Shape

Before the first factory run, the repo should remain mostly control-plane files
plus a minimal bootstrap shell.

That is enough. The factory should create the implementation in bounded phases.

## Bootstrap Sequence Used

1. Create the target repo shell.
2. Write the product and execution-control documents.
3. Add a minimal `Makefile`, `requirements.txt`, and `config.yaml`.
4. Generate the linear factory runner from `WORKFLOW.md`.
5. Prepare the Docker sandbox around this repo.
6. Start the prepared sandbox run with:

```bash
make factory-run
```

## Definition Of Done

Bootstrap is complete when:

- the target repo contains the control-plane files
- the repo has a bounded linear factory job sequence
- the container harness is set to operate on the target repo
- the next action is the unattended linear factory run
