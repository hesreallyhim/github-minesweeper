# Click Relay Contract (V1)

This document defines the relay contract for clickable board cells.

## Purpose

GitHub Markdown links cannot directly call `workflow_dispatch` or
`repository_dispatch`. They must navigate to an HTTP endpoint first.

The relay endpoint receives a signed click token from the board link and
dispatches the `minesweeper-click` workflow event.

## Incoming Link

Hidden-cell links are rendered as:

`<MINESWEEPER_CLICK_BASE_URL>?token=<signed>&issue=<n>&cell=<label>&seq=<n>`

`token` is the authoritative input; other query fields are hints only.

## Relay Requirements

1. Authenticate the GitHub user.
2. Enforce user is allowed to play this room (usually room owner).
3. Call GitHub REST API:

`POST /repos/{owner}/{repo}/dispatches`

Body:

```json
{
  "event_type": "minesweeper-click",
  "client_payload": {
    "issue_number": 123,
    "click_token": "<token>",
    "actor": "username",
    "request_id": "optional-idempotency-key"
  }
}
```

## Repository-side Validation

The workflow handler validates:

- click token signature (`MINESWEEPER_SECRET`)
- token expiry (`exp`)
- target room identity (`room_key`, `issue_number`)
- sequence freshness (`seq` must equal latest room state)
- actor ownership check (if relay provides `actor`)

## Latency Guidance

- Keep relay stateless.
- Reuse HTTP connections to GitHub API.
- Dispatch immediately; do not poll for completion in relay.
- Return fast acknowledgement to browser, then optionally redirect back to issue.
- Keep workflow runner steps minimal (already implemented with sparse checkout
  and no dependency installation).
