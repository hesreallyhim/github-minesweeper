interface Env {
  GITHUB_WEBHOOK_SECRET: string;
  GITHUB_PAT: string;
  MINESWEEPER_SECRET: string;
  GAME_ROWS: string;
  GAME_COLS: string;
  GAME_MINES: string;
  EDGE_LABEL?: string;
}

type CellState = "hidden" | "revealed" | "flagged";
type Phase = "playing" | "won" | "lost" | "given_up";
type MoveResult = "ok" | "win" | "loss" | "no_op" | "invalid";
type ParsedCommand = {
  action: "reveal" | "flag" | "unflag" | "chord" | "giveup";
  coordinate: string | null;
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
  "**Commands:** `/reveal B3` · `/flag H7` · `/unflag H7` · `/chord C4` · `/giveup`";
const DEFAULT_EDGE_LABEL = "game:minesweeper:edge";
const CMD_RE = /\/(reveal|flag|unflag|chord|giveup)\b\s*(\S*)/i;
const IMPLICIT_REVEAL_RE = /^\s*`?([A-Za-z]\d+|\d+[A-Za-z])`?\s*$/;
const COL_ROW_RE = /^([A-Za-z])(\d+)$/;
const ROW_COL_RE = /^(\d+)([A-Za-z])$/;
const STATE_TOKEN_RE = new RegExp(
  `<!--\\s*${STATE_MARKER}:\\s*(\\S+)\\s*-->`,
);

const TEXT_ENCODER = new TextEncoder();
const TEXT_DECODER = new TextDecoder();

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

function getEdgeLabel(env: Env): string {
  const raw = env.EDGE_LABEL?.trim();
  return raw && raw.length > 0 ? raw : DEFAULT_EDGE_LABEL;
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

function parseCommand(text: string): ParsedCommand | null {
  const commandMatch = CMD_RE.exec(text);
  if (commandMatch) {
    const action = commandMatch[1].toLowerCase() as ParsedCommand["action"];
    const rawCoord = (commandMatch[2] ?? "").trim();
    if (action === "giveup") return { action, coordinate: null };
    if (!rawCoord) return { action, coordinate: null };
    return { action, coordinate: rawCoord };
  }
  const implicit = IMPLICIT_REVEAL_RE.exec(text);
  if (implicit) {
    return { action: "reveal", coordinate: implicit[1] };
  }
  return null;
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
    if (this.cellStates[row][col] !== "hidden") return "no_op";
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

function renderBoardTable(board: Board, revealAll: boolean): string {
  const headers: string[] = [];
  for (let c = 0; c < board.cols; c += 1) headers.push(String.fromCharCode(65 + c));
  const lines = [`|   | ${headers.join(" | ")} |`, `|${"---|".repeat(board.cols + 1)}`];
  for (let r = 0; r < board.rows; r += 1) {
    const cells: string[] = [];
    for (let c = 0; c < board.cols; c += 1) {
      const display = board.getCellDisplay(r, c, revealAll);
      const label = coordToLabel(r, c);
      if (display === "hidden") cells.push(`\`${label}\``);
      else if (display === "empty") cells.push("·");
      else if (display === "flag") cells.push("🚩");
      else if (display === "mine") cells.push("💣");
      else if (display === "exploded") cells.push("💥");
      else cells.push(`**${display}**`);
    }
    lines.push(`| ${r + 1} | ${cells.join(" | ")} |`);
  }
  return lines.join("\n");
}

function renderRoomHeader(issueNumber: number, phase: Phase): string {
  const labels: Record<Phase, string> = {
    playing: "⛏️ In Progress",
    won: "🏆 You Win!",
    lost: "💥 Game Over",
    given_up: "🏳️ Abandoned",
  };
  return `### Minesweeper Room #${issueNumber} — ${labels[phase]}`;
}

function renderStats(board: Board): string {
  const minesRemaining = board.numMines - board.flaggedCount();
  return `Mines remaining: **${minesRemaining}** | Cells revealed: **${board.revealedCount()}/${board.safeCount()}**`;
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
    "- `/reveal B3` — reveal a cell\n" +
    "- `/flag H7` — flag a suspected mine\n" +
    "- `/unflag H7` — remove a flag\n" +
    "- `/chord C4` — chord-reveal around a numbered cell\n" +
    "- `/giveup` — end the game"
  );
}

function renderNonOwnerResponse(sender: string): string {
  return `Sorry @${sender}, only the room owner can play in this game. Open your own issue to start a new room!`;
}

function renderGameOverNotice(phase: Phase): string {
  const phaseLabel: Record<Phase, string> = {
    won: "won",
    lost: "lost",
    given_up: "given up",
    playing: "in progress",
  };
  return `This game is already **${phaseLabel[phase]}**. Open a new issue to start another game.`;
}

function resultMessage(action: ParsedCommand["action"], label: string, result: MoveResult): string {
  if (result === "win") {
    return "🏆 **You win!** All safe cells have been revealed. Congratulations!";
  }
  if (result === "loss") {
    return `💥 **BOOM!** You hit a mine at **${label}**. Game over.`;
  }
  if (result === "no_op") {
    return `No effect — \`/${action} ${label}\` had nothing to do.`;
  }
  if (result === "invalid") {
    return `Invalid move: \`/${action} ${label}\`.`;
  }
  if (action === "reveal") return `Revealed **${label}**.`;
  if (action === "flag") return `🚩 Flagged **${label}**.`;
  if (action === "unflag") return `Unflagged **${label}**.`;
  return `Chorded around **${label}**.`;
}

function deriveRoomKey(repo: string, issueNumber: number, owner: string): string {
  return `${repo}#${issueNumber}@${owner}`;
}

async function encodeStateMarker(state: GameStateV1, secret: string): Promise<string> {
  const token = await encodeSignedToken(state as unknown as Record<string, unknown>, secret);
  return `<!-- ${STATE_MARKER}: ${token} -->`;
}

async function decodeStateFromComment(
  commentBody: string,
  secret: string,
): Promise<GameStateV1 | null> {
  const token = extractStateToken(commentBody);
  if (!token) return null;
  const raw = await decodeSignedToken(token, secret);
  if (!raw) return null;
  if (raw.schema !== "v1" || raw.version !== 1) return null;
  return raw as unknown as GameStateV1;
}

async function ghFetch(
  env: Env,
  repo: string,
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  return fetch(`https://api.github.com/repos/${repo}${path}`, {
    ...init,
    headers: {
      accept: "application/vnd.github+json",
      authorization: `Bearer ${env.GITHUB_PAT}`,
      "x-github-api-version": "2022-11-28",
      ...(init.headers ?? {}),
    },
  });
}

async function listIssueComments(
  env: Env,
  repo: string,
  issueNumber: number,
): Promise<GitHubIssueComment[]> {
  const out: GitHubIssueComment[] = [];
  let page = 1;
  while (true) {
    const resp = await ghFetch(
      env,
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
  repo: string,
  issueNumber: number,
  body: string,
): Promise<void> {
  await ghFetch(env, repo, `/issues/${issueNumber}/comments`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ body }),
  });
}

async function updateLabels(
  env: Env,
  repo: string,
  issueNumber: number,
  add: string[],
  remove: string[],
): Promise<void> {
  for (const label of add) {
    await ghFetch(env, repo, `/issues/${issueNumber}/labels`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ labels: [label] }),
    });
  }
  for (const label of remove) {
    await ghFetch(env, repo, `/issues/${issueNumber}/labels/${encodeURIComponent(label)}`, {
      method: "DELETE",
    });
  }
}

