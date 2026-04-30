import { decideAbuseGuard } from "./abuse-guard";
import type { AbuseGuard } from "./abuse-guard";
import { guardedBlockGitHubUser, guardedGitHubRequest } from "./github-api-guard";
import type { GitHubApiGuard } from "./github-api-guard";
import { buildLeaderboardGameRecord } from "./leaderboard-record";

export { AbuseGuard } from "./abuse-guard";
export { GitHubApiGuard } from "./github-api-guard";

interface Env {
  GITHUB_WEBHOOK_SECRET: string;
  GITHUB_APP_ID: string;
  GITHUB_APP_PRIVATE_KEY: string;
  GITHUB_MODERATION_TOKEN?: string;
  MINESWEEPER_SECRET: string;
  GAME_ROWS: string;
  GAME_COLS: string;
  GAME_MINES: string;
  ABUSE_GUARD: DurableObjectNamespace<AbuseGuard>;
  GITHUB_API_GUARD: DurableObjectNamespace<GitHubApiGuard>;
}

type CellState = "hidden" | "revealed" | "flagged";
type Phase = "playing" | "won" | "lost" | "given_up" | "expired";
type MoveResult = "ok" | "win" | "loss" | "no_op" | "invalid";
type CommandAction = "reveal" | "flag" | "unflag" | "giveup";
type ParsedCommand = {
  action: CommandAction;
  coordinate: string | null;
};
type ParsedTurn = {
  commands: ParsedCommand[];
};
type GitHubIssueComment = {
  id: number;
  body?: string;
  user?: {
    login?: string;
    bot?: boolean;
  };
};

interface GameStateV1 {
  schema: "v1";
  version: 1;
  runtime: "edge-cfw1";
  room_key: string;
  issue_number: number;
  owner: string;
  rows: number;
  cols: number;
  mines: number;
  seed: number;
  revealed: Array<[number, number]>;
  flagged: Array<[number, number]>;
  phase: Phase;
  seq: number;
  processed_comment_ids: number[];
}

const STATE_MARKER = "MINESWEEPER_STATE_V1";
const COMMAND_REMINDER =
  "**Commands:** `A1 B2` (reveal) · `guess A1 A2` · `flag H7 H8` · `unflag H7` · `giveup`";
const ACTIVE_GAME_LABEL = "game:minesweeper";
const LEADERBOARD_GAME_RECORD_ROOT = ".github/leaderboards/data/games";
const LEADERBOARD_RECORD_BRANCH = "main";
const GAMEPLAY_LIMIT_MS = 30 * 60 * 1000;
const ACTION_ALIASES: Record<string, CommandAction> = {
  reveal: "reveal",
  guess: "reveal",
  flag: "flag",
  unflag: "unflag",
  giveup: "giveup",
};
const COORD_TOKEN_RE = /^`?([A-Za-z]\d+|\d+[A-Za-z])`?$/;
const COL_ROW_RE = /^([A-Za-z])(\d+)$/;
const ROW_COL_RE = /^(\d+)([A-Za-z])$/;
const STATE_TOKEN_RE = new RegExp(
  `<!--\\s*${STATE_MARKER}:\\s*(\\S+)\\s*-->`,
);

const TEXT_ENCODER = new TextEncoder();
const TEXT_DECODER = new TextDecoder();

const CONTRIBUTION_COLORS = ["#0e4429", "#006d32", "#26a641", "#39d353"];
const NUMBER_COLORS: Record<string, string> = {
  "1": "#58a6ff",
  "2": "#7ee787",
  "3": "#ff7b72",
  "4": "#d2a8ff",
  "5": "#ffa657",
  "6": "#79c0ff",
  "7": "#f0f6fc",
  "8": "#8b949e",
};

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function parseIntOr(raw: string | undefined, fallback: number): number {
  if (!raw) return fallback;
  const v = Number.parseInt(raw, 10);
  if (Number.isNaN(v)) return fallback;
  return v;
}

function parseTimestampMs(raw: string | undefined): number | null {
  if (!raw) return null;
  const value = Date.parse(raw);
  return Number.isNaN(value) ? null : value;
}

function isPastGameplayLimit(issueCreatedAt: string | undefined, checkedAt: string | undefined): boolean {
  const issueCreatedMs = parseTimestampMs(issueCreatedAt);
  const checkedMs = parseTimestampMs(checkedAt);
  if (issueCreatedMs === null || checkedMs === null) return false;
  return checkedMs - issueCreatedMs >= GAMEPLAY_LIMIT_MS;
}

function labelsFromIssue(payload: Record<string, unknown>): string[] {
  const issue = asObject(payload.issue);
  const labels = Array.isArray(issue?.labels) ? issue.labels : [];
  return labels
    .map((label) => {
      const labelObj = asObject(label);
      return typeof labelObj?.name === "string" ? labelObj.name : "";
    })
    .filter((x) => x.length > 0);
}

function asObject(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function getInstallationId(payload: Record<string, unknown>): number {
  const installation = asObject(payload.installation);
  return Number(installation?.id ?? 0);
}

function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a[i] ^ b[i];
  }
  return diff === 0;
}

function bytesToHex(data: Uint8Array): string {
  return Array.from(data)
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}

function b64urlEncode(data: Uint8Array): string {
  let binary = "";
  for (const byte of data) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function b64urlDecode(raw: string): Uint8Array {
  const normalized = raw.replace(/-/g, "+").replace(/_/g, "/");
  const padding = normalized.length % 4 === 0 ? "" : "=".repeat(4 - (normalized.length % 4));
  const binary = atob(`${normalized}${padding}`);
  const out = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) out[i] = binary.charCodeAt(i);
  return out;
}

