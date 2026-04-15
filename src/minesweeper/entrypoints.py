"""CLI entrypoints for GitHub Actions workflow steps.

These are invoked by the workflow YAML files. Each reads the event
payload from GITHUB_EVENT_PATH and uses the GitHub API (via
GITHUB_TOKEN) to post comments and manage labels.

In local/fixture mode, the entrypoints can also accept a JSON file
path as a CLI argument.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import sys
from typing import Any

from minesweeper.github_events import (
    handle_click_dispatch,
    handle_issue_comment,
    handle_issue_opened,
)

TERMINAL_PHASES = {"won", "lost", "given_up"}


def _load_event() -> dict[str, Any]:
    """Load the GitHub event payload from env or CLI arg."""
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not path:
        print("Error: no event payload path provided", file=sys.stderr)
        sys.exit(1)
    with open(path) as fh:
        return json.load(fh)


def _github_api_post_comment(
    repo: str, issue_number: int, body: str
) -> None:
    """Post an issue comment via the GitHub REST API.

    Requires GITHUB_TOKEN in the environment.
    """
    import urllib.request

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("Warning: GITHUB_TOKEN not set, skipping API call",
              file=sys.stderr)
        return

    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments"
    data = json.dumps({"body": body}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(f"Posted comment (status {resp.status})")
    except Exception as exc:
        print(f"Failed to post comment: {exc}", file=sys.stderr)
        sys.exit(1)


def _github_api_get_content(
    repo: str,
    path: str,
) -> tuple[dict[str, Any] | None, str | None]:
    """Fetch repository file content metadata and decoded JSON payload."""
    import urllib.request
    import urllib.parse

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return None, None

    quoted_path = urllib.parse.quote(path, safe="/")
    url = f"https://api.github.com/repos/{repo}/contents/{quoted_path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None, None

    sha = body.get("sha")
    content = body.get("content")
    if not isinstance(content, str):
        return None, sha
    try:
        raw = base64.b64decode(content.encode("ascii"), validate=False)
        decoded = json.loads(raw.decode("utf-8"))
    except Exception:
        return None, sha
    if not isinstance(decoded, dict):
        return None, sha
    return decoded, sha


def _github_api_upsert_json_content(
    repo: str,
    path: str,
    payload: dict[str, Any],
    *,
    message: str,
    sha: str | None = None,
) -> bool:
    """Create/update a JSON file in the repository via the contents API."""
    import urllib.request
    import urllib.parse

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return False

    quoted_path = urllib.parse.quote(path, safe="/")
    url = f"https://api.github.com/repos/{repo}/contents/{quoted_path}"
    raw = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(raw).decode("ascii"),
    }
    if sha:
        body["sha"] = sha

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req):
            return True
    except Exception as exc:
        print(f"Failed to write {path}: {exc}", file=sys.stderr)
        return False


def _maybe_record_terminal_game(
    *,
    repo: str,
    issue_number: int,
    state: dict[str, Any] | None,
) -> None:
    """Persist terminal game records in data/games for leaderboard builds."""
    if not state:
        return
    phase = str(state.get("phase", "")).strip().lower()
    if phase not in TERMINAL_PHASES:
        return

    record_path = f"data/games/{issue_number}.json"
    existing, existing_sha = _github_api_get_content(repo, record_path)
    if existing is not None:
        # One issue is one room. Keep first terminal record as canonical.
        return

    record = {
        "schema": "minesweeper-game-result-v1",
        "issue": issue_number,
        "player": state.get("owner", ""),
        "result": phase,
        "moves": int(state.get("seq", 0)),
        "rows": int(state.get("rows", 0)),
        "cols": int(state.get("cols", 0)),
        "mines": int(state.get("mines", 0)),
        "completed_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
    }
    _github_api_upsert_json_content(
        repo,
        record_path,
        record,
        message=f"leaderboard: record game #{issue_number}",
        sha=existing_sha,
    )


def _github_api_update_labels(
    repo: str, issue_number: int,
    add: list[str], remove: list[str],
) -> None:
    """Add and remove labels via the GitHub REST API."""
    import urllib.request

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return

    for label in add:
        url = (
            f"https://api.github.com/repos/{repo}"
            f"/issues/{issue_number}/labels"
        )
        data = json.dumps({"labels": [label]}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req):
                pass
        except Exception:
            pass

    for label in remove:
        url = (
            f"https://api.github.com/repos/{repo}"
            f"/issues/{issue_number}/labels/{label}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github+json",
            },
            method="DELETE",
        )
        try:
            with urllib.request.urlopen(req):
                pass
        except Exception:
            pass


def _fetch_latest_bot_comment(
    repo: str, issue_number: int
) -> str | None:
    """Fetch the last bot comment containing a state token.

    Scans comments in reverse order looking for the state marker.
    """
    import urllib.request

    from minesweeper.state import extract_state_token

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return None

    url = (
        f"https://api.github.com/repos/{repo}"
        f"/issues/{issue_number}/comments?per_page=30&sort=created&direction=desc"
    )
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            comments = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    for c in comments:
        body = c.get("body", "")
        if extract_state_token(body) is not None:
            return body
    return None


def room_open_entrypoint() -> None:
    """Entrypoint for the minesweeper-room-open workflow."""
    payload = _load_event()
    result = handle_issue_opened(payload)

    body = result.get("body", "")
    repo = result.get("repo", "")
    issue_number = result.get("issue_number", 0)

    if body and repo and issue_number:
        _github_api_post_comment(repo, issue_number, body)
        _github_api_update_labels(
            repo, issue_number, result.get("labels_add", []), []
        )

    print(f"Room created for {result.get('owner')} in {repo}#{issue_number}")


def room_comment_entrypoint() -> None:
    """Entrypoint for the minesweeper-room-comment workflow."""
    payload = _load_event()
    repo = payload.get("repository", {}).get("full_name", "")
    issue_number = payload.get("issue", {}).get("number", 0)

    # Fetch the last bot comment with state
    prior_body = _fetch_latest_bot_comment(repo, issue_number)

    result = handle_issue_comment(
        payload, prior_comment_body=prior_body
    )

    body = result.get("body")
    if body and repo and issue_number:
        _github_api_post_comment(repo, issue_number, body)
        _github_api_update_labels(
            repo, issue_number,
            result.get("labels_add", []),
            result.get("labels_remove", []),
        )
        _maybe_record_terminal_game(
            repo=repo,
            issue_number=issue_number,
            state=result.get("state"),
        )

    action = result.get("action", "unknown")
    print(f"Handled comment (action={action}, result={result.get('result')})")


def room_click_entrypoint() -> None:
    """Entrypoint for repository_dispatch click events."""
    payload = _load_event()
    repo = payload.get("repository", {}).get("full_name", "")
    raw_issue_number = payload.get("client_payload", {}).get("issue_number", 0)
    try:
        issue_number = int(raw_issue_number)
    except (TypeError, ValueError):
        issue_number = 0

    prior_body = _fetch_latest_bot_comment(repo, issue_number)
    result = handle_click_dispatch(
        payload,
        prior_comment_body=prior_body,
    )

    body = result.get("body")
    if body and repo and issue_number:
        _github_api_post_comment(repo, issue_number, body)
        _github_api_update_labels(
            repo, issue_number,
            result.get("labels_add", []),
            result.get("labels_remove", []),
        )
        _maybe_record_terminal_game(
            repo=repo,
            issue_number=issue_number,
            state=result.get("state"),
        )

    action = result.get("action", "unknown")
    print(f"Handled click dispatch (action={action}, result={result.get('result')})")


if __name__ == "__main__":
    # Allow direct invocation for testing:
    #   python -m minesweeper.entrypoints open <payload.json>
    #   python -m minesweeper.entrypoints comment <payload.json>
    if len(sys.argv) >= 2 and sys.argv[1] == "open":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        room_open_entrypoint()
    elif len(sys.argv) >= 2 and sys.argv[1] == "comment":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        room_comment_entrypoint()
    elif len(sys.argv) >= 2 and sys.argv[1] == "click":
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        room_click_entrypoint()
    else:
        print("Usage: python -m minesweeper.entrypoints <open|comment|click> [payload.json]",
              file=sys.stderr)
        sys.exit(1)