async function createRoomBody(
  env: Env,
  repo: string,
  issueNumber: number,
  owner: string,
): Promise<{ body: string; state: GameStateV1; labelsAdd: string[] }> {
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
  const header = renderRoomHeader(issueNumber, "playing");
  const boardText = renderBoardTable(board, false);
  const stats = renderStats(board);
  const content = formatRoomOpen(header, boardText, stats, mines);
  const marker = await encodeStateMarker(state, env.MINESWEEPER_SECRET);
  return {
    body: `${content}\n\n${marker}`,
    state,
    labelsAdd: ["game:minesweeper", getEdgeLabel(env)],
  };
}

async function applyMove(
  env: Env,
  priorState: GameStateV1,
  command: ParsedCommand,
  commentId: number,
): Promise<{
  body: string | null;
  state: GameStateV1;
  result: string;
  labelsAdd: string[];
  labelsRemove: string[];
}> {
  if (priorState.processed_comment_ids.includes(commentId)) {
    return { body: null, state: priorState, result: "duplicate", labelsAdd: [], labelsRemove: [] };
  }
  const board = Board.fromState(priorState);
  if (board.phase !== "playing") {
    return {
      body: renderGameOverNotice(board.phase),
      state: priorState,
      result: "game_over",
      labelsAdd: [],
      labelsRemove: [],
    };
  }

  let result: MoveResult = "invalid";
  let message = "";
  if (command.action === "giveup") {
    result = board.giveUp();
    message = "🏳️ You gave up. All mines are revealed.";
  } else if (!command.coordinate) {
    result = "invalid";
    message = `The \`/${command.action}\` command requires a coordinate (e.g. \`/${command.action} B3\`).`;
  } else {
    const parsed = parseCoord(command.coordinate, board.rows, board.cols);
    if (!parsed) {
      result = "invalid";
      message = `Invalid coordinate \`${command.coordinate}\`. Use a letter A–${String.fromCharCode(64 + board.cols)} and a number 1–${board.rows} (e.g. \`B3\`).`;
    } else {
      const [row, col] = parsed;
      const label = coordToLabel(row, col);
      if (command.action === "reveal") result = board.reveal(row, col);
      else if (command.action === "flag") result = board.flag(row, col);
      else if (command.action === "unflag") result = board.unflag(row, col);
      else result = board.chord(row, col);
      message = resultMessage(command.action, label, result);
    }
  }

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
  const revealAll = phase === "won" || phase === "lost" || phase === "given_up";
  const header = renderRoomHeader(newState.issue_number, phase);
  const bodyText = renderBoardTable(board, revealAll);
  const stats = renderStats(board);
  const content = formatMoveResponse(header, message, bodyText, stats, phase);
  const marker = await encodeStateMarker(newState, env.MINESWEEPER_SECRET);

  const labelsAdd: string[] = [];
  const labelsRemove: string[] = [];
  if (phase === "won") {
    labelsAdd.push("game:minesweeper:won");
    labelsRemove.push("game:minesweeper");
  } else if (phase === "lost") {
    labelsAdd.push("game:minesweeper:lost");
    labelsRemove.push("game:minesweeper");
  } else if (phase === "given_up") {
    labelsAdd.push("game:minesweeper:archived");
    labelsRemove.push("game:minesweeper");
  }
  return {
    body: `${content}\n\n${marker}`,
    state: newState,
    result,
    labelsAdd,
    labelsRemove,
  };
}