function stableJsonStringify(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableJsonStringify(item)).join(",")}]`;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj).sort();
  const parts = keys.map((k) => `${JSON.stringify(k)}:${stableJsonStringify(obj[k])}`);
  return `{${parts.join(",")}}`;
}

async function hmacSha256(secret: string, message: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    TEXT_ENCODER.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, TEXT_ENCODER.encode(message));
  return new Uint8Array(sig);
}

async function verifyWebhookSignature(
  body: string,
  signatureHeader: string | null,
  secret: string,
): Promise<boolean> {
  if (!signatureHeader || !signatureHeader.startsWith("sha256=")) {
    return false;
  }
  const actualHex = signatureHeader.slice("sha256=".length);
  if (!actualHex) return false;
  const expected = await hmacSha256(secret, body);
  const actualBytes = TEXT_ENCODER.encode(actualHex.toLowerCase());
  const expectedBytes = TEXT_ENCODER.encode(bytesToHex(expected));
  return timingSafeEqual(actualBytes, expectedBytes);
}

async function encodeSignedToken(payload: Record<string, unknown>, secret: string): Promise<string> {
  const payloadJson = stableJsonStringify(payload);
  const payloadB64 = b64urlEncode(TEXT_ENCODER.encode(payloadJson));
  const sig = await hmacSha256(secret, payloadB64);
  return `${payloadB64}.${b64urlEncode(sig)}`;
}

async function decodeSignedToken(
  token: string,
  secret: string,
): Promise<Record<string, unknown> | null> {
  const dot = token.indexOf(".");
  if (dot < 0) return null;
  const payloadB64 = token.slice(0, dot);
  const sigB64 = token.slice(dot + 1);
  const expected = await hmacSha256(secret, payloadB64);
  const actual = b64urlDecode(sigB64);
  if (!timingSafeEqual(actual, expected)) return null;
  try {
    const payloadJson = TEXT_DECODER.decode(b64urlDecode(payloadB64));
    const parsed = JSON.parse(payloadJson);
    if (!asObject(parsed)) return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

function extractStateToken(commentBody: string): string | null {
  const match = STATE_TOKEN_RE.exec(commentBody);
  return match?.[1] ?? null;
}

function coordToLabel(row: number, col: number): string {
  return `${String.fromCharCode("A".charCodeAt(0) + col)}${row + 1}`;
}

function parseCoord(raw: string, rows: number, cols: number): [number, number] | null {
  const trimmed = raw.trim();
  const colRow = COL_ROW_RE.exec(trimmed);
  const rowCol = ROW_COL_RE.exec(trimmed);
  let row = -1;
  let col = -1;
  if (colRow) {
    col = colRow[1].toUpperCase().charCodeAt(0) - "A".charCodeAt(0);
    row = Number.parseInt(colRow[2], 10) - 1;
  } else if (rowCol) {
    row = Number.parseInt(rowCol[1], 10) - 1;
    col = rowCol[2].toUpperCase().charCodeAt(0) - "A".charCodeAt(0);
  } else {
    return null;
  }
  if (row < 0 || row >= rows || col < 0 || col >= cols) return null;
  return [row, col];
}

function parseActionToken(token: string): CommandAction | null {
  let raw = token.trim().toLowerCase();
  if (raw.startsWith("/")) raw = raw.slice(1);
  if (!raw || !/^[a-z]+$/.test(raw)) return null;
  return ACTION_ALIASES[raw] ?? null;
}

function parseImplicitCoordinate(token: string): string | null {
  const match = COORD_TOKEN_RE.exec(token.trim());
  return match?.[1] ?? null;
}

function parseTurn(text: string): ParsedTurn | null {
  const commands: ParsedCommand[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const tokens = line.split(/\s+/).filter((token) => token.length > 0);
    if (tokens.length === 0) continue;

    const action = parseActionToken(tokens[0]);
    if (action !== null) {
      if (action === "giveup") {
        if (tokens.length > 1) return null;
        commands.push({ action: "giveup", coordinate: null });
        continue;
      }

      if (tokens.length === 1) {
        commands.push({ action, coordinate: null });
        continue;
      }

      for (const token of tokens.slice(1)) {
        if (parseActionToken(token) !== null) return null;
        const coordinate = parseImplicitCoordinate(token);
        if (coordinate === null) return null;
        commands.push({ action, coordinate });
      }
      continue;
    }

    for (const token of tokens) {
      const coordinate = parseImplicitCoordinate(token);
      if (coordinate === null) return null;
      commands.push({ action: "reveal", coordinate });
    }
  }

  if (commands.length === 0) return null;
  return { commands };
}

function seedHash(input: string): number {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t ^= t + Math.imul(t ^ (t >>> 7), 61 | t);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

class Board {
  rows: number;
  cols: number;
  numMines: number;
  seed: number;
  phase: Phase;
  mineGrid: boolean[][];
  adjCounts: number[][];
  cellStates: CellState[][];

  constructor(rows: number, cols: number, mines: number, seed: number) {
    if (mines >= rows * cols) throw new Error("Too many mines");
    if (rows <= 0 || cols <= 0 || mines <= 0) throw new Error("Invalid board shape");
    this.rows = rows;
    this.cols = cols;
    this.numMines = mines;
    this.seed = seed >>> 0;
    this.phase = "playing";

    const allCells: Array<[number, number]> = [];
    for (let r = 0; r < rows; r += 1) {
      for (let c = 0; c < cols; c += 1) allCells.push([r, c]);
    }
    const rng = mulberry32(this.seed);
    for (let i = allCells.length - 1; i > 0; i -= 1) {
      const j = Math.floor(rng() * (i + 1));
      [allCells[i], allCells[j]] = [allCells[j], allCells[i]];
    }
    const mineCells = allCells.slice(0, mines);

    this.mineGrid = Array.from({ length: rows }, () => Array<boolean>(cols).fill(false));
    for (const [r, c] of mineCells) this.mineGrid[r][c] = true;

    this.adjCounts = Array.from({ length: rows }, () => Array<number>(cols).fill(0));
    for (let r = 0; r < rows; r += 1) {
      for (let c = 0; c < cols; c += 1) {
        if (this.mineGrid[r][c]) {
          this.adjCounts[r][c] = -1;
          continue;
        }
        let n = 0;
        for (const [nr, nc] of this.neighbors(r, c)) {
          if (this.mineGrid[nr][nc]) n += 1;
        }
        this.adjCounts[r][c] = n;
      }
    }
    this.cellStates = Array.from({ length: rows }, () => Array<CellState>(cols).fill("hidden"));
  }

  static fromState(state: GameStateV1): Board {
    const board = new Board(state.rows, state.cols, state.mines, state.seed);
    board.phase = state.phase;
    for (const [r, c] of state.revealed) board.cellStates[r][c] = "revealed";
    for (const [r, c] of state.flagged) board.cellStates[r][c] = "flagged";
    return board;
  }

  toStateFields(): Pick<GameStateV1, "revealed" | "flagged" | "phase"> {
    const revealed: Array<[number, number]> = [];
    const flagged: Array<[number, number]> = [];
    for (let r = 0; r < this.rows; r += 1) {
      for (let c = 0; c < this.cols; c += 1) {
        if (this.cellStates[r][c] === "revealed") revealed.push([r, c]);
        if (this.cellStates[r][c] === "flagged") flagged.push([r, c]);
      }
    }
    revealed.sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
    flagged.sort((a, b) => (a[0] - b[0]) || (a[1] - b[1]));
    return { revealed, flagged, phase: this.phase };
  }

  safeCount(): number {
    return this.rows * this.cols - this.numMines;
  }

  revealedCount(): number {
    let total = 0;
    for (let r = 0; r < this.rows; r += 1) {
      for (let c = 0; c < this.cols; c += 1) if (this.cellStates[r][c] === "revealed") total += 1;
    }
    return total;
  }

  flaggedCount(): number {
    let total = 0;
    for (let r = 0; r < this.rows; r += 1) {
      for (let c = 0; c < this.cols; c += 1) if (this.cellStates[r][c] === "flagged") total += 1;
    }
    return total;
  }

  private inBounds(row: number, col: number): boolean {
    return row >= 0 && row < this.rows && col >= 0 && col < this.cols;
  }

  private *neighbors(row: number, col: number): Generator<[number, number]> {
    for (let dr = -1; dr <= 1; dr += 1) {
      for (let dc = -1; dc <= 1; dc += 1) {
        if (dr === 0 && dc === 0) continue;
        const nr = row + dr;
        const nc = col + dc;
        if (this.inBounds(nr, nc)) yield [nr, nc];
      }
    }
  }

  private checkWin(): boolean {
    return this.revealedCount() === this.safeCount();
  }

  private floodFill(row: number, col: number): void {
    const stack: Array<[number, number]> = [[row, col]];
    while (stack.length > 0) {
      const next = stack.pop();
      if (!next) break;
      const [r, c] = next;
      if (this.cellStates[r][c] === "revealed") continue;
      if (this.mineGrid[r][c]) continue;
      this.cellStates[r][c] = "revealed";
      if (this.adjCounts[r][c] === 0) {
        for (const [nr, nc] of this.neighbors(r, c)) {
          if (this.cellStates[nr][nc] === "hidden") stack.push([nr, nc]);
        }
      }
    }
  }

  reveal(row: number, col: number): MoveResult {
    if (this.phase !== "playing") return "invalid";
    if (!this.inBounds(row, col)) return "invalid";
    if (this.cellStates[row][col] === "revealed") return "no_op";
    if (this.cellStates[row][col] === "flagged") this.cellStates[row][col] = "hidden";
    if (this.mineGrid[row][col]) {
      this.cellStates[row][col] = "revealed";
      this.phase = "lost";
      return "loss";
    }
    this.floodFill(row, col);
    if (this.checkWin()) {
      this.phase = "won";
      return "win";
    }
    return "ok";
  }

  flag(row: number, col: number): MoveResult {
    if (this.phase !== "playing") return "invalid";
    if (!this.inBounds(row, col)) return "invalid";
    if (this.cellStates[row][col] !== "hidden") return "no_op";
    this.cellStates[row][col] = "flagged";
    return "ok";
  }

  unflag(row: number, col: number): MoveResult {
    if (this.phase !== "playing") return "invalid";
    if (!this.inBounds(row, col)) return "invalid";
    if (this.cellStates[row][col] !== "flagged") return "no_op";
    this.cellStates[row][col] = "hidden";
    return "ok";
  }

  chord(row: number, col: number): MoveResult {
    if (this.phase !== "playing") return "invalid";
    if (!this.inBounds(row, col)) return "invalid";
    if (this.cellStates[row][col] !== "revealed") return "no_op";
    const count = this.adjCounts[row][col];
    if (count <= 0) return "no_op";
    let adjFlags = 0;
    const hiddenNeighbors: Array<[number, number]> = [];
    for (const [nr, nc] of this.neighbors(row, col)) {
      if (this.cellStates[nr][nc] === "flagged") adjFlags += 1;
      if (this.cellStates[nr][nc] === "hidden") hiddenNeighbors.push([nr, nc]);
    }
    if (adjFlags !== count || hiddenNeighbors.length === 0) return "no_op";
    for (const [nr, nc] of hiddenNeighbors) {
      if (this.mineGrid[nr][nc]) {
        this.cellStates[nr][nc] = "revealed";
        this.phase = "lost";
        return "loss";
      }
    }
    for (const [nr, nc] of hiddenNeighbors) this.floodFill(nr, nc);
    if (this.checkWin()) {
      this.phase = "won";
      return "win";
    }
    return "ok";
  }

  giveUp(): MoveResult {
    if (this.phase !== "playing") return "invalid";
    this.phase = "given_up";
    return "ok";
  }

  getCellDisplay(row: number, col: number, revealAll: boolean): string {
    const state = this.cellStates[row][col];
    const isMine = this.mineGrid[row][col];
    if (state === "flagged") return "flag";
    if (state === "hidden") {
      if (revealAll && isMine) return "mine";
      return "hidden";
    }
    if (isMine) return "exploded";
    const count = this.adjCounts[row][col];
    if (count === 0) return "empty";
    return String(count);
  }
}

function boardImageUrl(origin: string, stateToken: string): string {
  const url = new URL("/board.svg", origin);
  url.searchParams.set("state", stateToken);
  return url.toString();
}

function renderBoardPictureHtml(origin: string, stateToken: string): string {
  return `<picture><img src="${boardImageUrl(origin, stateToken)}" alt="Minesweeper board" /></picture>`;
}

function renderBoardSvg(board: Board, revealAll: boolean): string {
  const cell = 50;
  const pad = 24;
  const tileInset = 2;
  const tileSize = cell - (tileInset * 2);
  const cols = board.cols;
  const rows = board.rows;
  const width = (pad * 2) + ((cols + 1) * cell);
  const height = (pad * 2) + ((rows + 1) * cell);

  const parts: string[] = [];
  parts.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}">`,
  );
  parts.push(
    `<defs>
      <filter id="cellShadow" x="-30%" y="-30%" width="160%" height="160%">
        <feDropShadow dx="0" dy="1.5" stdDeviation="1" flood-color="#000" flood-opacity="0.35"/>
      </filter>
      <symbol id="bomb" viewBox="-20 -20 40 40" overflow="visible">
        <g fill="#0d1117">
          <rect x="-1.8" y="-15" width="3.6" height="5" rx="0.5"/>
          <rect x="-1.8" y="10" width="3.6" height="5" rx="0.5"/>
          <rect x="-15" y="-1.8" width="5" height="3.6" rx="0.5"/>
          <rect x="10" y="-1.8" width="5" height="3.6" rx="0.5"/>
          <g transform="rotate(45)">
            <rect x="-1.8" y="-14" width="3.6" height="4.5" rx="0.5"/>
            <rect x="-1.8" y="9.5" width="3.6" height="4.5" rx="0.5"/>
            <rect x="-14" y="-1.8" width="4.5" height="3.6" rx="0.5"/>
            <rect x="9.5" y="-1.8" width="4.5" height="3.6" rx="0.5"/>
          </g>
        </g>
        <circle cx="0" cy="0" r="9.5" fill="#0d1117" stroke="#484f58" stroke-width="0.6"/>
        <circle cx="-3" cy="-3" r="2.3" fill="#484f58"/>
        <circle cx="-3.5" cy="-3.5" r="1" fill="#8b949e"/>
        <path d="M 6.5,-6.5 Q 10,-10 12,-13" stroke="#8b949e" stroke-width="1.6" fill="none" stroke-linecap="round"/>
        <circle cx="13" cy="-14" r="3" fill="#f85149"/>
        <circle cx="13" cy="-14" r="1.5" fill="#ffa657"/>
        <circle cx="13" cy="-14" r="0.6" fill="#f0f6fc"/>
      </symbol>
      <symbol id="flag" viewBox="-15 -18 30 36" overflow="visible">
        <rect x="-0.9" y="-14" width="1.8" height="28" fill="#c9d1d9"/>
        <rect x="-6" y="11" width="13" height="2" rx="0.5" fill="#8b949e"/>
        <rect x="-7" y="13" width="15" height="2.5" rx="0.5" fill="#8b949e"/>
        <path d="M 1,-14 L 12,-7 L 1,0 Z" fill="#f85149"/>
        <path d="M 1,-14 L 12,-7 L 1,-12 Z" fill="#ff7b72" opacity="0.6"/>
      </symbol>
    </defs>`,
  );

  parts.push(`<rect width="${width}" height="${height}" fill="#0d1117"/>`);
  const boardX = pad;
  const boardY = pad;
  const boardWidth = (cols + 1) * cell;
  const boardHeight = (rows + 1) * cell;
  const playableX = boardX + cell;
  const playableY = boardY + cell;
  const playableWidth = cols * cell;
  const playableHeight = rows * cell;
  parts.push(`<rect x="${boardX}" y="${boardY}" width="${boardWidth}" height="${boardHeight}" fill="#010409" stroke="#30363d" stroke-width="1.5"/>`);

  for (let r = 0; r <= rows; r += 1) {
    for (let c = 0; c <= cols; c += 1) {
      const x = boardX + (c * cell);
      const y = boardY + (r * cell);
      parts.push(`<rect x="${x}" y="${y}" width="${cell}" height="${cell}" fill="${r === 0 || c === 0 ? "#010409" : "#0d1117"}" stroke="#30363d" stroke-width="1"/>`);
    }
  }

  for (let c = 0; c < cols; c += 1) {
    const x = boardX + ((c + 1) * cell) + (cell / 2);
    const y = boardY + (cell / 2) + 1;
    parts.push(`<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="32" font-weight="700" fill="#e6edf3" stroke="#000" stroke-width="1.8" paint-order="stroke fill">${String.fromCharCode(65 + c)}</text>`);
  }
  for (let r = 0; r < rows; r += 1) {
    const x = boardX + (cell / 2);
    const y = boardY + ((r + 1) * cell) + (cell / 2) + 1;
    parts.push(`<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="32" font-weight="700" fill="#e6edf3" stroke="#000" stroke-width="1.8" paint-order="stroke fill">${r + 1}</text>`);
  }

  parts.push(`<g filter="url(#cellShadow)">`);
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const display = board.getCellDisplay(r, c, revealAll);
      const x = boardX + ((c + 1) * cell) + tileInset;
      const y = boardY + ((r + 1) * cell) + tileInset;
      if (display === "hidden" || display === "flag") {
        const fill = hiddenContributionColor(board, r, c);
        parts.push(`<rect x="${x}" y="${y}" width="${tileSize}" height="${tileSize}" rx="5" fill="${fill}" stroke="#000" stroke-opacity="0.25" stroke-width="0.5"/>`);
        if (display === "hidden") {
          const cx = x + (tileSize / 2);
          const cy = y + (tileSize / 2);
          parts.push(`<text x="${cx}" y="${cy}" text-anchor="middle" dominant-baseline="middle" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-size="22" font-weight="800" fill="#f0f6fc" stroke="#010409" stroke-width="2.2" paint-order="stroke fill">${coordToLabel(r, c)}</text>`);
        } else {
          const badgeCx = x + (tileSize / 2);
          const badgeCy = y + (tileSize / 2);
          const badgeR = tileSize * 0.34;
          const poleW = tileSize * 0.09;
          const poleTop = y + (tileSize * 0.22);
          const poleBottom = y + (tileSize * 0.78);
          const poleX = x + (tileSize * 0.44);
          const pennantTop = y + (tileSize * 0.24);
          const pennantMid = y + (tileSize * 0.40);
          const pennantBottom = y + (tileSize * 0.55);
          const pennantTip = x + (tileSize * 0.79);
          const baseY = y + (tileSize * 0.80);
          parts.push(`<circle cx="${badgeCx}" cy="${badgeCy}" r="${badgeR}" fill="#0d1117" fill-opacity="0.66" stroke="#f0f6fc" stroke-opacity="0.8" stroke-width="1.6"/>`);
          parts.push(`<rect x="${poleX}" y="${poleTop}" width="${poleW}" height="${poleBottom - poleTop}" rx="1" fill="#f0f6fc" stroke="#8b949e" stroke-width="0.8"/>`);
          parts.push(`<path d="M ${poleX + poleW} ${pennantTop} L ${pennantTip} ${pennantMid} L ${poleX + poleW} ${pennantBottom} Z" fill="#f85149" stroke="#ffd6d8" stroke-width="0.9"/>`);
          parts.push(`<rect x="${poleX - (tileSize * 0.08)}" y="${baseY}" width="${tileSize * 0.24}" height="${tileSize * 0.06}" rx="1" fill="#f0f6fc" stroke="#8b949e" stroke-width="0.8"/>`);
        }
        continue;
      }
      if (display === "mine" || display === "exploded") {
        parts.push(`<rect x="${x}" y="${y}" width="${tileSize}" height="${tileSize}" rx="5" fill="#3d1416" stroke="#f85149" stroke-width="1.5"/>`);
        const iconSize = Math.floor(tileSize * 0.7);
        const iconX = x + ((tileSize - iconSize) / 2);
        const iconY = y + ((tileSize - iconSize) / 2);
        parts.push(`<use href="#bomb" x="${iconX}" y="${iconY}" width="${iconSize}" height="${iconSize}"/>`);
        continue;
      }
      parts.push(`<rect x="${x}" y="${y}" width="${tileSize}" height="${tileSize}" rx="5" fill="#1c2128" stroke="#262c36" stroke-width="1"/>`);
      if (display !== "empty") {
        const color = NUMBER_COLORS[display] ?? "#f0f6fc";
        const fontSize = Math.floor(tileSize * 0.56);
        const cx = x + (tileSize / 2);
        const cy = y + (tileSize / 2) + (fontSize * 0.34);
        parts.push(`<text x="${cx}" y="${cy}" text-anchor="middle" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" font-weight="800" font-size="${fontSize}" fill="${color}">${display}</text>`);
      }
    }
  }
  parts.push("</g>");
  parts.push(renderTerminalOverlaySvg(board, {
    cell,
    tileInset,
    tileSize,
    playableX,
    playableY,
    playableWidth,
    playableHeight,
  }));
  parts.push("</svg>");
  return parts.join("");
}

