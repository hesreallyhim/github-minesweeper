# Low-Latency GitHub App Design

- Status: draft
- Updated: 2026-04-16
- Owner: maintainers

## Goal

Cut player-perceived move latency by removing GitHub Actions startup time from
the hot path while keeping game state and gameplay artifacts GitHub-native.

## Constraints

- Gameplay contract remains issue/comment driven.
- Authoritative state remains signed state token in bot comments.
- No external database required.
- GitHub API is the only required API surface for game data and writes.

## Why This Path

Current move handling is Actions-based. Even with minimal checkout and install,
workflow startup and queueing dominate latency. A GitHub App webhook processor
keeps a warm process and executes the move directly.

## Architecture (Minimal)

1. **GitHub App**
   - Permissions: Issues (read/write), Metadata (read).
   - Subscribed events: `issues`, `issue_comment`.
2. **Webhook Runtime**
   - Single HTTPS endpoint for webhook delivery.
   - Verifies `X-Hub-Signature-256`.
   - Converts payload into existing `minesweeper.github_events` handlers.
3. **GitHub API Client**
   - Creates installation token per delivery.
   - Reads issue comments and posts bot replies.
4. **Existing Engine**
   - Reuse `room_service`, `github_events`, `state`, `render`.

No external persistence is required in v1. The signed state chain remains in
GitHub comments.

## Event Flow

### Issue Open

1. Receive `issues.opened`.
2. Call `handle_issue_opened`.
3. Post initial board comment with signed state.
4. Apply labels.

### Issue Comment (Move)

1. Receive `issue_comment.created`.
2. Fetch latest state and reconcile missing earlier owner moves.
3. Call `handle_issue_comment`.
4. Post updated board + signed state.
5. Apply terminal labels and optional leaderboard write.

## Concurrency + Ordering

- Webhook ordering is not guaranteed.
- Keep current reconciliation behavior: replay all missing owner commands
  between latest signed state and current comment.
- Keep processed-comment idempotency from state chain.
- If parallel deliveries occur, the second delivery should recover via the
  same reconciliation logic.

## Latency Budget (Target)

- Webhook ingress + signature verify: `< 50ms`
- GitHub API read comments: `200-900ms`
- Engine + render: `< 25ms`
- Post reply comment: `300-1000ms`
- End-to-end target: `~0.8s - 2.5s` typical, much lower than Actions cold runs.

## Security Model

- Validate webhook signature with app webhook secret.
- Use short-lived installation tokens only.
- Keep `MINESWEEPER_SECRET` for state signing.
- Reject non-owner commands exactly as current logic does.

## Implementation Plan

### Phase A: Runtime Scaffold

- [ ] Add `app/webhook_server.py` with `/webhook` route.
- [ ] Add GitHub App auth helper (JWT -> installation token).
- [ ] Add minimal REST adapter currently using stdlib HTTP.

### Phase B: Handler Reuse

- [ ] Route `issues.opened` -> `handle_issue_opened`.
- [ ] Route `issue_comment.created` -> `handle_issue_comment`.
- [ ] Reuse existing reconciliation path from `entrypoints`.

### Phase C: Operations

- [ ] Add Docker target for webhook runtime.
- [ ] Add local replay harness for webhook payload fixtures.
- [ ] Add latency logging (`received_at`, `reply_posted_at`, `duration_ms`).

### Phase D: Rollout

- [ ] Run webhook in shadow mode (log-only) against fixture replays.
- [ ] Enable in one test repo.
- [ ] Keep Actions workflows for leaderboard jobs; disable move handling
      workflows after verification.

## Current Progress Snapshot

- [x] Reconciliation fix for out-of-order move processing merged in core path.
- [x] Regression tests added for `move N + 1` preserving `move N`.
- [ ] GitHub App runtime scaffold not started.