async function reconcileStateBeforeComment(
  env: Env,
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
    const cmd = parseCommand(comment.body ?? "");
    if (!cmd) continue;
    const move = await applyMove(env, mutableState, cmd, comment.id);
    mutableState = move.state;
    for (const id of mutableState.processed_comment_ids) processed.add(id);
  }
  return mutableState;
}

async function handleIssuesOpened(
  env: Env,
  payload: Record<string, unknown>,
): Promise<{ action: string; result?: string | null }> {
  if (payload.action !== "opened") return { action: "ignored" };
  const issue = asObject(payload.issue);
  const repoObj = asObject(payload.repository);
  if (!issue || !repoObj) return { action: "invalid_payload" };
  const labels = labelsFromIssue(payload);
  if (!labels.includes(getEdgeLabel(env))) return { action: "ignored_no_edge_label" };
  const issueNumber = Number(issue.number ?? 0);
  const owner = typeof asObject(issue.user)?.login === "string" ? (asObject(issue.user)?.login as string) : "";
  const repo = typeof repoObj.full_name === "string" ? repoObj.full_name : "";
  if (!issueNumber || !owner || !repo) return { action: "invalid_payload" };

  const room = await createRoomBody(env, repo, issueNumber, owner);
  await postIssueComment(env, repo, issueNumber, room.body);
  await updateLabels(env, repo, issueNumber, room.labelsAdd, []);
  return { action: "create_room", result: "ok" };
}

