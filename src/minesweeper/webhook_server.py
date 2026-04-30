"""Minimal HTTP server for GitHub App webhook delivery."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Mapping

from minesweeper.entrypoints import (
    _github_api_post_comment,
    _github_api_update_labels,
    _maybe_record_terminal_game,
    _reconcile_prior_comment_body_for_issue_comment,
)
from minesweeper.webhook_app import (
    WebhookEffectors,
    parse_webhook_payload,
    process_webhook_event,
    verify_webhook_signature,
)

EventProcessor = Callable[[str, dict[str, Any]], dict[str, Any]]


def _make_default_event_processor() -> EventProcessor:
    """Build the default event processor wired to GitHub REST side effects."""
    effectors = WebhookEffectors(
        get_prior_comment_body=lambda repo, issue_number, payload: (
            _reconcile_prior_comment_body_for_issue_comment(
                repo=repo,
                issue_number=issue_number,
                payload=payload,
            )
        ),
        post_comment=_github_api_post_comment,
        update_labels=_github_api_update_labels,
        record_terminal_game=lambda repo, issue_number, state: (
            _maybe_record_terminal_game(
                repo=repo,
                issue_number=issue_number,
                state=state,
            )
        ),
    )

    def _processor(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        return process_webhook_event(
            event_name=event_name,
            payload=payload,
            effectors=effectors,
        )

    return _processor


def handle_delivery(
    *,
    path: str,
    headers: Mapping[str, str],
    body: bytes,
    processor: EventProcessor,
    webhook_secret: str,
) -> tuple[int, dict[str, Any]]:
    """Process one webhook HTTP delivery and return status + JSON payload."""
    if path != "/webhook":
        return 404, {"error": "not_found"}

    signature = headers.get("X-Hub-Signature-256")
    if webhook_secret:
        if not verify_webhook_signature(body, signature, webhook_secret):
            return 401, {"error": "invalid_signature"}

    event_name = headers.get("X-GitHub-Event", "")
    if not event_name:
        return 400, {"error": "missing_event"}

    payload = parse_webhook_payload(body)
    if payload is None:
        return 400, {"error": "invalid_json"}

    try:
        result = processor(event_name, payload)
    except Exception:
        return 500, {"error": "processing_failed"}

    return 202, {
        "status": "accepted",
        "event": event_name,
        "action": result.get("action"),
        "result": result.get("result"),
    }


class GitHubWebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for GitHub webhook POST deliveries."""

    processor: EventProcessor = staticmethod(_make_default_event_processor())

    def do_POST(self) -> None:  # noqa: N802
        length_header = self.headers.get("Content-Length", "0")
        try:
            content_length = int(length_header)
        except ValueError:
            content_length = 0
        body = self.rfile.read(max(content_length, 0))
        status, payload = handle_delivery(
            path=self.path,
            headers=self.headers,
            body=body,
            processor=self.processor,
            webhook_secret=os.environ.get("GITHUB_WEBHOOK_SECRET", ""),
        )
        self._send_json(status, payload)

    def do_GET(self) -> None:  # noqa: N802
        self._send_json(404, {"error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:
        """Keep server stdout concise and machine-readable."""
        del fmt, args

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def serve(
    *,
    host: str = "0.0.0.0",
    port: int = 8787,
) -> None:
    """Run the webhook HTTP server."""
    server = HTTPServer((host, port), GitHubWebhookHandler)
    print(f"GitHub webhook server listening on http://{host}:{port}/webhook")
    server.serve_forever()


def main() -> None:
    """Entrypoint for ``python -m minesweeper.webhook_server``."""
    host = os.environ.get("MINESWEEPER_WEBHOOK_HOST", "0.0.0.0")
    raw_port = os.environ.get("MINESWEEPER_WEBHOOK_PORT", "8787")
    try:
        port = int(raw_port)
    except ValueError:
        port = 8787
    serve(host=host, port=port)


if __name__ == "__main__":
    main()