type BoardSvgLayout = {
  cell: number;
  tileInset: number;
  tileSize: number;
  playableX: number;
  playableY: number;
  playableWidth: number;
  playableHeight: number;
};

function renderTerminalOverlaySvg(board: Board, layout: BoardSvgLayout): string {
  if (board.phase === "won") return renderWinOverlaySvg(board, layout);
  if (board.phase === "lost") return renderLossOverlaySvg(layout);
  if (board.phase === "expired") return renderExpiredOverlaySvg(layout);
  return "";
}

function renderWinOverlaySvg(board: Board, layout: BoardSvgLayout): string {
  const colors = ["#2ea043", "#58a6ff", "#d2a8ff", "#ffa657", "#f85149", "#f0f6fc"];
  const confetti: string[] = [];
  for (let i = 0; i < 24; i += 1) {
    const rawX = seedHash(`${board.seed}:confetti-x:${i}`) % 1000;
    const rawDelay = seedHash(`${board.seed}:confetti-delay:${i}`) % 1400;
    const rawDrift = (seedHash(`${board.seed}:confetti-drift:${i}`) % 70) - 35;
    const x = layout.playableX + ((rawX / 1000) * layout.playableWidth);
    const startY = layout.playableY - 24 - (i % 4) * 18;
    const endY = layout.playableY + layout.playableHeight + 28;
    const color = colors[i % colors.length];
    const delay = `${(rawDelay / 1000).toFixed(2)}s`;
    const rotate = (i * 31) % 180;
    confetti.push(
      `<rect x="${x.toFixed(1)}" y="${startY}" width="8" height="13" rx="1.5" fill="${color}" opacity="0.9" transform="rotate(${rotate} ${x.toFixed(1)} ${startY})">
        <animate attributeName="y" values="${startY};${endY}" dur="2.8s" begin="${delay}" repeatCount="indefinite"/>
        <animateTransform attributeName="transform" type="translate" additive="sum" values="0 0;${rawDrift} 0;0 0" dur="2.8s" begin="${delay}" repeatCount="indefinite"/>
      </rect>`,
    );
  }

  const leftBalloonX = layout.playableX + 44;
  const rightBalloonX = layout.playableX + layout.playableWidth - 44;
  const balloonY = layout.playableY + 78;
  const trophyCx = layout.playableX + (layout.playableWidth / 2);
  const trophyCy = layout.playableY + (layout.playableHeight / 2);
  return `<g aria-label="Win celebration overlay">
    <rect x="${layout.playableX}" y="${layout.playableY}" width="${layout.playableWidth}" height="${layout.playableHeight}" fill="#238636" opacity="0.08"/>
    ${confetti.join("")}
    <g opacity="0.9" transform="translate(${trophyCx} ${trophyCy})">
      <circle cx="0" cy="0" r="82" fill="#010409" fill-opacity="0.58" stroke="#2ea043" stroke-width="6" stroke-opacity="0.9"/>
      <path d="M -47 -38 H 47 L 39 11 C 35 36 18 51 0 51 C -18 51 -35 36 -39 11 Z" fill="#ffd33d" stroke="#f0f6fc" stroke-width="4" stroke-linejoin="round"/>
      <path d="M -47 -27 H -68 C -68 8 -53 25 -35 26" fill="none" stroke="#ffd33d" stroke-width="12" stroke-linecap="round"/>
      <path d="M 47 -27 H 68 C 68 8 53 25 35 26" fill="none" stroke="#ffd33d" stroke-width="12" stroke-linecap="round"/>
      <path d="M -18 55 H 18 V 78 H -18 Z" fill="#ffd33d" stroke="#f0f6fc" stroke-width="4" stroke-linejoin="round"/>
      <path d="M -45 78 H 45 V 96 H -45 Z" fill="#ffd33d" stroke="#f0f6fc" stroke-width="4" stroke-linejoin="round"/>
      <path d="M -24 -24 H 24" stroke="#fff8c5" stroke-width="7" stroke-linecap="round" opacity="0.72"/>
    </g>
    <g opacity="0.88">
      <g>
        <animateTransform attributeName="transform" type="rotate" values="-4 ${leftBalloonX} ${balloonY + 46};4 ${leftBalloonX} ${balloonY + 46};-4 ${leftBalloonX} ${balloonY + 46}" dur="3.4s" repeatCount="indefinite"/>
      <path d="M ${leftBalloonX} ${balloonY + 45} C ${leftBalloonX - 15} ${balloonY + 105}, ${leftBalloonX + 22} ${balloonY + 140}, ${leftBalloonX - 4} ${balloonY + 190}" fill="none" stroke="#e6edf3" stroke-width="2" stroke-linecap="round"/>
      <ellipse cx="${leftBalloonX}" cy="${balloonY}" rx="27" ry="34" fill="#58a6ff" stroke="#f0f6fc" stroke-width="2">
        <animateTransform attributeName="transform" type="translate" values="0 0;0 -7;0 0" dur="2.4s" repeatCount="indefinite"/>
      </ellipse>
      <path d="M ${leftBalloonX - 6} ${balloonY + 34} L ${leftBalloonX + 6} ${balloonY + 34} L ${leftBalloonX} ${balloonY + 45} Z" fill="#58a6ff"/>
      </g>
      <g>
        <animateTransform attributeName="transform" type="rotate" values="4 ${rightBalloonX} ${balloonY + 58};-4 ${rightBalloonX} ${balloonY + 58};4 ${rightBalloonX} ${balloonY + 58}" dur="3.1s" repeatCount="indefinite"/>
      <path d="M ${rightBalloonX} ${balloonY + 45} C ${rightBalloonX + 16} ${balloonY + 98}, ${rightBalloonX - 18} ${balloonY + 135}, ${rightBalloonX + 4} ${balloonY + 190}" fill="none" stroke="#e6edf3" stroke-width="2" stroke-linecap="round"/>
      <ellipse cx="${rightBalloonX}" cy="${balloonY + 12}" rx="25" ry="32" fill="#d2a8ff" stroke="#f0f6fc" stroke-width="2">
        <animateTransform attributeName="transform" type="translate" values="0 0;0 -6;0 0" dur="2.1s" repeatCount="indefinite"/>
      </ellipse>
      <path d="M ${rightBalloonX - 6} ${balloonY + 46} L ${rightBalloonX + 6} ${balloonY + 46} L ${rightBalloonX} ${balloonY + 57} Z" fill="#d2a8ff"/>
      </g>
    </g>
  </g>`;
}

