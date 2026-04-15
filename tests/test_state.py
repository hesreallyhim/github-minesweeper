"""Tests for the signed state chain."""

from __future__ import annotations

from minesweeper.state import (
    CLICK_SCHEMA,
    SCHEMA_VERSION,
    decode_click_token,
    decode_state,
    derive_room_key,
    encode_click_token,
    encode_state,
    extract_state_token,
    make_initial_state,
)

SECRET = "test-secret-key"


class TestEncodeDecodeRoundtrip:
    def test_roundtrip(self):
        payload = {"foo": "bar", "num": 42}
        marker = encode_state(payload, SECRET)
        token = extract_state_token(marker)
        assert token is not None
        decoded = decode_state(token, SECRET)
        assert decoded == payload

    def test_marker_format(self):
        marker = encode_state({"x": 1}, SECRET)
        assert marker.startswith("<!-- MINESWEEPER_STATE_V1: ")
        assert marker.endswith(" -->")

    def test_complex_payload(self):
        payload = make_initial_state(
            room_key="repo#1@user",
            issue_number=1,
            owner="user",
            rows=9, cols=9, mines=10, seed=42,
        )
        marker = encode_state(payload, SECRET)
        token = extract_state_token(marker)
        decoded = decode_state(token, SECRET)
        assert decoded == payload

    def test_sorted_keys_deterministic(self):
        p1 = {"b": 2, "a": 1}
        p2 = {"a": 1, "b": 2}
        m1 = encode_state(p1, SECRET)
        m2 = encode_state(p2, SECRET)
        assert m1 == m2


class TestTamperRejection:
    def test_wrong_secret(self):
        payload = {"x": 1}
        marker = encode_state(payload, SECRET)
        token = extract_state_token(marker)
        assert decode_state(token, "wrong-secret") is None

    def test_modified_payload(self):
        payload = {"x": 1}
        marker = encode_state(payload, SECRET)
        token = extract_state_token(marker)
        # Tamper with the payload portion
        parts = token.split(".")
        tampered = parts[0][:-1] + "X" + "." + parts[1]
        assert decode_state(tampered, SECRET) is None

    def test_missing_sig(self):
        assert decode_state("payload_only_no_dot", SECRET) is None

    def test_empty_token(self):
        assert decode_state("", SECRET) is None

    def test_garbage_token(self):
        assert decode_state("not.valid.at.all", SECRET) is None


class TestExtractStateToken:
    def test_extracts_from_comment(self):
        body = (
            "## Room Status\n\nYour move was accepted.\n\n"
            "```\nboard here\n```\n\n"
            "<!-- MINESWEEPER_STATE_V1: abc123.sig456 -->"
        )
        token = extract_state_token(body)
        assert token == "abc123.sig456"

    def test_no_marker(self):
        assert extract_state_token("just a comment, no state") is None

    def test_empty_body(self):
        assert extract_state_token("") is None

    def test_whitespace_variants(self):
        body = "<!--  MINESWEEPER_STATE_V1:  tok.sig  -->"
        token = extract_state_token(body)
        assert token == "tok.sig"


class TestInitialState:
    def test_fields(self):
        state = make_initial_state(
            room_key="repo#1@user",
            issue_number=1,
            owner="user",
            rows=9, cols=9, mines=10, seed=42,
        )
        assert state["schema"] == SCHEMA_VERSION
        assert state["version"] == 1
        assert state["room_key"] == "repo#1@user"
        assert state["issue_number"] == 1
        assert state["owner"] == "user"
        assert state["rows"] == 9
        assert state["cols"] == 9
        assert state["mines"] == 10
        assert state["seed"] == 42
        assert state["revealed"] == []
        assert state["flagged"] == []
        assert state["phase"] == "playing"
        assert state["seq"] == 0
        assert state["processed_comment_ids"] == []


class TestDeriveRoomKey:
    def test_format(self):
        key = derive_room_key("owner/repo", 42, "player")
        assert key == "owner/repo#42@player"

    def test_deterministic(self):
        k1 = derive_room_key("r", 1, "u")
        k2 = derive_room_key("r", 1, "u")
        assert k1 == k2

    def test_different_inputs_differ(self):
        k1 = derive_room_key("r", 1, "u")
        k2 = derive_room_key("r", 2, "u")
        assert k1 != k2


class TestClickToken:
    def test_roundtrip(self):
        token = encode_click_token(
            room_key="owner/repo#1@player",
            issue_number=1,
            owner="player",
            action="reveal",
            coordinate="B3",
            seq=7,
            expires_at=1_900_000_000,
            secret=SECRET,
        )
        payload = decode_click_token(token, SECRET)
        assert payload is not None
        assert payload["schema"] == CLICK_SCHEMA
        assert payload["action"] == "reveal"
        assert payload["coordinate"] == "B3"
        assert payload["seq"] == 7

    def test_wrong_secret_rejected(self):
        token = encode_click_token(
            room_key="r#1@u",
            issue_number=1,
            owner="u",
            action="reveal",
            coordinate="A1",
            seq=0,
            expires_at=1_900_000_000,
            secret=SECRET,
        )
        assert decode_click_token(token, "wrong-secret") is None

    def test_tampered_rejected(self):
        token = encode_click_token(
            room_key="r#1@u",
            issue_number=1,
            owner="u",
            action="reveal",
            coordinate="A1",
            seq=0,
            expires_at=1_900_000_000,
            secret=SECRET,
        )
        parts = token.split(".")
        tampered = parts[0][:-1] + "X" + "." + parts[1]
        assert decode_click_token(tampered, SECRET) is None

    def test_schema_mismatch_rejected(self):
        marker = encode_state({"schema": "v1"}, SECRET)
        raw = extract_state_token(marker)
        assert raw is not None
        assert decode_click_token(raw, SECRET) is None
