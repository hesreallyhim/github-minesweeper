"""GitHub App webhook processing helpers.

This module provides a low-latency event processor that reuses the existing
game handlers without requiring GitHub Actions in the move hot path.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from minesweeper.github_events import handle_issue_comment, handle_issue_opened


GetPriorCommentBody = Callable[[str, int, dict[str, Any]], str | None]
PostComment = Callable[[str, int, str], None]
UpdateLabels = Callable[[str, int, list[str], list[str]], None]
RecordTerminalGame = Callable[[str, int, dict[str, Any] | None], None]


def _noop_record_terminal_game(
    repo: str,
    issue_number: int,
    state: dict[str, Any] | None,
) -> None:
    """Default callback for terminal game recording."""
    del repo, issue_number, state


@dataclass(frozen=True)
class WebhookEffectors:
    """Side-effect adapters used by webhook event processing."""

    get_prior_comment_body: GetPriorCommentBody
    post_comment: PostComment
    update_labels: UpdateLabels
    record_terminal_game: RecordTerminalGame = _noop_record_terminal_game


def get_signing_secret() -> str:
    """Return the state signing secret."""
    return os.environ.get("MINESWEEPER_SECRET", "dev-secret-do-not-use-in-prod")


def verify_webhook_signature(
    body: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify GitHub's ``X-Hub-Signature-256`` header."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    actual = signature_header[len("sha256="):]
    return hmac.compare_digest(actual, expected)


def parse_webhook_payload(body: bytes) -> dict[str, Any] | None:
    """Parse raw webhook JSON body into a dict payload."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def process_webhook_event(
    *,
    event_name: str,
    payload: dict[str, Any],
    effectors: WebhookEffectors,
    secret: str | None = None,
) -> dict[str, Any]:
    """Process one GitHub webhook event and apply side effects.

    Supported events:
      - ``issues`` with action ``opened``
      - ``issue_comment`` with action ``created``
    """
    action = str(payload.get("action", ""))
    secret_value = secret or get_signing_secret()
    repo = str(payload.get("repository", {}).get("full_name", ""))
    issue_number = int(payload.get("issue", {}).get("number", 0) or 0)

    if event_name == "issues" and action == "opened":
        result = handle_issue_opened(payload, secret=secret_value)
    elif event_name == "issue_comment" and action == "created":
        prior_body = effectors.get_prior_comment_body(repo, issue_number, payload)
        result = handle_issue_comment(
            payload,
            prior_comment_body=prior_body,
            secret=secret_value,
        )
    else:
        return {
            "action": "ignored",
            "event": event_name,
            "body": None,
            "labels_add": [],
            "labels_remove": [],
            "state": None,
            "repo": repo,
            "issue_number": issue_number,
        }

    body = result.get("body")
    if body and repo and issue_number:
        effectors.post_comment(repo, issue_number, body)
        effectors.update_labels(
            repo,
            issue_number,
            list(result.get("labels_add", [])),
            list(result.get("labels_remove", [])),
        )
        effectors.record_terminal_game(repo, issue_number, result.get("state"))
    return result
