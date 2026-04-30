import { describe, expect, it } from "vitest";
import {
  buildLeaderboardGameRecord,
  isLeaderboardRecordablePhase,
} from "./leaderboard-record";

describe("leaderboard game records", () => {
  it("records won, lost, and given_up terminal phases", () => {
    expect(isLeaderboardRecordablePhase("won")).toBe(true);
    expect(isLeaderboardRecordablePhase("lost")).toBe(true);
    expect(isLeaderboardRecordablePhase("given_up")).toBe(true);
  });

  it("does not record playing or expired phases", () => {
    expect(isLeaderboardRecordablePhase("playing")).toBe(false);
    expect(isLeaderboardRecordablePhase("expired")).toBe(false);
  });

  it("builds the main-branch game result payload", () => {
    expect(
      buildLeaderboardGameRecord(
        {
          issue_number: 42,
          owner: "octocat",
          rows: 9,
          cols: 9,
          mines: 10,
          phase: "lost",
          seq: 7,
        },
        "2026-04-30T17:00:00.000Z",
      ),
    ).toEqual({
      schema: "minesweeper-game-result-v1",
      issue: 42,
      player: "octocat",
      result: "lost",
      moves: 7,
      rows: 9,
      cols: 9,
      mines: 10,
      completed_at: "2026-04-30T17:00:00.000Z",
    });
  });
});

