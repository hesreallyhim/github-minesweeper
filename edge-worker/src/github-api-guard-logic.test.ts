import { describe, expect, it } from "vitest";
import {
  calculatePacingWaitMs,
  clearExpiredBlock,
  CONTENT_GENERATING_PACE_MS,
  defaultGitHubApiGuardState,
  isBlocked,
  isMutative,
  MUTATIVE_PACE_MS,
  retryAfterToMs,
  SECONDARY_BACKOFF_BASE_MS,
  SECONDARY_BACKOFF_MAX_MS,
  updateRateLimitState,
} from "./github-api-guard-logic";

const emptyRate = {
  limit: null,
  remaining: null,
  used: null,
  reset: null,
  resource: "",
  retryAfter: "",
};

describe("GitHub API guard logic", () => {
  it("parses retry-after seconds as a delay", () => {
    expect(retryAfterToMs("2", 10_000)).toBe(12_000);
  });

  it("parses retry-after HTTP dates as absolute timestamps", () => {
    const raw = "Wed, 21 Oct 2030 07:28:00 GMT";
    expect(retryAfterToMs(raw, 10_000)).toBe(Date.parse(raw));
  });

  it("classifies GET-like methods as non-mutative and writes as mutative", () => {
    expect(isMutative("GET")).toBe(false);
    expect(isMutative("head")).toBe(false);
    expect(isMutative("POST")).toBe(true);
    expect(isMutative("PUT")).toBe(true);
  });

  it("calculates no pacing wait for reads", () => {
    const state = defaultGitHubApiGuardState();
    state.lastMutativeMs = 9_500;
    state.lastContentGeneratingMs = 9_500;
    expect(calculatePacingWaitMs(state, "GET", false, 10_000)).toBe(0);
  });

  it("calculates mutative pacing", () => {
    const state = defaultGitHubApiGuardState();
    state.lastMutativeMs = 9_500;
    expect(calculatePacingWaitMs(state, "PUT", false, 10_000)).toBe(MUTATIVE_PACE_MS - 500);
  });

  it("uses the stricter content-generating pacing when applicable", () => {
    const state = defaultGitHubApiGuardState();
    state.lastMutativeMs = 9_500;
    state.lastContentGeneratingMs = 9_000;
    expect(calculatePacingWaitMs(state, "POST", true, 10_000)).toBe(CONTENT_GENERATING_PACE_MS - 1_000);
  });

  it("blocks until retry-after when retry-after is present", () => {
    const state = defaultGitHubApiGuardState();
    updateRateLimitState(state, 403, { ...emptyRate, retryAfter: "3" }, 10_000);
    expect(state.blockedUntilMs).toBe(13_000);
    expect(state.blockReason).toBe("retry_after");
  });

  it("blocks until x-ratelimit-reset on primary exhaustion", () => {
    const state = defaultGitHubApiGuardState();
    updateRateLimitState(state, 403, { ...emptyRate, remaining: 0, reset: 123 }, 10_000);
    expect(state.blockedUntilMs).toBe(123_000);
    expect(state.blockReason).toBe("primary_rate_limit");
  });

  it("uses exponential backoff for ambiguous 403 or 429 responses", () => {
    const state = defaultGitHubApiGuardState();
    updateRateLimitState(state, 403, emptyRate, 10_000);
    expect(state.blockedUntilMs).toBe(10_000 + SECONDARY_BACKOFF_BASE_MS);
    expect(state.secondaryBackoffLevel).toBe(1);

    updateRateLimitState(state, 429, emptyRate, 20_000);
    expect(state.blockedUntilMs).toBe(20_000 + (SECONDARY_BACKOFF_BASE_MS * 2));
    expect(state.secondaryBackoffLevel).toBe(2);
  });

  it("caps exponential backoff", () => {
    const state = defaultGitHubApiGuardState();
    state.secondaryBackoffLevel = 10;
    updateRateLimitState(state, 429, emptyRate, 10_000);
    expect(state.blockedUntilMs).toBe(10_000 + SECONDARY_BACKOFF_MAX_MS);
  });

  it("resets secondary backoff after a successful response", () => {
    const state = defaultGitHubApiGuardState();
    state.secondaryBackoffLevel = 3;
    updateRateLimitState(state, 200, emptyRate, 10_000);
    expect(state.secondaryBackoffLevel).toBe(0);
  });

  it("clears expired blocks and reports active blocks", () => {
    const state = defaultGitHubApiGuardState();
    state.blockedUntilMs = 10_000;
    state.blockReason = "retry_after";
    expect(isBlocked(state, 9_999)).toBe(true);

    clearExpiredBlock(state, 10_000);
    expect(isBlocked(state, 10_000)).toBe(false);
    expect(state.blockedUntilMs).toBe(0);
    expect(state.blockReason).toBe("");
  });
});
