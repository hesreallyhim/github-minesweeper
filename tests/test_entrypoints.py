"""Tests for entrypoint orchestration behavior."""

from __future__ import annotations

from minesweeper import entrypoints
from minesweeper.coords import parse_coord
from minesweeper.room_service import create_room
from minesweeper.state import decode_state, extract_state_token
from tests.conftest import load_fixture

TEST_SECRET = "test-secret-key"
TEST_SEED = 42
TEST_REPO = "testowner/github-issue-minesweeper"
TEST_ISSUE_NUMBER = 1
TEST_OWNER = "testplayer"


def _comment(
    comment_id: int,
    *,
    body: str,
    login: str,
    bot: bool = False,
) -> dict:
    return {
        "id": comment_id,
        "body": body,
        "user": {
            "login": login,
            "bot": bot,
        },
    }


def test_reconcile_replays_missing_owner_commands(monkeypatch):
    opening = create_room(
        owner=TEST_OWNER,
        issue_number=TEST_ISSUE_NUMBER,
        repo=TEST_REPO,
        secret=TEST_SECRET,
        seed=TEST_SEED,
    )
    room_body = opening["body"]

    payload = load_fixture("owner-reveal.json")
    payload = dict(payload)
    payload["comment"] = dict(payload["comment"])
    payload["comment"]["id"] = 101
    payload["comment"]["body"] = "/reveal C3"

    comments = [
        _comment(
            10,
            body=room_body,
            login="github-actions[bot]",
            bot=True,
        ),
        _comment(100, body="/reveal B3", login=TEST_OWNER),
        _comment(101, body="/reveal C3", login=TEST_OWNER),
    ]
    monkeypatch.setattr(
        entrypoints,
        "_github_api_list_issue_comments",
        lambda repo, issue_number, per_page=100: comments,
    )
    monkeypatch.setenv("MINESWEEPER_SECRET", TEST_SECRET)

    prior_body = entrypoints._reconcile_prior_comment_body_for_issue_comment(
        repo=TEST_REPO,
        issue_number=TEST_ISSUE_NUMBER,
        payload=payload,
    )

    assert prior_body is not None
    token = extract_state_token(prior_body)
    assert token is not None
    state = decode_state(token, TEST_SECRET)
    assert state is not None
    assert state["seq"] == 1
    assert 100 in state["processed_comment_ids"]
    assert 101 not in state["processed_comment_ids"]


def test_room_comment_entrypoint_preserves_previous_move(monkeypatch):
    opening = create_room(
        owner=TEST_OWNER,
        issue_number=TEST_ISSUE_NUMBER,
        repo=TEST_REPO,
        secret=TEST_SECRET,
        seed=TEST_SEED,
    )
    room_body = opening["body"]

    payload = load_fixture("owner-reveal.json")
    payload = dict(payload)
    payload["repository"] = dict(payload["repository"])
    payload["issue"] = dict(payload["issue"])
    payload["comment"] = dict(payload["comment"])
    payload["sender"] = dict(payload["sender"])
    payload["repository"]["full_name"] = TEST_REPO
    payload["issue"]["number"] = TEST_ISSUE_NUMBER
    payload["sender"]["login"] = TEST_OWNER
    payload["comment"]["id"] = 101
    payload["comment"]["body"] = "/reveal C3"

    comments = [
        _comment(
            10,
            body=room_body,
            login="github-actions[bot]",
            bot=True,
        ),
        _comment(100, body="/reveal B3", login=TEST_OWNER),
        _comment(101, body="/reveal C3", login=TEST_OWNER),
    ]
    posted: dict[str, str] = {}
    labels: dict[str, list[str]] = {}

    monkeypatch.setenv("MINESWEEPER_SECRET", TEST_SECRET)
    monkeypatch.setattr(entrypoints, "_load_event", lambda: payload)
    monkeypatch.setattr(
        entrypoints,
        "_github_api_list_issue_comments",
        lambda repo, issue_number, per_page=100: comments,
    )
    monkeypatch.setattr(
        entrypoints,
        "_github_api_post_comment",
        lambda repo, issue_number, body: posted.update({"body": body}),
    )
    monkeypatch.setattr(
        entrypoints,
        "_github_api_update_labels",
        lambda repo, issue_number, add, remove: labels.update(
            {"add": list(add), "remove": list(remove)}
        ),
    )
    monkeypatch.setattr(
        entrypoints,
        "_maybe_record_terminal_game",
        lambda repo, issue_number, state: None,
    )

    entrypoints.room_comment_entrypoint()

    assert "body" in posted
    token = extract_state_token(posted["body"])
    assert token is not None
    state = decode_state(token, TEST_SECRET)
    assert state is not None
    assert state["seq"] == 2
    assert 100 in state["processed_comment_ids"]
    assert 101 in state["processed_comment_ids"]
    assert labels["add"] == []
    assert labels["remove"] == []

    b3 = parse_coord("B3", state["rows"], state["cols"])
    c3 = parse_coord("C3", state["rows"], state["cols"])
    revealed = {tuple(cell) for cell in state["revealed"]}
    assert b3 in revealed
    assert c3 in revealed