function renderLossOverlaySvg(layout: BoardSvgLayout): string {
  const cx = layout.playableX + (layout.playableWidth / 2);
  const cy = layout.playableY + (layout.playableHeight / 2);
  const radius = Math.min(layout.playableWidth, layout.playableHeight) * 0.24;

  return `<g aria-label="Mine blast overlay">
    <rect x="${layout.playableX}" y="${layout.playableY}" width="${layout.playableWidth}" height="${layout.playableHeight}" fill="#f85149" opacity="0.1"/>
    <circle cx="${cx}" cy="${cy}" r="${radius}" fill="#0d1117" fill-opacity="0.78" stroke="#f85149" stroke-width="8"/>
    <circle cx="${cx}" cy="${cy}" r="${radius * 1.03}" fill="none" stroke="#f85149" stroke-width="4" stroke-opacity="0.62">
      <animate attributeName="r" values="${radius * 1.03};${radius * 1.34}" dur="1.6s" repeatCount="indefinite"/>
      <animate attributeName="stroke-opacity" values="0.62;0" dur="1.6s" repeatCount="indefinite"/>
    </circle>
    <g transform="translate(${cx} ${cy})">
      <use href="#bomb" x="-76" y="-76" width="152" height="152"/>
    </g>
  </g>`;
}

