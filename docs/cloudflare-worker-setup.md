# Cloudflare Worker Setup (Webhook Fast Path)

- Updated: 2026-04-16
- Status: experimental

This repo now includes a Cloudflare Worker implementation under
`edge-worker/` that can process Minesweeper GitHub webhooks directly.

## Why This Exists

The Worker path removes GitHub Actions startup latency from the move hot path.

## Current Scope

- Endpoint: `POST /webhook`
- Events handled:
  - `issues` (`action=opened`)
  - `issue_comment` (`action=created`)
- Signature verification: `X-Hub-Signature-256`
- State chain: signed HTML state marker (`MINESWEEPER_STATE_V1`)
- Race handling: reconciles missing owner commands between latest state and
  current comment.
- Safety gate: only issues with label `game:minesweeper:edge` are processed by
  this Worker.

## Cloudflare Auth

If your Cloudflare auth is GitHub-based, Wrangler login is still:

```bash
cd edge-worker
npx wrangler login
npx wrangler whoami
```

Wrangler will open the Cloudflare OAuth flow in the browser.

## Required Worker Secrets

Set these in the Worker:

```bash
cd edge-worker
npx wrangler secret put GITHUB_WEBHOOK_SECRET
npx wrangler secret put GITHUB_PAT
npx wrangler secret put MINESWEEPER_SECRET
```

Notes:

- `GITHUB_WEBHOOK_SECRET`: shared secret configured on the GitHub webhook.
- `GITHUB_PAT`: GitHub token with permission to read/write issues/labels in the
  target repo.
- `MINESWEEPER_SECRET`: same signing secret used for game state integrity.

## Optional Vars

Configured in `wrangler.jsonc`:

- `GAME_ROWS` (default `"9"`)
- `GAME_COLS` (default `"9"`)
- `GAME_MINES` (default `"10"`)
- `EDGE_LABEL` (optional env var; defaults to `game:minesweeper:edge`)

## Local Dev

```bash
cd edge-worker
npm install
npx tsc --noEmit
npx wrangler dev
```

## Deploy

```bash
cd edge-worker
npx wrangler deploy
```

After deploy, use the Worker URL as the GitHub webhook URL, for example:

`https://github-minesweeper-webhook.<subdomain>.workers.dev/webhook`

## GitHub Wiring

1. Add/update repository webhook to Worker URL.
2. Subscribe to events:
   - `Issues`
   - `Issue comment`
3. Set webhook secret to match `GITHUB_WEBHOOK_SECRET`.
4. For test issues, apply label `game:minesweeper:edge`.

## Rollout Guidance

- Keep existing GitHub Actions workflows active while testing edge-labeled
  rooms only.
- Once satisfied with latency and behavior, migrate issue templates to apply
  edge label by default and then retire the move workflows.

## Known Constraints

- This Worker runtime is intentionally isolated to edge-labeled rooms for now.
- It assumes a valid `GITHUB_PAT` secret is present in Cloudflare.
