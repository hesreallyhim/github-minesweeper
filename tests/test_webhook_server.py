"""Tests for webhook HTTP delivery handling."""

from __future__ import annotations

import hashlib
import hmac
import json

from minesweeper.webhook_server import handle_delivery

TEST_SECRET = "webhook-secret"


def _sign(body: bytes) -> str:
    digest = hmac.new(
        TEST_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def test_handle_delivery_rejects_wrong_path():
    status, payload = handle_delivery(
        path="/not-webhook",
        headers={},
        body=b"{}",
        processor=lambda event, payload: {},
        webhook_secret=TEST_SECRET,
    )
    assert status == 404
    assert payload["error"] == "not_found"


def test_handle_delivery_rejects_invalid_signature():
    body = b'{"ok":true}'
    status, payload = handle_delivery(
        path="/webhook",
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=deadbeef",
        },
        body=body,
        processor=lambda event, payload: {},
        webhook_secret=TEST_SECRET,
    )
    assert status == 401
    assert payload["error"] == "invalid_signature"


def test_handle_delivery_rejects_missing_event():
    body = b'{"ok":true}'
    status, payload = handle_delivery(
        path="/webhook",
        headers={"X-Hub-Signature-256": _sign(body)},
        body=body,
        processor=lambda event, payload: {},
        webhook_secret=TEST_SECRET,
    )
    assert status == 400
    assert payload["error"] == "missing_event"


def test_handle_delivery_rejects_invalid_json():
    body = b"{"
    status, payload = handle_delivery(
        path="/webhook",
        headers={
            "X-GitHub-Event": "issue_comment",
            "X-Hub-Signature-256": _sign(body),
        },
        body=body,
        processor=lambda event, payload: {},
        webhook_secret=TEST_SECRET,
    )
    assert status == 400
    assert payload["error"] == "invalid_json"


def test_handle_delivery_processes_valid_delivery():
    body = json.dumps({"action": "opened"}).encode("utf-8")
    seen: dict[str, object] = {}

    status, payload = handle_delivery(
        path="/webhook",
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": _sign(body),
        },
        body=body,
        processor=lambda event, parsed: seen.update(
            {"event": event, "payload": parsed}
        ) or {"action": "create_room", "result": None},
        webhook_secret=TEST_SECRET,
    )

    assert status == 202
    assert payload["status"] == "accepted"
    assert payload["event"] == "issues"
    assert payload["action"] == "create_room"
    assert seen["event"] == "issues"
    assert seen["payload"] == {"action": "opened"}


def test_handle_delivery_allows_unsigned_when_secret_unset():
    body = b'{"action":"opened"}'
    status, payload = handle_delivery(
        path="/webhook",
        headers={"X-GitHub-Event": "issues"},
        body=body,
        processor=lambda event, parsed: {"action": "create_room", "result": None},
        webhook_secret="",
    )
    assert status == 202
    assert payload["action"] == "create_room"