function renderExpiredOverlaySvg(layout: BoardSvgLayout): string {
  const cx = layout.playableX + (layout.playableWidth / 2);
  const cy = layout.playableY + (layout.playableHeight / 2);
  const radius = Math.min(layout.playableWidth, layout.playableHeight) * 0.24;
  return `<g aria-label="Expired timer overlay">
    <rect x="${layout.playableX}" y="${layout.playableY}" width="${layout.playableWidth}" height="${layout.playableHeight}" fill="#010409" opacity="0.34"/>
    <circle cx="${cx}" cy="${cy}" r="${radius}" fill="#0d1117" fill-opacity="0.72" stroke="#d2a8ff" stroke-width="8"/>
    <rect x="${cx - 18}" y="${cy - radius - 22}" width="36" height="18" rx="5" fill="#d2a8ff" opacity="0.9"/>
    <line x1="${cx}" y1="${cy}" x2="${cx}" y2="${cy - (radius * 0.62)}" stroke="#f0f6fc" stroke-width="9" stroke-linecap="round"/>
    <line x1="${cx}" y1="${cy}" x2="${cx + (radius * 0.47)}" y2="${cy + (radius * 0.26)}" stroke="#f0f6fc" stroke-width="9" stroke-linecap="round">
      <animateTransform attributeName="transform" type="rotate" from="0 ${cx} ${cy}" to="360 ${cx} ${cy}" dur="4s" repeatCount="indefinite"/>
    </line>
    <circle cx="${cx}" cy="${cy}" r="9" fill="#f0f6fc"/>
  </g>`;
}

function hiddenContributionTone(board: Board, row: number, col: number): number {
  return seedHash(`${board.seed}:${row}:${col}`) % CONTRIBUTION_COLORS.length;
}

function hiddenContributionColor(board: Board, row: number, col: number): string {
  return CONTRIBUTION_COLORS[hiddenContributionTone(board, row, col)];
}

function renderRoomHeader(issueNumber: number, phase: Phase): string {
  const labels: Record<Phase, string> = {
    playing: "⛏️ In Progress",
    won: "🏆 You Win!",
    lost: "💥 Game Over",
    given_up: "🏳️ Abandoned",
    expired: "⌛ Expired",
  };
  return `### Minesweeper Room #${issueNumber} — ${labels[phase]}`;
}

function renderStats(board: Board): string {
  const minesRemaining = board.numMines - board.flaggedCount();
  return `Mines remaining: **${minesRemaining}** | Cells revealed: **${board.revealedCount()}**`;
}

function formatRoomOpen(header: string, boardText: string, stats: string, mines: number): string {
  return `${header}\n\nWelcome to your Minesweeper room! A **9×9** board with **${mines}** hidden mines has been generated.\n\n${boardText}\n\n${stats}\n\n${COMMAND_REMINDER}`;
}

function formatMoveResponse(
  header: string,
  message: string,
  boardText: string,
  stats: string,
  phase: Phase,
): string {
  const parts = [header, "", message, "", boardText, "", stats];
  if (phase === "playing") parts.push("", COMMAND_REMINDER);
  return parts.join("\n");
}

function renderMalformedCommand(): string {
  return (
    "I didn't recognize a valid command. Available commands:\n\n" +
    "- `A1 B2` — reveal one or more cells (same as `guess A1 B2`)\n" +
    "- `flag H7 H8` — flag one or more suspected mines\n" +
    "- `unflag H7` — remove one or more flags\n" +
    "- `giveup` — end the game\n\n" +
    "Leading `/` is still accepted (for example `/flag B3`)."
  );
}

function renderGameOverNotice(phase: Phase): string {
  const phaseLabel: Record<Phase, string> = {
    won: "won",
    lost: "lost",
    given_up: "given up",
    expired: "expired",
    playing: "in progress",
  };
  return `This game is already **${phaseLabel[phase]}**. Open a new issue to start another game.`;
}

function resultMessage(action: CommandAction, label: string, result: MoveResult): string {
  if (result === "win") {
    return "🏆 **You win!** All safe cells have been revealed. Congratulations!";
  }
  if (result === "loss") {
    return `💥 **BOOM!** You hit a mine at **${label}**. Game over.`;
  }
  if (result === "no_op") {
    return `No effect — \`${action} ${label}\` had nothing to do.`;
  }
  if (result === "invalid") {
    return `Invalid move: \`${action} ${label}\`.`;
  }
  if (action === "reveal") return `Revealed **${label}**.`;
  if (action === "flag") return `🚩 Flagged **${label}**.`;
  if (action === "unflag") return `Unflagged **${label}**.`;
  return `Applied \`${action} ${label}\`.`;
}

function executeCommand(board: Board, command: ParsedCommand): { result: MoveResult; message: string } {
  if (command.action === "giveup") {
    const result = board.giveUp();
    return { result, message: "🏳️ You gave up. All mines are revealed." };
  }

  if (!command.coordinate) {
    return {
      result: "invalid",
      message: `The \`${command.action}\` command requires a coordinate (e.g. \`${command.action} B3\`).`,
    };
  }

  const parsed = parseCoord(command.coordinate, board.rows, board.cols);
  if (!parsed) {
    return {
      result: "invalid",
      message: `Invalid coordinate \`${command.coordinate}\`. Use a letter A–${String.fromCharCode(64 + board.cols)} and a number 1–${board.rows} (e.g. \`B3\`).`,
    };
  }

  const [row, col] = parsed;
  const label = coordToLabel(row, col);
  let result: MoveResult;
  if (command.action === "reveal") result = board.reveal(row, col);
  else if (command.action === "flag") result = board.flag(row, col);
  else result = board.unflag(row, col);
  return { result, message: resultMessage(command.action, label, result) };
}

