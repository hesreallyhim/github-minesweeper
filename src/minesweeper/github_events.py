"""GitHub webhook event normalization and routing.

Handles issue-open and issue-comment events for the game workflow.
Produces response dicts that callers (workflow entrypoints or fixture
replays) use to post comments and update labels.
"""

from __future__ import annotations

from typing import Any

from minesweeper.commands import parse_command
from minesweeper.render import render_malformed_command, render_non_owner_response
from minesweeper.room_service import (
    apply_move,
    create_room,
    load_state_from_comment,
    validate_owner,
)


def handle_issue_opened(
    payload: dict[str, Any],
    *,
    secret: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Process an issue-opened event and initialize a room.

    Parameters
    ----------
    payload : dict
        The GitHub ``issues`` webhook payload (action == "opened").
    secret : str, optional
        HMAC signing secret. Falls back to env/default.
    seed : int, optional
        Deterministic seed for testing. Uses time-based seed if None.

    Returns
    -------
    dict with keys:
        action : str  -- "create_room"
        body : str    -- the comment body to post
        state : dict  -- the initial state payload
        labels_add : list[str]
        issue_number : int
        owner : str
        repo : str
    """
    issue = payload.get("issue", {})
    issue_number = issue.get("number", 0)
    owner = issue.get("user", {}).get("login", "")
    repo = payload.get("repository", {}).get("full_name", "")

    room = create_room(
        owner=owner,
        issue_number=issue_number,
        repo=repo,
        secret=secret,
        seed=seed,
    )
    return {
        "action": "create_room",
        "body": room["body"],
        "state": room["state"],
        "labels_add": room["labels_add"],
        "issue_number": issue_number,
        "owner": owner,
        "repo": repo,
    }


def handle_issue_comment(
    payload: dict[str, Any],
    *,
    prior_comment_body: str | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Process an issue-comment event and apply a move.

    Parameters
    ----------
    payload : dict
        The GitHub ``issue_comment`` webhook payload (action == "created").
    prior_comment_body : str, optional
        The body of the last bot comment containing the state token.
        In production, this is fetched via the GitHub API. For tests,
        it is passed directly.
    secret : str, optional
        HMAC signing secret.

    Returns
    -------
    dict with keys:
        action : str  -- "move", "non_owner", "no_command", "no_state",
                         "duplicate", "game_over"
        body : str | None  -- comment body to post (None = skip posting)
        state : dict | None
        result : str | None
        labels_add : list[str]
        labels_remove : list[str]
        issue_number : int
        owner : str
        repo : str
        comment_id : int
    """
    issue = payload.get("issue", {})
    comment = payload.get("comment", {})
    issue_number = issue.get("number", 0)
    owner = issue.get("user", {}).get("login", "")
    repo = payload.get("repository", {}).get("full_name", "")
    comment_id = comment.get("id", 0)
    sender = payload.get("sender", {}).get("login", "")
    comment_body = comment.get("body", "")

    base = {
        "issue_number": issue_number,
        "owner": owner,
        "repo": repo,
        "comment_id": comment_id,
    }

    # Owner check
    if not validate_owner(payload, owner):
        return {
            **base,
            "action": "non_owner",
            "body": render_non_owner_response(sender),
            "state": None,
            "result": None,
            "labels_add": [],
            "labels_remove": [],
        }

    # Parse command
    cmd = parse_command(comment_body)
    if cmd is None:
        return {
            **base,
            "action": "no_command",
            "body": render_malformed_command(comment_body),
            "state": None,
            "result": None,
            "labels_add": [],
            "labels_remove": [],
        }

    # Load prior state
    if prior_comment_body is None:
        return {
            **base,
            "action": "no_state",
            "body": "Could not find the game state. "
            "The room may be corrupted or the bot comment was deleted.",
            "state": None,
            "result": None,
            "labels_add": [],
            "labels_remove": [],
        }

    prior_state = load_state_from_comment(prior_comment_body, secret)
    if prior_state is None:
        return {
            **base,
            "action": "no_state",
            "body": "Could not verify the game state. "
            "The state token may have been tampered with.",
            "state": None,
            "result": None,
            "labels_add": [],
            "labels_remove": [],
        }

    # Apply the move
    move = apply_move(prior_state, cmd, comment_id, secret=secret)

    # Map internal result to action label
    result_str = move.get("result", "")
    if result_str == "duplicate":
        action_label = "duplicate"
    elif result_str == "game_over":
        action_label = "game_over"
    else:
        action_label = "move"

    return {
        **base,
        "action": action_label,
        "body": move["body"],
        "state": move["state"],
        "result": result_str,
        "labels_add": move.get("labels_add", []),
        "labels_remove": move.get("labels_remove", []),
    }
