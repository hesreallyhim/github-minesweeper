"""Fixture-driven tests for GitHub event orchestration (Phase 3).

Tests cover:
- issue-open room creation
- owner reveal / flag commands
- non-owner rejection
- duplicate delivery idempotency
- win path
- loss path
- give-up flow
- malformed commands
- game-over rejection
"""

from __future__ import annotations

import time

import pytest

from tests.conftest import load_fixture

from minesweeper.github_events import (
    handle_click_dispatch,
    handle_issue_comment,
    handle_issue_opened,
)
from minesweeper.state import (
    decode_state,
    encode_click_token,
    extract_state_token,
)

# Deterministic seed for reproducible tests
TEST_SECRET = "test-secret-key"
TEST_SEED = 42


class TestHandleIssueOpened:
    """Tests for the issue-opened event handler."""

    def test_creates_room(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)

        assert result["action"] == "create_room"
        assert result["owner"] == "testplayer"
        assert result["issue_number"] == 1
        assert result["repo"] == "testowner/github-issue-minesweeper"
        assert "game:minesweeper" in result["labels_add"]

    def test_room_body_contains_board(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)

        body = result["body"]
        assert "|   | A | B | C |" in body  # table header
        assert "| 1 |" in body  # first row
        assert "`A1`" in body  # hidden cell coordinate

    def test_room_body_contains_state_token(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)

        body = result["body"]
        token = extract_state_token(body)
        assert token is not None

        state = decode_state(token, TEST_SECRET)
        assert state is not None
        assert state["owner"] == "testplayer"
        assert state["phase"] == "playing"
        assert state["seq"] == 0
        assert state["revealed"] == []
        assert state["flagged"] == []

    def test_state_payload_fields(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)

        state = result["state"]
        assert state["schema"] == "v1"
        assert state["rows"] == 9
        assert state["cols"] == 9
        assert state["mines"] == 10
        assert state["seed"] == TEST_SEED
        assert state["room_key"] == "testowner/github-issue-minesweeper#1@testplayer"

    def test_deterministic_with_same_seed(self):
        payload = load_fixture("issue-open.json")
        r1 = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        r2 = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        assert r1["body"] == r2["body"]
        assert r1["state"] == r2["state"]

    def test_clickable_table_when_click_url_set(self, monkeypatch):
        monkeypatch.setenv(
            "MINESWEEPER_CLICK_BASE_URL",
            "https://click.example.test/play",
        )
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        body = result["body"]
        assert "|   | A | B | C |" in body
        assert "[`A1`](https://click.example.test/play?" in body
        assert "token=" in body
        assert "cell=A1" in body