function finalizeTurnResult(results: MoveResult[]): MoveResult {
  if (results.length === 0) return "invalid";
  if (results.includes("win")) return "win";
  if (results.includes("loss")) return "loss";
  if (results.includes("invalid")) return "invalid";
  if (results.includes("ok")) return "ok";
  return "no_op";
}

function executeTurn(board: Board, commands: ParsedCommand[]): { result: MoveResult; message: string } {
  if (commands.length === 0) {
    return { result: "invalid", message: "No command found in this move." };
  }

  const results: MoveResult[] = [];
  const messages: string[] = [];
  for (const command of commands) {
    const step = executeCommand(board, command);
    results.push(step.result);
    messages.push(step.message);
    if (step.result === "invalid" || step.result === "loss" || step.result === "win") break;
    if (board.phase !== "playing") break;
  }

  const result = finalizeTurnResult(results);
  if (messages.length === 1) return { result, message: messages[0] };
  return {
    result,
    message: `Processed move steps:\n${messages.map((entry) => `- ${entry}`).join("\n")}`,
  };
}

function deriveRoomKey(repo: string, issueNumber: number, owner: string): string {
  return `${repo}#${issueNumber}@${owner}`;
}

async function encodeStateToken(state: GameStateV1, secret: string): Promise<string> {
  return encodeSignedToken(state as unknown as Record<string, unknown>, secret);
}

function stateMarkerFromToken(token: string): string {
  return `<!-- ${STATE_MARKER}: ${token} -->`;
}

function parseGameState(raw: Record<string, unknown>): GameStateV1 | null {
  if (raw.schema !== "v1" || raw.version !== 1) return null;
  if (typeof raw.room_key !== "string") return null;
  if (typeof raw.runtime !== "string") return null;
  if (typeof raw.owner !== "string") return null;
  if (typeof raw.issue_number !== "number") return null;
  if (typeof raw.rows !== "number" || typeof raw.cols !== "number" || typeof raw.mines !== "number") return null;
  if (typeof raw.seed !== "number" || typeof raw.phase !== "string" || typeof raw.seq !== "number") return null;
  if (!Array.isArray(raw.revealed) || !Array.isArray(raw.flagged) || !Array.isArray(raw.processed_comment_ids)) return null;
  return raw as unknown as GameStateV1;
}

async function decodeStateToken(token: string, secret: string): Promise<GameStateV1 | null> {
  const raw = await decodeSignedToken(token, secret);
  if (!raw) return null;
  return parseGameState(raw);
}

async function decodeStateFromComment(
  commentBody: string,
  secret: string,
): Promise<GameStateV1 | null> {
  const token = extractStateToken(commentBody);
  if (!token) return null;
  return decodeStateToken(token, secret);
}

function headersInitToRecord(headers: HeadersInit | undefined): Record<string, string> {
  if (!headers) return {};
  if (headers instanceof Headers) {
    const out: Record<string, string> = {};
    headers.forEach((value, key) => {
      out[key] = value;
    });
    return out;
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers.map(([key, value]) => [key, value]));
  }
  return { ...headers };
}

async function ghFetch(
  env: Env,
  installationId: number,
  repo: string,
  path: string,
  init: RequestInit = {},
  options: { contentGenerating?: boolean } = {},
): Promise<Response> {
  const result = await guardedGitHubRequest(env, {
    installationId,
    repo,
    path,
    method: init.method ?? "GET",
    headers: headersInitToRecord(init.headers),
    body: typeof init.body === "string" ? init.body : undefined,
    contentGenerating: Boolean(options.contentGenerating),
  });
  if (result.suppressed) {
    throw new Error(`github_api_guard_suppressed:${result.reason ?? "blocked"}`);
  }
  return new Response(result.body, {
    status: result.status,
    headers: result.headers,
  });
}

function renderNonOwnerWarning(senderLogin: string): string {
  const safeLogin = senderLogin.replace(/[^A-Za-z0-9-]/g, "");
  const mention = safeLogin ? `@${safeLogin}` : "This account";
  return `${mention} Only the issue opener can play in Minesweeper rooms. Further comments in active game rooms may result in being blocked from this repository owner's projects and reported to GitHub.`;
}

function renderOwnerSpamWarning(): string {
  return "Please slow down. Rapid repeated comments may be ignored to protect the game room and the GitHub API. If rapid comments continue, this room may be locked.";
}

function renderOwnerSpamLock(): string {
  return "This room is being locked because it received too many rapid repeated comments. Open a new issue to start another game.";
}

async function blockGitHubUser(
  env: Env,
  installationId: number,
  username: string,
): Promise<boolean> {
  const result = await guardedBlockGitHubUser(env, {
    installationId,
    username,
  });
  if (result.skipped) {
    console.warn("github_user_block_skipped", {
      username,
      reason: result.reason ?? null,
    });
    return false;
  }
  if (result.blocked) return true;
  console.error("github_user_block_failed", {
    username,
    status: result.status ?? null,
    reason: result.reason ?? null,
  });
  return false;
}

async function listIssueComments(
  env: Env,
  installationId: number,
  repo: string,
  issueNumber: number,
): Promise<GitHubIssueComment[]> {
  const out: GitHubIssueComment[] = [];
  let page = 1;
  while (true) {
    const resp = await ghFetch(
      env,
      installationId,
      repo,
      `/issues/${issueNumber}/comments?per_page=100&sort=created&direction=asc&page=${page}`,
    );
    if (!resp.ok) break;
    const rows = (await resp.json()) as unknown;
    if (!Array.isArray(rows) || rows.length === 0) break;
    for (const row of rows) {
      const comment = asObject(row);
      if (!comment) continue;
      out.push({
        id: Number(comment.id ?? 0),
        body: typeof comment.body === "string" ? comment.body : "",
        user: asObject(comment.user)
          ? {
              login: typeof asObject(comment.user)?.login === "string"
                ? (asObject(comment.user)?.login as string)
                : "",
              bot: Boolean(asObject(comment.user)?.bot),
            }
          : undefined,
      });
    }
    if (rows.length < 100) break;
    page += 1;
  }
  return out;
}

async function postIssueComment(
  env: Env,
  installationId: number,
  repo: string,
  issueNumber: number,
  body: string,
): Promise<void> {
  const resp = await ghFetch(
    env,
    installationId,
    repo,
    `/issues/${issueNumber}/comments`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ body }),
    },
    { contentGenerating: true },
  );
  if (!resp.ok) {
    console.warn("post_issue_comment_failed", { repo, issueNumber, status: resp.status });
  }
}

async function lockIssue(
  env: Env,
  installationId: number,
  repo: string,
  issueNumber: number,
): Promise<void> {
  const resp = await ghFetch(
    env,
    installationId,
    repo,
    `/issues/${issueNumber}/lock`,
    {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ lock_reason: "resolved" }),
    },
  );
  if (!resp.ok) {
    console.log(`Issue lock request returned ${resp.status} for ${repo}#${issueNumber}`);
  }
}

async function ensureLeaderboardGameRecord(
  env: Env,
  installationId: number,
  repo: string,
  state: GameStateV1,
): Promise<void> {
  try {
    const record = buildLeaderboardGameRecord(state, new Date().toISOString());
    if (!record) return;

    const recordPath = `${LEADERBOARD_GAME_RECORD_ROOT}/${state.issue_number}.json`;
    const encodedPath = recordPath.split("/").map(encodeURIComponent).join("/");
    const exists = await ghFetch(
      env,
      installationId,
      repo,
      `/contents/${encodedPath}?ref=${encodeURIComponent(LEADERBOARD_RECORD_BRANCH)}`,
    );
    if (exists.status === 200) {
      console.log("leaderboard_game_record_exists", {
        repo,
        issueNumber: state.issue_number,
        path: recordPath,
      });
      return;
    }
    if (exists.status !== 404) {
      console.warn("leaderboard_game_record_check_failed", {
        repo,
        issueNumber: state.issue_number,
        path: recordPath,
        status: exists.status,
      });
      return;
    }

    const content = btoa(`${stableJsonStringify(record)}\n`);
    const created = await ghFetch(
      env,
      installationId,
      repo,
      `/contents/${encodedPath}`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          message: `leaderboard: record game #${state.issue_number}`,
          content,
          branch: LEADERBOARD_RECORD_BRANCH,
        }),
      },
      { contentGenerating: true },
    );
    if (!created.ok) {
      console.warn("leaderboard_game_record_write_failed", {
        repo,
        issueNumber: state.issue_number,
        path: recordPath,
        status: created.status,
      });
      return;
    }
    console.log("leaderboard_game_record_written", {
      repo,
      issueNumber: state.issue_number,
      path: recordPath,
    });
  } catch (err) {
    console.warn("leaderboard_game_record_error", {
      repo,
      issueNumber: state.issue_number,
      error: err instanceof Error ? err.message : String(err),
    });
    return;
  }
}

