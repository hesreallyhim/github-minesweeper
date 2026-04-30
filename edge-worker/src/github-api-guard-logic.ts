export type GitHubApiGuardState = {
  blockedUntilMs: number;
  blockReason: string;
  secondaryBackoffLevel: number;
  lastMutativeMs: number;
  lastContentGeneratingMs: number;
};

export type GitHubRateLimitHeaders = {
  limit: number | null;
  remaining: number | null;
  used: number | null;
  reset: number | null;
  resource: string;
  retryAfter: string;
};

export const MUTATIVE_PACE_MS = 1_000;
export const CONTENT_GENERATING_PACE_MS = 5_000;
export const SECONDARY_BACKOFF_BASE_MS = 60_000;
export const SECONDARY_BACKOFF_MAX_MS = 15 * 60_000;

export function defaultGitHubApiGuardState(): GitHubApiGuardState {
  return {
    blockedUntilMs: 0,
    blockReason: "",
    secondaryBackoffLevel: 0,
    lastMutativeMs: 0,
    lastContentGeneratingMs: 0,
  };
}

export function normalizeGitHubApiGuardState(raw: Partial<GitHubApiGuardState>): GitHubApiGuardState {
  return {
    blockedUntilMs: raw.blockedUntilMs ?? 0,
    blockReason: raw.blockReason ?? "",
    secondaryBackoffLevel: raw.secondaryBackoffLevel ?? 0,
    lastMutativeMs: raw.lastMutativeMs ?? 0,
    lastContentGeneratingMs: raw.lastContentGeneratingMs ?? 0,
  };
}

export function isMutative(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

export function retryAfterToMs(raw: string, nowMs: number): number | null {
  if (!raw) return null;
  const seconds = Number(raw);
  if (Number.isFinite(seconds) && seconds >= 0) {
    return nowMs + Math.ceil(seconds * 1000);
  }
  const absoluteMs = Date.parse(raw);
  return Number.isNaN(absoluteMs) ? null : absoluteMs;
}

export function calculatePacingWaitMs(
  state: GitHubApiGuardState,
  method: string,
  contentGenerating: boolean,
  nowMs: number,
): number {
  let waitMs = 0;
  if (isMutative(method)) {
    waitMs = Math.max(waitMs, MUTATIVE_PACE_MS - (nowMs - state.lastMutativeMs));
  }
  if (contentGenerating) {
    waitMs = Math.max(waitMs, CONTENT_GENERATING_PACE_MS - (nowMs - state.lastContentGeneratingMs));
  }
  return Math.max(0, waitMs);
}

export function clearExpiredBlock(state: GitHubApiGuardState, nowMs: number): void {
  if (state.blockedUntilMs > 0 && state.blockedUntilMs <= nowMs) {
    state.blockedUntilMs = 0;
    state.blockReason = "";
  }
}

export function isBlocked(state: GitHubApiGuardState, nowMs: number): boolean {
  return state.blockedUntilMs > nowMs;
}

export function updateRateLimitState(
  state: GitHubApiGuardState,
  status: number,
  rate: GitHubRateLimitHeaders,
  nowMs: number,
): void {
  const retryAfterMs = retryAfterToMs(rate.retryAfter, nowMs);
  if (retryAfterMs !== null) {
    state.blockedUntilMs = retryAfterMs;
    state.blockReason = "retry_after";
    return;
  }

  if (rate.remaining === 0 && rate.reset !== null) {
    state.blockedUntilMs = rate.reset * 1000;
    state.blockReason = "primary_rate_limit";
    return;
  }

  if (status === 403 || status === 429) {
    const backoffMs = Math.min(
      SECONDARY_BACKOFF_BASE_MS * (2 ** state.secondaryBackoffLevel),
      SECONDARY_BACKOFF_MAX_MS,
    );
    state.secondaryBackoffLevel += 1;
    state.blockedUntilMs = nowMs + backoffMs;
    state.blockReason = "secondary_or_ambiguous_rate_limit";
    return;
  }

  if (status < 400) {
    state.secondaryBackoffLevel = 0;
  }
}
