# Privacy and Data Handling

- Updated: 2026-04-16
- Status: current implementation baseline

This repository hosts a GitHub-native game. Gameplay is driven by GitHub issue
events and comments.

## Summary

- The game processes only the data needed to run gameplay.
- The system does not use analytics SDKs, ads, trackers, or external LLM APIs.
- In the Cloudflare Worker mode, GitHub webhook payloads are processed in
  Cloudflare runtime memory and are not forwarded to other services.

## Processing Paths

There are two runtime paths in this repository:

1. GitHub Actions workflows
2. Cloudflare Worker webhook runtime (`edge-worker/`)

Both paths consume GitHub event payloads and write results back to GitHub via
GitHub API.

## Data Received

From GitHub webhooks/events, the runtime may receive:

- Repository metadata (`repository.full_name`)
- Issue metadata (`issue.number`, labels, issue opener login)
- Comment metadata (`comment.id`, comment body, comment author login)
- Sender login (`sender.login`)
- Delivery metadata (`X-GitHub-Event`, `X-GitHub-Delivery`)

## Data Used (Minimum Necessary)

The game logic uses only what is required for:

- ownership checks (issue opener vs command sender)
- command parsing (`/reveal`, `/flag`, etc.)
- state progression (signed state chain)
- idempotency (`processed_comment_ids`)
- posting updated board comments
- updating game labels

The mine layout is never exposed directly; only signed state markers and board
render outputs are used.

## Data Transmitted

The runtime transmits data to:

1. GitHub API (required)
   - Read issue comments (to load prior signed state)
   - Post bot comment responses
   - Add/remove issue labels
2. Cloudflare platform (Worker mode only)
   - Receives webhook request and executes runtime

No other third-party transmission is implemented by default.

## Data Not Transmitted by Design

- Webhook payloads are not forwarded to other external APIs.
- Secrets are not included in comments, labels, or responses.
- Raw payload bodies are not intentionally logged by runtime code in this repo.

## Data Stored

Persistent storage in this repository is limited to gameplay artifacts:

- Bot comments in GitHub issues (rendered board + signed state marker)
- Optional leaderboard records in `data/games/*.json` and derived outputs

No separate user database is used in the default path.

## Secrets

Secrets are expected to be stored in platform secret managers:

- GitHub Actions secrets (workflow path)
- Cloudflare Worker secrets (Worker path)

Required secret names and setup are documented in:

- `docs/operator-notes.md`
- `docs/cloudflare-worker-setup.md`

## Retention and Deletion

- Gameplay history follows GitHub issue/comment retention.
- Removing issues/comments in GitHub removes those gameplay records.
- Leaderboard files are repository content and can be removed by maintainers.

## Operator Responsibilities

Operators should:

- set only required secrets
- rotate secrets periodically
- avoid enabling unnecessary telemetry/log forwarding
- keep runtime paths lean and remove migration-only compatibility behavior once
  rollout decisions are finalized

## Contact / Change Control

This document should be updated whenever data flows, storage behavior, or
runtime providers change.
