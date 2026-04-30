import { DurableObject } from "cloudflare:workers";

export type AbuseGuardEventKind = "owner" | "non_owner";
export type AbuseGuardAction =
  | "process_owner"
  | "suppress_owner"
  | "warn_owner"
  | "lock_room"
  | "ignore_non_owner"
  | "warn_non_owner"
  | "block_non_owner";
export type AbuseGuardRequest = {
  kind: AbuseGuardEventKind;
  repo: string;
  issueNumber: number;
  owner: string;
  sender: string;
};
export type AbuseGuardDecision = {
  action: AbuseGuardAction;
  reason: string;
  sender: string;
  count?: number;
  retryAfterMs?: number;
};

type AbuseOffenderRecord = {
  count: number;
  warned: boolean;
  block_recommended: boolean;
  first_seen_ms: number;
  last_seen_ms: number;
  issues: number[];
};
type OwnerPacingRecord = {
  last_processed_ms: number;
  suppressed_count: number;
  warned: boolean;
  lock_recommended: boolean;
};
type AbuseGuardCounters = {
  non_owner_ignored: number;
  non_owner_warnings: number;
  non_owner_blocks_recommended: number;
  owner_comments_suppressed: number;
  owner_warnings: number;
  owner_locks_recommended: number;
};
type AbuseGuardState = {
  offenders: Record<string, AbuseOffenderRecord>;
  owner_pacing: Record<string, OwnerPacingRecord>;
  counters: AbuseGuardCounters;
};

const ABUSE_WINDOW_MS = 60 * 60 * 1000;
const OWNER_COMMENT_COOLDOWN_MS = 5 * 1000;
const OWNER_WARNING_THRESHOLD = 5;
const OWNER_LOCK_THRESHOLD = 10;
const NON_OWNER_WARNING_THRESHOLD = 5;
const NON_OWNER_BLOCK_THRESHOLD = 10;

function defaultAbuseGuardState(): AbuseGuardState {
  return {
    offenders: {},
    owner_pacing: {},
    counters: {
      non_owner_ignored: 0,
      non_owner_warnings: 0,
      non_owner_blocks_recommended: 0,
      owner_comments_suppressed: 0,
      owner_warnings: 0,
      owner_locks_recommended: 0,
    },
  };
}

function normalizeAbuseGuardState(raw: AbuseGuardState): AbuseGuardState {
  return {
    offenders: raw.offenders ?? {},
    owner_pacing: raw.owner_pacing ?? {},
    counters: {
      non_owner_ignored: raw.counters?.non_owner_ignored ?? 0,
      non_owner_warnings: raw.counters?.non_owner_warnings ?? 0,
      non_owner_blocks_recommended: raw.counters?.non_owner_blocks_recommended ?? 0,
      owner_comments_suppressed: raw.counters?.owner_comments_suppressed ?? 0,
      owner_warnings: raw.counters?.owner_warnings ?? 0,
      owner_locks_recommended: raw.counters?.owner_locks_recommended ?? 0,
    },
  };
}

function normalizeLoginKey(login: string): string {
  return login.trim().toLowerCase();
}

function pruneAbuseGuardState(state: AbuseGuardState, nowMs: number): void {
  for (const [login, record] of Object.entries(state.offenders)) {
    if (nowMs - record.first_seen_ms >= ABUSE_WINDOW_MS) {
      delete state.offenders[login];
    }
  }
  for (const [issueNumber, record] of Object.entries(state.owner_pacing)) {
    if (nowMs - record.last_processed_ms >= ABUSE_WINDOW_MS) {
      delete state.owner_pacing[issueNumber];
    }
  }
}

function addIssueToOffender(record: AbuseOffenderRecord, issueNumber: number): void {
  if (!record.issues.includes(issueNumber)) {
    record.issues.push(issueNumber);
  }
}