async function createRoomBody(
  env: Env,
  repo: string,
  issueNumber: number,
  owner: string,
  requestOrigin: string,
): Promise<{ body: string; state: GameStateV1 }> {
  const rows = parseIntOr(env.GAME_ROWS, 9);
  const cols = parseIntOr(env.GAME_COLS, 9);
  const mines = parseIntOr(env.GAME_MINES, 10);
  const seed = ((Date.now() >>> 0) ^ seedHash(`${repo}#${issueNumber}@${owner}`)) >>> 0;
  const state: GameStateV1 = {
    schema: "v1",
    version: 1,
    runtime: "edge-cfw1",
    room_key: deriveRoomKey(repo, issueNumber, owner),
    issue_number: issueNumber,
    owner,
    rows,
    cols,
    mines,
    seed,
    revealed: [],
    flagged: [],
    phase: "playing",
    seq: 0,
    processed_comment_ids: [],
  };
  const board = new Board(rows, cols, mines, seed);
  const stateToken = await encodeStateToken(state, env.MINESWEEPER_SECRET);
  const header = renderRoomHeader(issueNumber, "playing");
  const boardText = renderBoardPictureHtml(requestOrigin, stateToken);
  const stats = renderStats(board);
  const content = formatRoomOpen(header, boardText, stats, mines);
  const marker = stateMarkerFromToken(stateToken);
  return {
    body: `${content}\n\n${marker}`,
    state,
  };
}

async function applyMove(
  env: Env,
  requestOrigin: string,
  priorState: GameStateV1,
  turn: ParsedTurn,
  commentId: number,
): Promise<{
  body: string | null;
  state: GameStateV1;
  result: string;
  lockIssue: boolean;
}> {
  if (priorState.processed_comment_ids.includes(commentId)) {
    return { body: null, state: priorState, result: "duplicate", lockIssue: false };
  }
  const board = Board.fromState(priorState);
  if (board.phase !== "playing") {
    return {
      body: renderGameOverNotice(board.phase),
      state: priorState,
      result: "game_over",
      lockIssue: false,
    };
  }

  const executed = executeTurn(board, turn.commands);
  const result = executed.result;
  const message = executed.message;

  const fields = board.toStateFields();
  const phase = fields.phase as Phase;
  const newState: GameStateV1 = {
    ...priorState,
    revealed: fields.revealed,
    flagged: fields.flagged,
    phase,
    seq: priorState.seq + 1,
    processed_comment_ids: [...priorState.processed_comment_ids, commentId],
  };
  const header = renderRoomHeader(newState.issue_number, phase);
  const stateToken = await encodeStateToken(newState, env.MINESWEEPER_SECRET);
  const bodyText = renderBoardPictureHtml(requestOrigin, stateToken);
  const stats = renderStats(board);
  const content = formatMoveResponse(header, message, bodyText, stats, phase);
  const marker = stateMarkerFromToken(stateToken);

  return {
    body: `${content}\n\n${marker}`,
    state: newState,
    result,
    lockIssue: phase !== "playing",
  };
}

async function expireGame(
  env: Env,
  requestOrigin: string,
  priorState: GameStateV1,
  commentId: number,
): Promise<{
  body: string | null;
  state: GameStateV1;
  result: string;
  lockIssue: boolean;
}> {
  if (priorState.processed_comment_ids.includes(commentId)) {
    return { body: null, state: priorState, result: "duplicate", lockIssue: false };
  }
  const newState: GameStateV1 = {
    ...priorState,
    phase: "expired",
    seq: priorState.seq + 1,
    processed_comment_ids: [...priorState.processed_comment_ids, commentId],
  };
  const board = Board.fromState(newState);
  const header = renderRoomHeader(newState.issue_number, "expired");
  const stateToken = await encodeStateToken(newState, env.MINESWEEPER_SECRET);
  const bodyText = renderBoardPictureHtml(requestOrigin, stateToken);
  const stats = renderStats(board);
  const content = formatMoveResponse(
    header,
    "This Minesweeper room has expired because it has been open for more than 30 minutes. Open a new issue to start another game.",
    bodyText,
    stats,
    "expired",
  );
  const marker = stateMarkerFromToken(stateToken);
  return {
    body: `${content}\n\n${marker}`,
    state: newState,
    result: "expired",
    lockIssue: true,
  };
}

async function reconcileStateBeforeComment(
  env: Env,
  requestOrigin: string,
  comments: GitHubIssueComment[],
  currentCommentId: number,
  baseStateCommentId: number,
  state: GameStateV1,
): Promise<GameStateV1> {
  let mutableState = state;
  const owner = state.owner.toLowerCase();
  const processed = new Set<number>(state.processed_comment_ids);
  for (const comment of comments) {
    if (comment.id <= baseStateCommentId || comment.id >= currentCommentId) continue;
    if (processed.has(comment.id)) continue;
    if (comment.user?.bot) continue;
    if ((comment.user?.login ?? "").toLowerCase() !== owner) continue;
    const turn = parseTurn(comment.body ?? "");
    if (!turn) continue;
    const move = await applyMove(env, requestOrigin, mutableState, turn, comment.id);
    mutableState = move.state;
    for (const id of mutableState.processed_comment_ids) processed.add(id);
  }
  return mutableState;
}

async function handleIssuesOpened(
  env: Env,
  installationId: number,
  requestOrigin: string,
  payload: Record<string, unknown>,
): Promise<{ action: string; result?: string | null }> {
  if (payload.action !== "opened") return { action: "ignored" };
  const issue = asObject(payload.issue);
  const repoObj = asObject(payload.repository);
  if (!issue || !repoObj) return { action: "invalid_payload" };
  const labels = labelsFromIssue(payload);
  if (!labels.includes(ACTIVE_GAME_LABEL)) return { action: "ignored_no_game_label" };
  const issueNumber = Number(issue.number ?? 0);
  const owner = typeof asObject(issue.user)?.login === "string" ? (asObject(issue.user)?.login as string) : "";
  const repo = typeof repoObj.full_name === "string" ? repoObj.full_name : "";
  if (!issueNumber || !owner || !repo) return { action: "invalid_payload" };

  const room = await createRoomBody(env, repo, issueNumber, owner, requestOrigin);
  await postIssueComment(env, installationId, repo, issueNumber, room.body);
  return { action: "create_room", result: "ok" };
}

