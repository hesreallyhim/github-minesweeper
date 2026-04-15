"""Room lifecycle management.

Handles room creation, active-room enforcement, ownership checks,
move application, and room state transitions.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from minesweeper.commands import ParsedCommand
from minesweeper.config import DEFAULT_COLS, DEFAULT_MINES, DEFAULT_ROWS
from minesweeper.coords import coord_to_label, parse_coord
from minesweeper.engine import Board, MoveResult, Phase
from minesweeper.state import (
    decode_state,
    derive_room_key,
    encode_click_token,
    encode_state,
    extract_state_token,
    make_initial_state,
)


def _get_secret() -> str:
    """Return the HMAC signing secret from the environment."""
    return os.environ.get("MINESWEEPER_SECRET", "dev-secret-do-not-use-in-prod")


def _get_click_base_url() -> str:
    """Return the optional click relay URL base for clickable boards."""
    return os.environ.get("MINESWEEPER_CLICK_BASE_URL", "").strip()


def _get_click_ttl_seconds() -> int:
    """Return click token ttl in seconds."""
    raw = os.environ.get("MINESWEEPER_CLICK_TTL_SECONDS", "120").strip()
    try:
        ttl = int(raw)
    except ValueError:
        ttl = 120
    return max(ttl, 30)


def _with_query_params(base_url: str, params: dict[str, str | int]) -> str:
    """Append/merge query params into base_url."""
    parts = urlsplit(base_url)
    existing = parts.query
    extra = urlencode(params)
    query = f"{existing}&{extra}" if existing else extra
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def _build_hidden_cell_link(
    state: dict[str, Any],
    secret: str,
) -> Callable[[str], str] | None:
    """Build a hidden-cell link factory for reveal clicks."""
    base_url = _get_click_base_url()
    if not base_url:
        return None

    expires_at = int(time.time()) + _get_click_ttl_seconds()

    def _link_for(label: str) -> str:
        token = encode_click_token(
            room_key=state["room_key"],
            issue_number=state["issue_number"],
            owner=state["owner"],
            action="reveal",
            coordinate=label,
            seq=state["seq"],
            expires_at=expires_at,
            secret=secret,
        )
        return _with_query_params(
            base_url,
            {
                "token": token,
                "issue": state["issue_number"],
                "cell": label,
                "seq": state["seq"],
            },
        )

    return _link_for


def _render_board_surface(
    board: Board,
    state: dict[str, Any],
    *,
    secret: str,
    reveal_all: bool,
) -> str:
    """Render the board as a Markdown table (optionally clickable)."""
    from minesweeper.render import render_board_table

    hidden_cell_link = None if reveal_all else _build_hidden_cell_link(state, secret)
    return render_board_table(
        board,
        reveal_all=reveal_all,
        hidden_cell_link=hidden_cell_link,
    )


def create_room(
    owner: str,
    issue_number: int,
    repo: str,
    *,
    rows: int = DEFAULT_ROWS,
    cols: int = DEFAULT_COLS,
    mines: int = DEFAULT_MINES,
    seed: int | None = None,
    secret: str | None = None,
) -> dict[str, Any]:
    """Initialize a new game room for the given owner and issue.

    Returns a dict with:
      - body: the full bot comment body (board + hidden state)
      - state: the raw state payload dict
      - labels_add: labels to apply to the issue
    """
    secret = secret or _get_secret()
    if seed is None:
        seed = int(time.time() * 1000) ^ hash((repo, issue_number, owner))

    room_key = derive_room_key(repo, issue_number, owner)
    state = make_initial_state(
        room_key=room_key,
        issue_number=issue_number,
        owner=owner,
        rows=rows,
        cols=cols,
        mines=mines,
        seed=seed,
    )
    board = Board(rows, cols, mines, seed)
    state_token = encode_state(state, secret)

    from minesweeper.render import (
        format_room_open,
        render_room_header,
        render_stats,
    )

    board_text = _render_board_surface(
        board,
        state,
        secret=secret,
        reveal_all=False,
    )
    header = render_room_header(owner, issue_number, Phase.PLAYING)
    stats = render_stats(board)
    body_content = format_room_open(header, board_text, stats, mines)
    body = f"{body_content}\n\n{state_token}"
    return {
        "body": body,
        "state": state,
        "labels_add": ["game:minesweeper"],
    }


def validate_owner(payload: dict[str, Any], expected_owner: str) -> bool:
    """Check whether the comment author matches the room owner."""
    sender = payload.get("sender", {}).get("login", "")
    return sender.lower() == expected_owner.lower()


def apply_move(
    prior_state: dict[str, Any],
    command: ParsedCommand,
    comment_id: int,
    *,
    secret: str | None = None,
) -> dict[str, Any]:
    """Apply a parsed command against the prior game state.

    Returns a dict with:
      - body: the full bot response body
      - state: the updated state payload dict
      - result: the MoveResult value
      - labels_add: labels to add (if any)
      - labels_remove: labels to remove (if any)
    """
    secret = secret or _get_secret()

    # Duplicate comment check
    if comment_id in prior_state.get("processed_comment_ids", []):
        return {
            "body": None,
            "state": prior_state,
            "result": "duplicate",
            "labels_add": [],
            "labels_remove": [],
        }

    # Reconstruct board from state
    board = Board.from_state(
        rows=prior_state["rows"],
        cols=prior_state["cols"],
        mines=prior_state["mines"],
        seed=prior_state["seed"],
        revealed=prior_state["revealed"],
        flagged=prior_state["flagged"],
        phase=prior_state["phase"],
    )

    # Check if the game is already over
    if board.phase != Phase.PLAYING:
        return _game_over_response(board, prior_state, secret)

    # Apply the command
    move_result, message = _execute_command(board, command)

    # Build updated state
    new_state = dict(prior_state)
    board_fields = board.to_state_fields()
    new_state["revealed"] = board_fields["revealed"]
    new_state["flagged"] = board_fields["flagged"]
    new_state["phase"] = board_fields["phase"]
    new_state["seq"] = prior_state["seq"] + 1
    new_state["processed_comment_ids"] = prior_state.get(
        "processed_comment_ids", []
    ) + [comment_id]

    state_token = encode_state(new_state, secret)

    # Determine reveal_all for terminal states
    reveal_all = board.phase in (Phase.LOST, Phase.WON, Phase.GIVEN_UP)

    from minesweeper.render import (
        format_move_response,
        render_room_header,
        render_stats,
    )

    board_text = _render_board_surface(
        board,
        new_state,
        secret=secret,
        reveal_all=reveal_all,
    )
    header = render_room_header(
        new_state["owner"], new_state["issue_number"], board.phase
    )
    stats = render_stats(board)

    labels_add: list[str] = []
    labels_remove: list[str] = []
    if board.phase == Phase.WON:
        labels_add.append("game:minesweeper:won")
        labels_remove.append("game:minesweeper")
    elif board.phase == Phase.LOST:
        labels_add.append("game:minesweeper:lost")
        labels_remove.append("game:minesweeper")
    elif board.phase == Phase.GIVEN_UP:
        labels_add.append("game:minesweeper:archived")
        labels_remove.append("game:minesweeper")

    body_content = format_move_response(
        header, message, board_text, stats, board.phase
    )
    body = f"{body_content}\n\n{state_token}"
    return {
        "body": body,
        "state": new_state,
        "result": move_result.value,
        "labels_add": labels_add,
        "labels_remove": labels_remove,
    }


def _execute_command(
    board: Board, command: ParsedCommand
) -> tuple[MoveResult, str]:
    """Execute a parsed command on the board, return result and message."""
    action = command.action

    if action == "giveup":
        result = board.give_up()
        return result, "\U0001f3f3\ufe0f You gave up. All mines are revealed."

    # Actions that require a coordinate
    if command.coordinate is None:
        return MoveResult.INVALID, (
            f"The `/{action}` command requires a coordinate "
            f"(e.g. `/{action} B3`)."
        )

    parsed = parse_coord(command.coordinate, board.rows, board.cols)
    if parsed is None:
        return MoveResult.INVALID, (
            f"Invalid coordinate `{command.coordinate}`. "
            f"Use a letter A\u2013{chr(64 + board.cols)} and a number "
            f"1\u2013{board.rows} (e.g. `B3`)."
        )

    row, col = parsed
    label = coord_to_label(row, col)

    if action == "reveal":
        result = board.reveal(row, col)
    elif action == "flag":
        result = board.flag(row, col)
    elif action == "unflag":
        result = board.unflag(row, col)
    elif action == "chord":
        result = board.chord(row, col)
    else:
        return MoveResult.INVALID, f"Unknown action `/{action}`."

    message = _result_message(action, label, result)
    return result, message


def _result_message(action: str, label: str, result: MoveResult) -> str:
    """Build a human-readable message for a move result."""
    if result == MoveResult.WIN:
        return (
            "\U0001f3c6 **You win!** All safe cells have been revealed. "
            "Congratulations!"
        )
    if result == MoveResult.LOSS:
        return (
            f"\U0001f4a5 **BOOM!** You hit a mine at **{label}**. Game over."
        )
    if result == MoveResult.NO_OP:
        return f"No effect \u2014 `/{action} {label}` had nothing to do."
    if result == MoveResult.INVALID:
        return f"Invalid move: `/{action} {label}`."
    # OK
    messages = {
        "reveal": f"Revealed **{label}**.",
        "flag": f"\U0001f6a9 Flagged **{label}**.",
        "unflag": f"Unflagged **{label}**.",
        "chord": f"Chorded around **{label}**.",
    }
    return messages.get(action, f"Applied `/{action} {label}`.")


def _game_over_response(
    board: Board, state: dict, secret: str
) -> dict[str, Any]:
    """Return a response for a command on an already-finished game."""
    from minesweeper.render import render_game_over_notice

    return {
        "body": render_game_over_notice(board.phase),
        "state": state,
        "result": "game_over",
        "labels_add": [],
        "labels_remove": [],
    }


def load_state_from_comment(comment_body: str, secret: str | None = None) -> dict | None:
    """Extract and decode the state token from a bot comment body.

    Returns the decoded state dict, or None if not found or invalid.
    """
    secret = secret or _get_secret()
    token = extract_state_token(comment_body)
    if token is None:
        return None
    return decode_state(token, secret)