class TestHandleIssueComment:
    """Tests for the issue-comment event handler."""

    def _create_room(self):
        """Helper: create a room and return the body with the state token."""
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        return result["body"]

    def test_owner_reveal(self):
        prior_body = self._create_room()
        payload = load_fixture("owner-reveal.json")

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "move"
        assert result["comment_id"] == 100
        assert result["body"] is not None
        assert "|   | A | B | C |" in result["body"]  # board rendered

        # State was advanced
        state = result["state"]
        assert state["seq"] == 1
        assert 100 in state["processed_comment_ids"]

    def test_owner_flag(self):
        prior_body = self._create_room()
        payload = load_fixture("owner-flag.json")

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "move"
        assert result["comment_id"] == 101
        state = result["state"]
        assert state["seq"] == 1
        assert len(state["flagged"]) > 0 or result["result"] == "no_op"

    def test_owner_multi_cell_flag_without_slash(self):
        from minesweeper.coords import parse_coord

        prior_body = self._create_room()
        payload = load_fixture("owner-flag.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["id"] = 111
        payload["comment"]["body"] = "flag A1 B2"

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "move"
        assert result["result"] == "ok"
        state = result["state"]
        flagged = {tuple(cell) for cell in state["flagged"]}
        assert parse_coord("A1", 9, 9) in flagged
        assert parse_coord("B2", 9, 9) in flagged
        assert state["seq"] == 1

    def test_owner_mixed_multi_line_turn(self):
        from minesweeper.coords import coord_to_label
        from minesweeper.engine import Board

        prior_body = self._create_room()
        payload = load_fixture("owner-reveal.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["id"] = 112

        board = Board(9, 9, 10, TEST_SEED)
        reveal_cell = next(
            (r, c)
            for r in range(9)
            for c in range(9)
            if not board.mine_grid[r][c] and board.adj_counts[r][c] > 0
        )
        mine_cell = sorted(board.mine_set)[0]
        reveal_label = coord_to_label(*reveal_cell)
        mine_label = coord_to_label(*mine_cell)
        payload["comment"]["body"] = f"guess {reveal_label}\nflag {mine_label}"

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "move"
        assert result["result"] == "ok"
        state = result["state"]
        revealed = {tuple(cell) for cell in state["revealed"]}
        flagged = {tuple(cell) for cell in state["flagged"]}
        assert reveal_cell in revealed
        assert mine_cell in flagged
        assert state["seq"] == 1

    def test_rejects_mixed_actions_on_one_line(self):
        prior_body = self._create_room()
        payload = load_fixture("owner-flag.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["id"] = 113
        payload["comment"]["body"] = "flag A1 A4 reveal B3"

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "no_command"
        assert "one action per line" in result["body"]

    def test_rejects_turn_with_non_parseable_token(self):
        prior_body = self._create_room()
        payload = load_fixture("owner-flag.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["id"] = 114
        payload["comment"]["body"] = "reveal A1 B2 3"

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "no_command"
        assert "didn't recognize" in result["body"]

    def test_non_owner_rejected(self):
        prior_body = self._create_room()
        payload = load_fixture("non-owner-command.json")

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "non_owner"
        assert result["state"] is None
        assert "interloper" in result["body"]

    def test_duplicate_delivery_idempotent(self):
        prior_body = self._create_room()

        # First delivery
        payload = load_fixture("owner-reveal.json")
        first = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )
        assert first["action"] == "move"

        # Get the updated state body for the second delivery
        updated_body = first["body"]

        # Second delivery of same comment id
        dup_payload = load_fixture("duplicate-delivery.json")
        second = handle_issue_comment(
            dup_payload, prior_comment_body=updated_body, secret=TEST_SECRET
        )

        assert second["action"] == "duplicate"
        assert second["body"] is None  # no new comment posted

    def test_no_command_in_comment(self):
        prior_body = self._create_room()

        payload = load_fixture("owner-reveal.json")
        # Override comment body to have no command
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["body"] = "Just chatting, no command here"

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["action"] == "no_command"
        assert "didn't recognize" in result["body"]

    def test_no_prior_state(self):
        payload = load_fixture("owner-reveal.json")

        result = handle_issue_comment(
            payload, prior_comment_body=None, secret=TEST_SECRET
        )

        assert result["action"] == "no_state"
        assert result["state"] is None

    def test_tampered_state_rejected(self):
        prior_body = self._create_room()
        # Tamper with the state token in the body
        tampered = prior_body.replace("MINESWEEPER_STATE_V1: ", "MINESWEEPER_STATE_V1: AAAA")

        payload = load_fixture("owner-reveal.json")
        result = handle_issue_comment(
            payload, prior_comment_body=tampered, secret=TEST_SECRET
        )

        assert result["action"] == "no_state"

    def test_state_chain_integrity(self):
        """Verify that sequential moves chain state correctly."""
        prior_body = self._create_room()

        # Move 1: reveal B3
        payload1 = load_fixture("owner-reveal.json")
        r1 = handle_issue_comment(
            payload1, prior_comment_body=prior_body, secret=TEST_SECRET
        )
        assert r1["state"]["seq"] == 1

        # Move 2: flag H7 — uses the body from move 1
        payload2 = load_fixture("owner-flag.json")
        r2 = handle_issue_comment(
            payload2, prior_comment_body=r1["body"], secret=TEST_SECRET
        )
        assert r2["state"]["seq"] == 2
        assert 100 in r2["state"]["processed_comment_ids"]
        assert 101 in r2["state"]["processed_comment_ids"]


class TestGameTermination:
    """Tests for win, loss, and give-up paths."""

    def _create_room(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        return result["body"]

    def _play_until_loss(self):
        """Play moves until we hit a mine, returning the result."""
        from minesweeper.engine import Board

        # Find a mine cell for this seed
        board = Board(9, 9, 10, TEST_SEED)
        mine_cells = sorted(board.mine_set)
        mine_r, mine_c = mine_cells[0]

        prior_body = self._create_room()

        # Construct a payload that reveals the mine cell
        from minesweeper.coords import coord_to_label
        label = coord_to_label(mine_r, mine_c)

        payload = load_fixture("owner-reveal.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["body"] = f"/reveal {label}"
        payload["comment"]["id"] = 300

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )
        return result

    def test_loss_reveals_mines(self):
        result = self._play_until_loss()
        assert result["result"] == "loss"
        assert "game:minesweeper:lost" in result["labels_add"]
        assert "game:minesweeper" in result["labels_remove"]
        assert "\U0001f4a5" in result["body"]  # exploded mine symbol

    def test_give_up(self):
        prior_body = self._create_room()

        payload = load_fixture("owner-reveal.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["body"] = "/giveup"
        payload["comment"]["id"] = 400

        result = handle_issue_comment(
            payload, prior_comment_body=prior_body, secret=TEST_SECRET
        )

        assert result["result"] == "ok"
        assert result["state"]["phase"] == "given_up"
        assert "game:minesweeper:archived" in result["labels_add"]
        assert "game:minesweeper" in result["labels_remove"]
        assert "gave up" in result["body"]

    def test_command_after_game_over(self):
        """Commands on a finished game produce a game_over response."""
        loss_result = self._play_until_loss()
        lost_body = loss_result["body"]

        payload = load_fixture("owner-reveal.json")
        payload = dict(payload)
        payload["comment"] = dict(payload["comment"])
        payload["comment"]["id"] = 301

        result = handle_issue_comment(
            payload, prior_comment_body=lost_body, secret=TEST_SECRET
        )

        assert result["action"] == "game_over"

    def test_win_path(self):
        """Simulate revealing all safe cells to win."""
        from minesweeper.engine import Board

        board = Board(9, 9, 10, TEST_SEED)
        mine_set = board.mine_set
        safe_cells = [
            (r, c) for r in range(9) for c in range(9)
            if (r, c) not in mine_set
        ]

        prior_body = self._create_room()
        from minesweeper.coords import coord_to_label

        comment_id = 500
        for r, c in safe_cells:
            label = coord_to_label(r, c)
            payload = load_fixture("owner-reveal.json")
            payload = dict(payload)
            payload["comment"] = dict(payload["comment"])
            payload["comment"]["body"] = f"/reveal {label}"
            payload["comment"]["id"] = comment_id

            result = handle_issue_comment(
                payload, prior_comment_body=prior_body, secret=TEST_SECRET
            )

            if result["result"] == "win":
                assert "game:minesweeper:won" in result["labels_add"]
                assert "game:minesweeper" in result["labels_remove"]
                assert "win" in result["body"].lower()
                return

            # Use updated body for next move
            if result["body"] is not None:
                prior_body = result["body"]
            comment_id += 1

        pytest.fail("Expected to win after revealing all safe cells")


class TestRenderIntegration:
    """Verify render output in orchestration responses."""

    def test_initial_board_has_correct_dimensions(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        body = result["body"]

        table_lines = [line for line in body.splitlines() if line.startswith("|")]
        assert table_lines[0].startswith("|   | A | B | C |")  # column headers
        assert len(table_lines) == 11  # header + divider + 9 rows

    def test_room_header_present(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        assert "### Minesweeper Room #1" in result["body"]
        assert "In Progress" in result["body"]


class TestRoomService:
    """Direct tests for room_service functions."""

    def test_validate_owner_match(self):
        from minesweeper.room_service import validate_owner

        payload = {"sender": {"login": "testplayer"}}
        assert validate_owner(payload, "testplayer") is True

    def test_validate_owner_case_insensitive(self):
        from minesweeper.room_service import validate_owner

        payload = {"sender": {"login": "TestPlayer"}}
        assert validate_owner(payload, "testplayer") is True

    def test_validate_owner_mismatch(self):
        from minesweeper.room_service import validate_owner

        payload = {"sender": {"login": "interloper"}}
        assert validate_owner(payload, "testplayer") is False

    def test_load_state_from_comment(self):
        from minesweeper.room_service import load_state_from_comment
        from minesweeper.state import encode_state, make_initial_state

        state = make_initial_state(
            room_key="test#1@player",
            issue_number=1,
            owner="player",
            rows=9, cols=9, mines=10, seed=42,
        )
        token = encode_state(state, TEST_SECRET)
        body = f"Some text\n\n{token}\n\nMore text"

        loaded = load_state_from_comment(body, TEST_SECRET)
        assert loaded is not None
        assert loaded["owner"] == "player"
        assert loaded["seed"] == 42

    def test_load_state_returns_none_for_missing(self):
        from minesweeper.room_service import load_state_from_comment

        assert load_state_from_comment("no token here", TEST_SECRET) is None


class TestHandleClickDispatch:
    """Tests for repository_dispatch click orchestration."""

    def _create_room(self):
        payload = load_fixture("issue-open.json")
        result = handle_issue_opened(payload, secret=TEST_SECRET, seed=TEST_SEED)
        return result["body"]

    def _dispatch_payload(self, token: str, *, issue_number: int = 1, actor: str = "testplayer"):
        return {
            "repository": {"full_name": "testowner/github-issue-minesweeper"},
            "client_payload": {
                "issue_number": issue_number,
                "click_token": token,
                "actor": actor,
                "request_id": "req-1",
            },
        }

    def test_valid_click_applies_move(self):
        prior_body = self._create_room()
        prior_token = extract_state_token(prior_body)
        assert prior_token is not None
        state = decode_state(prior_token, TEST_SECRET)
        assert state is not None

        token = encode_click_token(
            room_key=state["room_key"],
            issue_number=1,
            owner="testplayer",
            action="reveal",
            coordinate="B3",
            seq=state["seq"],
            expires_at=int(time.time()) + 300,
            secret=TEST_SECRET,
        )
        payload = self._dispatch_payload(token)
        result = handle_click_dispatch(
            payload,
            prior_comment_body=prior_body,
            secret=TEST_SECRET,
        )

        assert result["action"] == "move"
        assert result["body"] is not None
        assert result["state"]["seq"] == 1

    def test_stale_seq_rejected(self):
        prior_body = self._create_room()
        prior_token = extract_state_token(prior_body)
        assert prior_token is not None
        state = decode_state(prior_token, TEST_SECRET)
        assert state is not None

        token = encode_click_token(
            room_key=state["room_key"],
            issue_number=1,
            owner="testplayer",
            action="reveal",
            coordinate="B3",
            seq=state["seq"],
            expires_at=int(time.time()) + 300,
            secret=TEST_SECRET,
        )
        payload = self._dispatch_payload(token)
        first = handle_click_dispatch(
            payload,
            prior_comment_body=prior_body,
            secret=TEST_SECRET,
        )
        assert first["action"] == "move"

        second = handle_click_dispatch(
            payload,
            prior_comment_body=first["body"],
            secret=TEST_SECRET,
        )
        assert second["action"] == "stale_click"
        assert second["body"] is None

    def test_expired_click_rejected(self):
        prior_body = self._create_room()
        prior_token = extract_state_token(prior_body)
        assert prior_token is not None
        state = decode_state(prior_token, TEST_SECRET)
        assert state is not None
        token = encode_click_token(
            room_key=state["room_key"],
            issue_number=1,
            owner="testplayer",
            action="reveal",
            coordinate="A1",
            seq=state["seq"],
            expires_at=int(time.time()) - 5,
            secret=TEST_SECRET,
        )
        payload = self._dispatch_payload(token)
        result = handle_click_dispatch(
            payload,
            prior_comment_body=prior_body,
            secret=TEST_SECRET,
        )
        assert result["action"] == "stale_click"
        assert result["body"] is None

    def test_actor_mismatch_rejected(self):
        prior_body = self._create_room()
        prior_token = extract_state_token(prior_body)
        assert prior_token is not None
        state = decode_state(prior_token, TEST_SECRET)
        assert state is not None
        token = encode_click_token(
            room_key=state["room_key"],
            issue_number=1,
            owner="testplayer",
            action="reveal",
            coordinate="A1",
            seq=state["seq"],
            expires_at=int(time.time()) + 300,
            secret=TEST_SECRET,
        )
        payload = self._dispatch_payload(token, actor="interloper")
        result = handle_click_dispatch(
            payload,
            prior_comment_body=prior_body,
            secret=TEST_SECRET,
        )
        assert result["action"] == "non_owner"
        assert "interloper" in (result["body"] or "")
