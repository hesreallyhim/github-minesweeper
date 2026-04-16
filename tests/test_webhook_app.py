"""Tests for GitHub App webhook event processing helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from minesweeper.room_service import create_room
from minesweeper.webhook_app import (
    WebhookEffectors,
    parse_webhook_payload,
    process_webhook_event,
    verify_webhook_signature,
)
from tests.conftest import load_fixture

TEST_SECRET = "test-secret-key"
TEST_REPO = "testowner/github-issue-minesweeper"
TEST_ISSUE = 1


def test_verify_webhook_signature_accepts_valid_signature():
    body = b'{"ok":true}'
    sig = hmac.new(TEST_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    header = f"sha256={sig}"
    assert verify_webhook_signature(body, header, TEST_SECRET) is True


def test_verify_webhook_signature_rejects_invalid_signature():
    body = b'{"ok":true}'
    assert (
        verify_webhook_signature(body, "sha256=deadbeef", TEST_SECRET)
        is False
    )


def test_parse_webhook_payload_rejects_non_json():
    assert parse_webhook_payload(b"not json") is None


def test_parse_webhook_payload_rejects_non_dict_json():
    assert parse_webhook_payload(json.dumps([1, 2, 3]).encode("utf-8")) is None


def test_process_webhook_event_issue_open_posts_comment_and_labels():
    payload = load_fixture("issue-open.json")
    posted: dict[str, Any] = {}
    labels: dict[str, Any] = {}

    effectors = WebhookEffectors(
        get_prior_comment_body=lambda repo, issue, raw: None,
        post_comment=lambda repo, issue, body: posted.update(
            {"repo": repo, "issue": issue, "body": body}
        ),
        update_labels=lambda repo, issue, add, remove: labels.update(
            {"repo": repo, "issue": issue, "add": list(add), "remove": list(remove)}
        ),
    )

    result = process_webhook_event(
        event_name="issues",
        payload=payload,
        effectors=effectors,
        secret=TEST_SECRET,
    )

    assert result["action"] == "create_room"
    assert posted["repo"] == TEST_REPO
    assert posted["issue"] == TEST_ISSUE
    assert "MINESWEEPER_STATE_V1" in posted["body"]
    assert labels["add"] == ["game:minesweeper"]
    assert labels["remove"] == []


def test_process_webhook_event_issue_comment_uses_prior_state_callback():
    room = create_room(
        owner="testplayer",
        issue_number=TEST_ISSUE,
        repo=TEST_REPO,
        secret=TEST_SECRET,
        seed=42,
    )
    prior_body = room["body"]
    payload = load_fixture("owner-reveal.json")
    posted: dict[str, Any] = {}

    effectors = WebhookEffectors(
        get_prior_comment_body=lambda repo, issue, raw: prior_body,
        post_comment=lambda repo, issue, body: posted.update({"body": body}),
        update_labels=lambda repo, issue, add, remove: None,
    )

    result = process_webhook_event(
        event_name="issue_comment",
        payload=payload,
        effectors=effectors,
        secret=TEST_SECRET,
    )

    assert result["action"] == "move"
    assert result["state"]["seq"] == 1
    assert "body" in posted


def test_process_webhook_event_ignored_for_unsupported_events():
    payload = load_fixture("issue-open.json")
    called = {"post": False, "labels": False}

    effectors = WebhookEffectors(
        get_prior_comment_body=lambda repo, issue, raw: None,
        post_comment=lambda repo, issue, body: called.update({"post": True}),
        update_labels=lambda repo, issue, add, remove: called.update(
            {"labels": True}
        ),
    )

    result = process_webhook_event(
        event_name="pull_request",
        payload=payload,
        effectors=effectors,
        secret=TEST_SECRET,
    )

    assert result["action"] == "ignored"
    assert called["post"] is False
    assert called["labels"] is False