async function handleIssueCommentCreated(
  env: Env,
  installationId: number,
  requestOrigin: string,
  payload: Record<string, unknown>,
): Promise<{ action: string; result?: string | null }> {
  if (payload.action !== "created") return { action: "ignored" };
  const issue = asObject(payload.issue);
  const comment = asObject(payload.comment);
  const sender = asObject(payload.sender);
  const repoObj = asObject(payload.repository);
  if (!issue || !comment || !sender || !repoObj) return { action: "invalid_payload" };

  const labels = labelsFromIssue(payload);
  if (!labels.includes(ACTIVE_GAME_LABEL)) return { action: "ignored_no_game_label" };
  if (Boolean(asObject(comment.user)?.bot)) return { action: "ignored_bot_comment" };

  const issueNumber = Number(issue.number ?? 0);
  const repo = typeof repoObj.full_name === "string" ? repoObj.full_name : "";
  const owner = typeof asObject(issue.user)?.login === "string" ? (asObject(issue.user)?.login as string) : "";
  const senderLogin = typeof sender.login === "string" ? sender.login : "";
  const senderType = typeof sender.type === "string" ? sender.type : "";
  const commentId = Number(comment.id ?? 0);
  const commentBody = typeof comment.body === "string" ? comment.body : "";
  const issueCreatedAt = typeof issue.created_at === "string" ? issue.created_at : undefined;
  const commentCreatedAt = typeof comment.created_at === "string" ? comment.created_at : undefined;
  if (!issueNumber || !repo || !owner || !commentId) return { action: "invalid_payload" };
  if (senderType !== "User" || senderLogin.toLowerCase().endsWith("[bot]")) {
    return { action: "ignored_bot_sender" };
  }

  if (senderLogin.toLowerCase() !== owner.toLowerCase()) {
    const decision = await decideAbuseGuard(env, {
      kind: "non_owner",
      repo,
      issueNumber,
      owner,
      sender: senderLogin,
    });
    if (decision.action === "warn_non_owner") {
      await postIssueComment(env, installationId, repo, issueNumber, renderNonOwnerWarning(senderLogin));
      return { action: "warned_non_owner", result: decision.reason };
    }
    if (decision.action === "block_non_owner") {
      const blocked = await blockGitHubUser(env, installationId, senderLogin);
      console.warn("abuse_guard_block_attempted", {
        repo,
        issueNumber,
        sender: senderLogin,
        count: decision.count ?? null,
        blocked,
      });
      return {
        action: blocked ? "blocked_non_owner" : "block_failed_non_owner",
        result: decision.reason,
      };
    }
    return { action: "ignored_non_owner", result: decision.reason };
  }

  const ownerDecision = await decideAbuseGuard(env, {
    kind: "owner",
    repo,
    issueNumber,
    owner,
    sender: senderLogin,
  });
  if (ownerDecision.action === "warn_owner") {
    await postIssueComment(env, installationId, repo, issueNumber, renderOwnerSpamWarning());
    return { action: "warned_owner_cooldown", result: ownerDecision.reason };
  }
  if (ownerDecision.action === "lock_room") {
    await postIssueComment(env, installationId, repo, issueNumber, renderOwnerSpamLock());
    await lockIssue(env, installationId, repo, issueNumber);
    console.warn("abuse_guard_owner_room_locked", {
      repo,
      issueNumber,
      owner,
      count: ownerDecision.count ?? null,
    });
    return { action: "locked_owner_spam", result: ownerDecision.reason };
  }
  if (ownerDecision.action === "suppress_owner") {
    return { action: "suppressed_owner_cooldown", result: ownerDecision.reason };
  }

  const allComments = await listIssueComments(env, installationId, repo, issueNumber);
  let baseComment: GitHubIssueComment | null = null;
  let baseState: GameStateV1 | null = null;
  for (const row of allComments) {
    const body = row.body ?? "";
    if (!extractStateToken(body)) continue;
    const decoded = await decodeStateFromComment(body, env.MINESWEEPER_SECRET);
    if (!decoded) continue;
    baseComment = row;
    baseState = decoded;
  }
  if (!baseComment || !baseState) {
    await postIssueComment(
      env,
      installationId,
      repo,
      issueNumber,
      "Could not find the game state. The room may be corrupted or the bot comment was deleted.",
    );
    return { action: "no_state", result: null };
  }
  if (baseState.runtime !== "edge-cfw1") {
    return { action: "ignored_non_edge_state" };
  }

  const reconciled = await reconcileStateBeforeComment(
    env,
    requestOrigin,
    allComments,
    commentId,
    baseComment.id,
    baseState,
  );

  if (reconciled.phase === "playing" && isPastGameplayLimit(issueCreatedAt, commentCreatedAt)) {
    const expired = await expireGame(env, requestOrigin, reconciled, commentId);
    if (expired.body) {
      await postIssueComment(env, installationId, repo, issueNumber, expired.body);
      if (expired.lockIssue) await lockIssue(env, installationId, repo, issueNumber);
    }
    return { action: "move", result: expired.result };
  }

  const turn = parseTurn(commentBody);
  if (!turn) {
    await postIssueComment(env, installationId, repo, issueNumber, renderMalformedCommand());
    return { action: "no_command", result: null };
  }

  const move = await applyMove(env, requestOrigin, reconciled, turn, commentId);
  if (move.body) {
    await postIssueComment(env, installationId, repo, issueNumber, move.body);
    if (move.lockIssue) await ensureLeaderboardGameRecord(env, installationId, repo, move.state);
    if (move.lockIssue) await lockIssue(env, installationId, repo, issueNumber);
  }
  return { action: "move", result: move.result };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/board.svg") {
      if (request.method !== "GET") {
        return json(405, { error: "method_not_allowed" });
      }
      if (!env.MINESWEEPER_SECRET) {
        return json(500, { error: "missing_worker_secrets" });
      }
      const stateToken = url.searchParams.get("state") ?? "";
      if (!stateToken) {
        return json(400, { error: "missing_state" });
      }
      const state = await decodeStateToken(stateToken, env.MINESWEEPER_SECRET);
      if (!state) {
        return json(400, { error: "invalid_state" });
      }
      const board = Board.fromState(state);
      const revealAll = state.phase !== "playing";
      const svg = renderBoardSvg(board, revealAll);
      return new Response(svg, {
        status: 200,
        headers: {
          "content-type": "image/svg+xml; charset=utf-8",
          "cache-control": "private, no-store",
        },
      });
    }

    if (url.pathname !== "/webhook") {
      return json(404, { error: "not_found" });
    }
    if (request.method !== "POST") {
      return json(405, { error: "method_not_allowed" });
    }

    const event = request.headers.get("X-GitHub-Event") ?? "";
    const hasSecret = Boolean(env.GITHUB_WEBHOOK_SECRET?.trim());
    if (!event) {
      return json(400, { error: "missing_event" });
    }
    if (!hasSecret) {
      return json(500, { error: "missing_webhook_secret" });
    }

    if (
      !env.GITHUB_APP_ID
      || !env.GITHUB_APP_PRIVATE_KEY
      || !env.MINESWEEPER_SECRET
    ) {
      return json(500, { error: "missing_worker_secrets" });
    }

    const rawBody = await request.text();
    const signature = request.headers.get("X-Hub-Signature-256");
    const valid = await verifyWebhookSignature(rawBody, signature, env.GITHUB_WEBHOOK_SECRET);
    if (!valid) {
      return json(401, { error: "invalid_signature" });
    }

    let payload: Record<string, unknown>;
    try {
      const parsed = JSON.parse(rawBody);
      const asRec = asObject(parsed);
      if (!asRec) return json(400, { error: "invalid_json" });
      payload = asRec;
    } catch {
      return json(400, { error: "invalid_json" });
    }

    try {
      let result: { action: string; result?: string | null };
      if (event === "issues" || event === "issue_comment") {
        const installationId = getInstallationId(payload);
        if (!installationId) {
          return json(400, { error: "missing_installation" });
        }
        const requestOrigin = url.origin;
        if (event === "issues") {
          result = await handleIssuesOpened(env, installationId, requestOrigin, payload);
        } else {
          result = await handleIssueCommentCreated(
            env,
            installationId,
            requestOrigin,
            payload,
          );
        }
      } else {
        result = { action: "ignored_event" };
      }
      return json(202, {
        status: "accepted",
        action: result.action,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.startsWith("github_api_guard_suppressed:")) {
        return json(202, {
          status: "accepted",
          action: "github_api_suppressed",
          reason: message.slice("github_api_guard_suppressed:".length),
        });
      }
      if (message.startsWith("token_exchange_failed_403") || message.startsWith("token_exchange_failed_429")) {
        return json(202, {
          status: "accepted",
          action: "github_api_rate_limited",
        });
      }
      console.error("processing_failed", { event, message });
      return json(500, { error: "processing_failed" });
    }
  },
};
