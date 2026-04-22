# Cloudflare Worker Setup (Webhook Fast Path)

- Updated: 2026-04-22
- Status: experimental

This repo now includes a Cloudflare Worker implementation under
`edge-worker/` that can process Minesweeper GitHub webhooks directly.

For the data minimization and transmission policy for this path, see
`PRIVACY.md`.

## Why This Exists

The Worker path removes GitHub Actions startup latency from the move hot path.

## Current Scope

- Endpoint: `POST /webhook`
- Events handled:
  - `issues` (`action=opened`)
  - `issue_comment` (`action=created`)
- Signature verification: `X-Hub-Signature-256`
- GitHub auth: App JWT exchange to installation token
- Token cache: in-memory per-installation token reuse until near expiry
- State chain: signed HTML state marker (`MINESWEEPER_STATE_V1`)
- Race handling: reconciles missing owner commands between latest state and
  current comment.
- Label gate: gameplay rooms use `game:minesweeper`.

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
npx wrangler secret put GITHUB_APP_ID
npx wrangler secret put GITHUB_APP_PRIVATE_KEY
npx wrangler secret put MINESWEEPER_SECRET
```

Notes:

- `GITHUB_WEBHOOK_SECRET`: shared secret configured on the GitHub webhook.
- `GITHUB_APP_ID`: numeric GitHub App ID.
- `GITHUB_APP_PRIVATE_KEY`: GitHub App PEM private key.
- `MINESWEEPER_SECRET`: same signing secret used for game state integrity.

### Secret Operations

- Set secrets in Cloudflare Worker only; never in source-controlled files.
- Rotate `GITHUB_WEBHOOK_SECRET` and webhook setting together.
- Rotate `GITHUB_APP_PRIVATE_KEY` and verify token exchange and comment writes.
- Keep `MINESWEEPER_SECRET` stable during active games; rotating it invalidates
  all existing state chains.

## Optional Vars

Configured in `wrangler.jsonc`:

- `GAME_ROWS` (default `"9"`)
- `GAME_COLS` (default `"9"`)
- `GAME_MINES` (default `"10"`)

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

1. Create/update a GitHub App and set webhook URL to the Worker URL.
2. App webhook events:
   - `Issues`
   - `Issue comment`
3. App permissions:
   - `Issues`: Read and write
   - `Metadata`: Read
4. Install the App on the target repository.
5. Set App webhook secret to match `GITHUB_WEBHOOK_SECRET`.
6. Disable move-handling Actions workflows to avoid duplicate processing:
   - `.github/workflows/minesweeper-room-open.yml`
   - `.github/workflows/minesweeper-room-comment.yml`
   - `.github/workflows/minesweeper-room-click.yml`

## Rollout Guidance

Target is direct cutover to Worker move handling with sub-10s worst-case
latency and typical response in low single-digit seconds.

## Known Constraints

- Webhook payloads must come from a GitHub App installation webhook
  (`installation.id` required for token exchange).