export class AbuseGuard extends DurableObject {
  async decide(input: AbuseGuardRequest): Promise<AbuseGuardDecision> {
    const nowMs = Date.now();
    const state = normalizeAbuseGuardState(
      (await this.ctx.storage.get<AbuseGuardState>("state")) ?? defaultAbuseGuardState(),
    );
    pruneAbuseGuardState(state, nowMs);

    const sender = normalizeLoginKey(input.sender);
    if (!sender) {
      return {
        action: input.kind === "owner" ? "suppress_owner" : "ignore_non_owner",
        reason: "missing_sender",
        sender: "",
      };
    }

    const decision = input.kind === "owner"
      ? this.decideOwner(state, input, sender, nowMs)
      : this.decideNonOwner(state, input, sender, nowMs);

    await this.ctx.storage.put("state", state);
    console.log("abuse_guard_decision", {
      repo: input.repo,
      issueNumber: input.issueNumber,
      sender: decision.sender,
      action: decision.action,
      reason: decision.reason,
      count: decision.count ?? null,
      retryAfterMs: decision.retryAfterMs ?? null,
    });
    return decision;
  }

  private decideOwner(
    state: AbuseGuardState,
    input: AbuseGuardRequest,
    sender: string,
    nowMs: number,
  ): AbuseGuardDecision {
    const issueKey = String(input.issueNumber);
    const current = state.owner_pacing[issueKey];
    if (!current || nowMs - current.last_processed_ms >= OWNER_COMMENT_COOLDOWN_MS) {
      state.owner_pacing[issueKey] = {
        last_processed_ms: nowMs,
        suppressed_count: current?.suppressed_count ?? 0,
        warned: current?.warned ?? false,
        lock_recommended: current?.lock_recommended ?? false,
      };
      return {
        action: "process_owner",
        reason: "owner_cooldown_clear",
        sender,
      };
    }

    current.suppressed_count += 1;
    state.counters.owner_comments_suppressed += 1;
    if (current.suppressed_count === OWNER_WARNING_THRESHOLD && !current.warned) {
      current.warned = true;
      state.counters.owner_warnings += 1;
      return {
        action: "warn_owner",
        reason: "owner_warning_threshold",
        sender,
        count: current.suppressed_count,
        retryAfterMs: OWNER_COMMENT_COOLDOWN_MS - (nowMs - current.last_processed_ms),
      };
    }
    if (current.suppressed_count >= OWNER_LOCK_THRESHOLD && !current.lock_recommended) {
      current.lock_recommended = true;
      state.counters.owner_locks_recommended += 1;
      return {
        action: "lock_room",
        reason: "owner_lock_threshold",
        sender,
        count: current.suppressed_count,
        retryAfterMs: OWNER_COMMENT_COOLDOWN_MS - (nowMs - current.last_processed_ms),
      };
    }
    return {
      action: "suppress_owner",
      reason: "owner_cooldown",
      sender,
      count: current.suppressed_count,
      retryAfterMs: OWNER_COMMENT_COOLDOWN_MS - (nowMs - current.last_processed_ms),
    };
  }

  private decideNonOwner(
    state: AbuseGuardState,
    input: AbuseGuardRequest,
    sender: string,
    nowMs: number,
  ): AbuseGuardDecision {
    const existing = state.offenders[sender];
    const record = existing ?? {
      count: 0,
      warned: false,
      block_recommended: false,
      first_seen_ms: nowMs,
      last_seen_ms: nowMs,
      issues: [],
    };
    record.count += 1;
    record.last_seen_ms = nowMs;
    addIssueToOffender(record, input.issueNumber);
    state.offenders[sender] = record;

    if (record.count === NON_OWNER_WARNING_THRESHOLD && !record.warned) {
      record.warned = true;
      state.counters.non_owner_warnings += 1;
      return {
        action: "warn_non_owner",
        reason: "non_owner_warning_threshold",
        sender,
        count: record.count,
      };
    }

    if (record.count >= NON_OWNER_BLOCK_THRESHOLD && !record.block_recommended) {
      record.block_recommended = true;
      state.counters.non_owner_blocks_recommended += 1;
      return {
        action: "block_non_owner",
        reason: "non_owner_block_threshold",
        sender,
        count: record.count,
      };
    }

    state.counters.non_owner_ignored += 1;
    return {
      action: "ignore_non_owner",
      reason: "non_owner_below_threshold",
      sender,
      count: record.count,
    };
  }
}

export async function decideAbuseGuard(
  env: { ABUSE_GUARD: DurableObjectNamespace<AbuseGuard> },
  input: AbuseGuardRequest,
): Promise<AbuseGuardDecision> {
  const stub = env.ABUSE_GUARD.getByName(input.repo.toLowerCase());
  return stub.decide(input);
}