async function handleIssueCommentCreated(
  env: Env,
  payload: Record<string, unknown>,
): Promise<{ action: string; result?: string | null }> {
  if (payload.action !== "created") return { action: "ignored" };
  const issue = asObject(payload.issue);
  const comment = asObject(payload.comment);
  const sender = asObject(payload.sender);
  const repoObj = asObject(payload.repository);
  if (!issue || !comment || !sender || !repoObj) return { action: "invalid_payload" };

  const labels = labelsFromIssue(payload);
  if (!labels.includes(getEdgeLabel(env))) return { action: "ignored_no_edge_label" };
  if (Boolean(asObject(comment.user)?.bot)) return { action: "ignored_bot_comment" };

  const issueNumber = Number(issue.number ?? 0);
  const repo = typeof repoObj.full_name === "string" ? repoObj.full_name : "";
  const owner = typeof asObject(issue.user)?.login === "string" ? (asObject(issue.user)?.login as string) : "";
  const senderLogin = typeof sender.login === "string" ? sender.login : "";
  const commentId = Number(comment.id ?? 0);
  const commentBody = typeof comment.body === "string" ? comment.body : "";
  if (!issueNumber || !repo || !owner || !commentId) return { action: "invalid_payload" };

  const allComments = await listIssueComments(env, repo, issueNumber);
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
      repo,
      issueNumber,
      "Could not find the game state. The room may be corrupted or the bot comment was deleted.",
    );
    return { action: "no_state", result: null };
  }
  if (baseState.runtime !== "edge-cfw1") {
    return { action: "ignored_non_edge_state" };
  }
  if (senderLogin.toLowerCase() !== baseState.owner.toLowerCase()) {
    await postIssueComment(env, repo, issueNumber, renderNonOwnerResponse(senderLogin));
    return { action: "non_owner", result: null };
  }

  const parsed = parseCommand(commentBody);
  if (!parsed) {
    await postIssueComment(env, repo, issueNumber, renderMalformedCommand());
    return { action: "no_command", result: null };
  }

  const reconciled = await reconcileStateBeforeComment(
    env,
    allComments,
    commentId,
    baseComment.id,
    baseState,
  );
  const move = await applyMove(env, reconciled, parsed, commentId);
  if (move.body) {
    await postIssueComment(env, repo, issueNumber, move.body);
    await updateLabels(env, repo, issueNumber, move.labelsAdd, move.labelsRemove);
  }
  return { action: "move", result: move.result };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (new URL(request.url).pathname !== "/webhook") {
      return json(404, { error: "not_found" });
    }
    if (request.method !== "POST") {
      return json(405, { error: "method_not_allowed" });
    }

    const event = request.headers.get("X-GitHub-Event") ?? "";
    const delivery = request.headers.get("X-GitHub-Delivery") ?? "";
    const hasSecret = Boolean(env.GITHUB_WEBHOOK_SECRET?.trim());
    if (!event) {
      return json(400, { error: "missing_event" });
    }
    if (!hasSecret) {
      return json(500, { error: "missing_webhook_secret" });
    }

    if (!env.GITHUB_PAT || !env.MINESWEEPER_SECRET) {
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
      if (event === "issues") {
        result = await handleIssuesOpened(env, payload);
      } else if (event === "issue_comment") {
        result = await handleIssueCommentCreated(env, payload);
      } else {
        result = { action: "ignored_event" };
      }
      return json(202, {
        status: "accepted",
        delivery,
        event,
        action: result.action,
        result: result.result ?? null,
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "unknown";
      return json(500, { error: "processing_failed", message });
    }
  },
};
