#!/usr/bin/env python3
"""Replay GitHub event fixtures through the local game engine.

Supports two modes:

1. Single fixture: replay one event and print the bot response.
2. Sequence replay: replay multiple fixtures in order, chaining state
   between them to simulate a full game session.

Usage:
    # Single issue-open event
    python scripts/replay_fixture.py tests/fixtures/github/issue-open.json

    # Chain multiple events (open → reveal → flag → ...)
    python scripts/replay_fixture.py \\
        tests/fixtures/github/issue-open.json \\
        tests/fixtures/github/owner-reveal.json \\
        tests/fixtures/github/owner-flag.json

    # Replay all fixtures in a directory (sorted by name)
    python scripts/replay_fixture.py tests/fixtures/github/

Environment:
    MINESWEEPER_SECRET  - HMAC signing secret (default: dev-secret-do-not-use-in-prod)
    MINESWEEPER_SEED    - Deterministic seed for board generation (default: 42)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure stdout can handle emoji/unicode
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

# Ensure src/ is on the import path
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from minesweeper.github_events import handle_issue_comment, handle_issue_opened


def _load_fixture(path: str) -> dict:
    with open(path) as fh:
        return json.load(fh)


def _resolve_fixtures(args: list[str]) -> list[str]:
    """Resolve CLI arguments to a list of fixture file paths.

    If an argument is a directory, expand to all .json files sorted by name.
    """
    paths: list[str] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            paths.extend(sorted(str(f) for f in p.glob("*.json")))
        elif p.is_file():
            paths.append(str(p))
        else:
            print(f"Warning: skipping {arg} (not a file or directory)",
                  file=sys.stderr)
    return paths


def _separator(label: str) -> str:
    return f"\n{'=' * 60}\n  {label}\n{'=' * 60}\n"


def replay(fixture_paths: list[str], *, verbose: bool = True) -> list[dict]:
    """Replay a sequence of fixtures, chaining state between them.

    Returns the list of result dicts from each event.
    """
    secret = os.environ.get("MINESWEEPER_SECRET", "dev-secret-do-not-use-in-prod")
    seed = int(os.environ.get("MINESWEEPER_SEED", "42"))

    last_body: str | None = None
    results: list[dict] = []

    for i, path in enumerate(fixture_paths):
        payload = _load_fixture(path)
        action = payload.get("action", "unknown")
        fixture_name = Path(path).name

        if verbose:
            print(_separator(f"Event {i + 1}: {fixture_name} (action={action})"))

        if action == "opened":
            result = handle_issue_opened(payload, secret=secret, seed=seed)
        elif action == "created":
            result = handle_issue_comment(
                payload, prior_comment_body=last_body, secret=secret
            )
        else:
            if verbose:
                print(f"  Skipping unknown action: {action}")
            continue

        results.append(result)

        # Print response
        body = result.get("body")
        if verbose:
            action_label = result.get("action", "?")
            print(f"  Action: {action_label}")
            if result.get("labels_add"):
                print(f"  Labels +: {result['labels_add']}")
            if result.get("labels_remove"):
                print(f"  Labels -: {result['labels_remove']}")
            print()
            if body:
                print(body)
            else:
                print("  (no response body — duplicate or skipped)")

        # Chain state: save the body for the next event's prior_comment_body
        if body:
            last_body = body

    return results


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: replay_fixture.py <fixture.json|dir> [fixture2.json ...]",
            file=sys.stderr,
        )
        print(
            "\nReplay one or more GitHub event fixtures through the local engine.",
            file=sys.stderr,
        )
        print(
            "Pass a directory to replay all .json files in sorted order.",
            file=sys.stderr,
        )
        sys.exit(1)

    fixture_paths = _resolve_fixtures(sys.argv[1:])
    if not fixture_paths:
        print("No fixture files found.", file=sys.stderr)
        sys.exit(1)

    results = replay(fixture_paths)

    # Summary
    print(_separator("Summary"))
    for i, r in enumerate(results):
        action = r.get("action", "?")
        result = r.get("result", "—")
        has_body = "yes" if r.get("body") else "no"
        print(f"  Event {i + 1}: action={action}, result={result}, body={has_body}")

    # Check for failures
    failures = [r for r in results if r.get("action") == "no_state"]
    if failures:
        print(f"\n  ⚠ {len(failures)} event(s) had no valid state")
        sys.exit(1)

    print(f"\n  ✓ {len(results)} event(s) replayed successfully")


if __name__ == "__main__":
    main()
