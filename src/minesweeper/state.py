"""Signed state token encoding, decoding, and verification.

Implements the hidden HTML-comment state contract:
<!-- MINESWEEPER_STATE_V1: <payload>.<sig> -->

Uses HMAC-SHA256 for integrity. The payload is base64url-encoded JSON.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re

_MARKER = "MINESWEEPER_STATE_V1"
_TOKEN_RE = re.compile(
    r"<!--\s*" + re.escape(_MARKER) + r":\s*(\S+)\s*-->"
)

SCHEMA_VERSION = "v1"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _sign(payload_b64: str, secret: str) -> str:
    sig = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(sig)


def encode_state(payload: dict, secret: str) -> str:
    """Encode a state payload into a signed token string.

    Returns the full HTML comment marker ready to embed in a bot comment.
    """
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    payload_b64 = _b64url_encode(payload_json.encode("utf-8"))
    sig = _sign(payload_b64, secret)
    token = f"{payload_b64}.{sig}"
    return f"<!-- {_MARKER}: {token} -->"


def decode_state(token: str, secret: str) -> dict | None:
    """Decode and verify a signed token, returning the payload or None.

    The token is the raw 'payload_b64.sig' string (without HTML comment
    wrapper). Returns None if the signature is invalid or data is malformed.
    """
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    payload_b64, sig = parts
    expected_sig = _sign(payload_b64, secret)
    if not hmac.compare_digest(sig, expected_sig):
        return None
    try:
        payload_json = _b64url_decode(payload_b64).decode("utf-8")
        return json.loads(payload_json)
    except (ValueError, json.JSONDecodeError):
        return None


def extract_state_token(comment_body: str) -> str | None:
    """Extract the raw token from a bot comment's HTML marker.

    Returns the 'payload_b64.sig' string, or None if not found.
    """
    m = _TOKEN_RE.search(comment_body)
    if not m:
        return None
    return m.group(1)


def make_initial_state(
    room_key: str,
    issue_number: int,
    owner: str,
    rows: int,
    cols: int,
    mines: int,
    seed: int,
) -> dict:
    """Create the initial state payload for a new room."""
    return {
        "schema": SCHEMA_VERSION,
        "version": 1,
        "room_key": room_key,
        "issue_number": issue_number,
        "owner": owner,
        "rows": rows,
        "cols": cols,
        "mines": mines,
        "seed": seed,
        "revealed": [],
        "flagged": [],
        "phase": "playing",
        "seq": 0,
        "processed_comment_ids": [],
    }


def derive_room_key(repo: str, issue_number: int, owner: str) -> str:
    """Derive a deterministic room key from repo, issue, and owner."""
    return f"{repo}#{issue_number}@{owner}"
