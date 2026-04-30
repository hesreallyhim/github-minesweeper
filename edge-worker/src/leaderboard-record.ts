export const LEADERBOARD_GAME_RESULT_SCHEMA = "minesweeper-game-result-v1";

export type LeaderboardRecordablePhase = "won" | "lost" | "given_up";

export type LeaderboardGameState = {
  issue_number: number;
  owner: string;
  rows: number;
  cols: number;
  mines: number;
  phase: string;
  seq: number;
};

export type LeaderboardGameRecord = {
  schema: typeof LEADERBOARD_GAME_RESULT_SCHEMA;
  issue: number;
  player: string;
  result: LeaderboardRecordablePhase;
  moves: number;
  rows: number;
  cols: number;
  mines: number;
  completed_at: string;
};

const RECORDABLE_PHASES = new Set<string>(["won", "lost", "given_up"]);

function safeInt(value: number, fallback = 0): number {
  return Number.isFinite(value) ? Math.trunc(value) : fallback;
}

export function isLeaderboardRecordablePhase(phase: string): phase is LeaderboardRecordablePhase {
  return RECORDABLE_PHASES.has(phase);
}

export function buildLeaderboardGameRecord(
  state: LeaderboardGameState,
  completedAt: string,
): LeaderboardGameRecord | null {
  if (!isLeaderboardRecordablePhase(state.phase)) return null;
  return {
    schema: LEADERBOARD_GAME_RESULT_SCHEMA,
    issue: safeInt(state.issue_number, 0),
    player: state.owner,
    result: state.phase,
    moves: Math.max(safeInt(state.seq, 0), 0),
    rows: Math.max(safeInt(state.rows, 0), 0),
    cols: Math.max(safeInt(state.cols, 0), 0),
    mines: Math.max(safeInt(state.mines, 0), 0),
    completed_at: completedAt,
  };
}

