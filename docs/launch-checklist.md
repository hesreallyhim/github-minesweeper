# Launch Checklist

Pre-launch checklist for deploying GitHub Issue Minesweeper to a live
repository.

## Repository Setup

- [ ] Create a new GitHub repository (or use this one).
- [ ] Set repository visibility as desired (public recommended for the
      social game experience).
- [ ] Enable GitHub Actions in the repository settings.

## Secrets

- [ ] Generate a signing secret:
      `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- [ ] Add `MINESWEEPER_SECRET` to the repository secrets
      (Settings > Secrets and variables > Actions).
- [ ] Verify `GITHUB_TOKEN` is available (automatic in Actions).

## Labels

Create the following labels in the repository:

- [ ] `game:minesweeper` (active game room)
- [ ] `game:minesweeper:won` (player won)
- [ ] `game:minesweeper:lost` (player lost)
- [ ] `game:minesweeper:archived` (given up / abandoned)

## Files

Verify these files are present and up to date:

- [ ] `.github/ISSUE_TEMPLATE/minesweeper-room.yml`
- [ ] `.github/workflows/minesweeper-room-open.yml`
- [ ] `.github/workflows/minesweeper-room-comment.yml`
- [ ] `src/minesweeper/` — all engine modules
- [ ] `config.yaml`
- [ ] `requirements.txt`

## Local Validation

Before going live, run these locally:

- [ ] `make test` — all tests pass
- [ ] `make simulate-room` — fixture replay produces correct output
- [ ] `make docker-build` — Docker image builds successfully
- [ ] `make docker-test` — tests pass inside Docker

## Live Smoke Test

After deploying to the target repository:

- [ ] Open a new issue using the Minesweeper Room template.
- [ ] Verify the bot posts an initial board comment.
- [ ] Comment `/reveal A1` and verify the board updates.
- [ ] Comment `/flag B2` and verify the flag appears.
- [ ] Comment `/giveup` and verify the game ends.
- [ ] Verify labels are updated correctly at each phase transition.
- [ ] Open a second issue to verify one-active-room enforcement
      (if implemented).

## What Is NOT Validated Locally

The following require live GitHub workflow execution and cannot be fully
validated in the local Docker path:

- Webhook delivery and event payload shape from real GitHub triggers.
- `GITHUB_TOKEN` permissions and API rate limits in production.
- Real issue comment posting and label management via the GitHub API.
- Concurrent webhook delivery and race condition handling.
- Issue template rendering in the GitHub UI.
- One-active-room-per-player enforcement across multiple issues
  (requires GitHub API queries not exercised in fixtures).

These should be validated during the live smoke test above.
