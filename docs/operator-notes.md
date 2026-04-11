# Operator Notes

## Overview

This document covers deployment and operational concerns for running
GitHub Issue Minesweeper in a repository.

## Requirements

- A GitHub repository with Actions enabled.
- A `GITHUB_TOKEN` secret (available by default in Actions).
- A `MINESWEEPER_SECRET` secret for signing game state tokens (HMAC-SHA256).
- Python 3.11+ runtime in the Actions environment.

## Secrets

| Secret               | Purpose                                    |
|----------------------|--------------------------------------------|
| `GITHUB_TOKEN`       | Post bot comments, manage labels           |
| `MINESWEEPER_SECRET` | Sign and verify hidden game state tokens   |

The `MINESWEEPER_SECRET` should be a random string of at least 32
characters. Generate one with:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

## GitHub Labels

The following labels should exist in the repository:

| Label                       | Purpose                     |
|-----------------------------|-----------------------------|
| `game:minesweeper`          | Active game room            |
| `game:minesweeper:won`      | Completed room (player won) |
| `game:minesweeper:lost`     | Completed room (player lost)|
| `game:minesweeper:archived` | Archived/given-up room      |

## Workflows

Two GitHub Actions workflows handle the game loop:

- **minesweeper-room-open.yml** — Triggered when an issue with the
  `game:minesweeper` label is opened. Initializes the room and posts the
  first board.
- **minesweeper-room-comment.yml** — Triggered when a comment is created
  on an issue with the `game:minesweeper` label. Parses the command,
  applies the move, and posts the updated board.

## Configuration

Game settings are in `config.yaml` at the repository root. The v1 preset
is a 9x9 board with 10 mines.

## Local Development

```bash
# Set up the development environment
make bootstrap

# Run the test suite
make test

# Run lint checks
make lint

# Replay a fixture sequence locally (open → reveal → flag)
make simulate-room

# Replay specific fixtures
PYTHONPATH=src python scripts/replay_fixture.py \
    tests/fixtures/github/issue-open.json \
    tests/fixtures/github/owner-reveal.json

# Replay all fixtures in a directory
PYTHONPATH=src python scripts/replay_fixture.py tests/fixtures/github/
```

## Docker

```bash
# Build the local Docker image
make docker-build

# Run tests inside Docker
make docker-test

# Replay fixtures inside Docker
make docker-replay
```

The Docker image includes all source, tests, and fixtures. It uses
`python:3.11-slim` with `PYTHONPATH=/app/src` pre-set. The default
command runs the test suite.

## Launch Checklist

See `docs/launch-checklist.md` for a complete pre-launch checklist
covering repository setup, secrets, labels, local validation, and
live smoke testing.

## Troubleshooting

- **State token errors**: Verify `MINESWEEPER_SECRET` is set and matches
  across workflow runs. A changed secret invalidates all active games.
- **Duplicate moves**: The engine tracks processed comment IDs and
  silently skips duplicates.
- **Multiple active rooms**: The engine enforces one active room per
  player. A second room attempt should be rejected.
