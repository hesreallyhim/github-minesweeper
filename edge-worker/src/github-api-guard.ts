import { DurableObject } from "cloudflare:workers";
import {
  calculatePacingWaitMs,
  clearExpiredBlock,
  isBlocked,
  isMutative,
  normalizeGitHubApiGuardState,
  updateRateLimitState,
} from "./github-api-guard-logic";
import type { GitHubApiGuardState, GitHubRateLimitHeaders } from "./github-api-guard-logic";

type GuardEnv = {
  GITHUB_APP_ID: string;
  GITHUB_APP_PRIVATE_KEY: string;
  GITHUB_MODERATION_TOKEN?: string;
};

export type GitHubApiGuardRequest = {
  installationId: number;
  repo: string;
  path: string;
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  contentGenerating?: boolean;
  apiVersion?: string;
};

export type GitHubApiGuardBlockUserRequest = {
  installationId: number;
  username: string;
};

export type GitHubApiGuardResponse = {
  status: number;
  ok: boolean;
  headers: Record<string, string>;
  body: string;
  suppressed?: boolean;
  reason?: string;
  blockedUntilMs?: number;
};

export type GitHubApiGuardBlockUserResponse = {
  blocked: boolean;
  skipped: boolean;
  reason?: string;
  status?: number;
};

type InstallationTokenCacheEntry = {
  token: string;
  expiresAtMs: number;
};

type GitHubApiGuardStoredState = GitHubApiGuardState & {
  token?: InstallationTokenCacheEntry;
};

const TEXT_ENCODER = new TextEncoder();
const APP_JWT_TTL_SECONDS = 9 * 60;
const TOKEN_CACHE_SKEW_MS = 60_000;
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function endpointFamily(path: string): string {
  return path
    .replace(/\/\d+(?=\/|$)/g, "/:number")
    .replace(/\/issues\/:number\/comments\/\d+(?=\/|$)/g, "/issues/:number/comments/:number")
    .replace(/\/user\/blocks\/[^/]+$/g, "/user/blocks/:username");
}

function parseIntegerHeader(headers: Headers, name: string): number | null {
  const raw = headers.get(name);
  if (!raw) return null;
  const parsed = Number.parseInt(raw, 10);
  return Number.isNaN(parsed) ? null : parsed;
}

function readRateLimitHeaders(headers: Headers): GitHubRateLimitHeaders {
  return {
    limit: parseIntegerHeader(headers, "x-ratelimit-limit"),
    remaining: parseIntegerHeader(headers, "x-ratelimit-remaining"),
    used: parseIntegerHeader(headers, "x-ratelimit-used"),
    reset: parseIntegerHeader(headers, "x-ratelimit-reset"),
    resource: headers.get("x-ratelimit-resource") ?? "",
    retryAfter: headers.get("retry-after") ?? "",
  };
}

function headersToRecord(headers: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  headers.forEach((value, key) => {
    out[key] = value;
  });
  return out;
}

function pemToDerBytes(privateKeyPem: string): Uint8Array {
  const normalized = privateKeyPem
    .replace(/-----BEGIN [^-]+-----/g, "")
    .replace(/-----END [^-]+-----/g, "")
    .replace(/\s+/g, "");
  const binary = atob(normalized);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function b64urlEncode(data: Uint8Array): string {
  let binary = "";
  for (const byte of data) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function encodeJwtSegment(value: Record<string, unknown>): string {
  return b64urlEncode(TEXT_ENCODER.encode(JSON.stringify(value)));
}

async function rs256Sign(privateKeyPem: string, message: string): Promise<Uint8Array> {
  const derBytes = pemToDerBytes(privateKeyPem);
  const derBuffer = (new Uint8Array(derBytes)).buffer as ArrayBuffer;
  const key = await crypto.subtle.importKey(
    "pkcs8",
    derBuffer,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, TEXT_ENCODER.encode(message));
  return new Uint8Array(signature);
}

async function createGitHubAppJwt(appId: string, privateKeyPem: string): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const payload = {
    iat: now - 60,
    exp: now + APP_JWT_TTL_SECONDS,
    iss: appId,
  };
  const unsigned = `${encodeJwtSegment(header)}.${encodeJwtSegment(payload)}`;
  const signature = await rs256Sign(privateKeyPem, unsigned);
  return `${unsigned}.${b64urlEncode(signature)}`;
}

function suppressedResponse(state: GitHubApiGuardState): GitHubApiGuardResponse {
  return {
    status: 429,
    ok: false,
    headers: {},
    body: "",
    suppressed: true,
    reason: state.blockReason || "github_api_guard_blocked",
    blockedUntilMs: state.blockedUntilMs,
  };
}

export class GitHubApiGuard extends DurableObject<GuardEnv> {
  private queue: Promise<void> = Promise.resolve();

  async request(input: GitHubApiGuardRequest): Promise<GitHubApiGuardResponse> {
    return this.enqueue(() => this.handleRequest(input));
  }

  async blockUser(input: GitHubApiGuardBlockUserRequest): Promise<GitHubApiGuardBlockUserResponse> {
    return this.enqueue(() => this.handleBlockUser(input));
  }

  private enqueue<T>(fn: () => Promise<T>): Promise<T> {
    const run = this.queue.then(fn, fn);
    this.queue = run.then(() => undefined, () => undefined);
    return run;
  }

  private async loadState(): Promise<GitHubApiGuardStoredState> {
    const raw = (await this.ctx.storage.get<Partial<GitHubApiGuardStoredState>>("state")) ?? {};
    return {
      ...normalizeGitHubApiGuardState(raw),
      token: raw.token,
    };
  }

  private async saveState(state: GitHubApiGuardStoredState): Promise<void> {
    await this.ctx.storage.put("state", state);
  }

  private isBlocked(state: GitHubApiGuardStoredState): boolean {
    return isBlocked(state, Date.now());
  }

  private clearExpiredBlock(state: GitHubApiGuardStoredState): void {
    clearExpiredBlock(state, Date.now());
  }

  private async handleRequest(input: GitHubApiGuardRequest): Promise<GitHubApiGuardResponse> {
    const state = await this.loadState();
    this.clearExpiredBlock(state);
    if (this.isBlocked(state)) {
      await this.saveState(state);
      console.warn("github_api_guard_suppressed", {
        installationId: input.installationId,
        repo: input.repo,
        endpoint: endpointFamily(`/repos/${input.repo}${input.path}`),
        blockedUntilMs: state.blockedUntilMs,
        reason: state.blockReason,
      });
      return suppressedResponse(state);
    }

    try {
      const token = await this.getInstallationToken(state, input.installationId);
      return await this.performFetch(state, {
        installationId: input.installationId,
        repo: input.repo,
        path: `/repos/${input.repo}${input.path}`,
        method: input.method ?? "GET",
        headers: {
          authorization: `Bearer ${token}`,
          ...(input.headers ?? {}),
        },
        body: input.body,
        contentGenerating: Boolean(input.contentGenerating),
        apiVersion: input.apiVersion,
        tokenKind: "installation",
      });
    } finally {
      await this.saveState(state);
    }
  }

  private async handleBlockUser(
    input: GitHubApiGuardBlockUserRequest,
  ): Promise<GitHubApiGuardBlockUserResponse> {
    const state = await this.loadState();
    this.clearExpiredBlock(state);
    const moderationToken = this.env.GITHUB_MODERATION_TOKEN?.trim() ?? "";
    if (!moderationToken) {
      await this.saveState(state);
      return { blocked: false, skipped: true, reason: "missing_moderation_token" };
    }
    if (this.isBlocked(state)) {
      await this.saveState(state);
      console.warn("github_api_guard_block_user_suppressed", {
        installationId: input.installationId,
        username: input.username,
        blockedUntilMs: state.blockedUntilMs,
        reason: state.blockReason,
      });
      return { blocked: false, skipped: true, reason: state.blockReason };
    }

    try {
      const response = await this.performFetch(state, {
        installationId: input.installationId,
        repo: "",
        path: `/user/blocks/${encodeURIComponent(input.username)}`,
        method: "PUT",
        headers: {
          authorization: `Bearer ${moderationToken}`,
        },
        apiVersion: "2026-03-10",
        tokenKind: "moderation",
      });
      return {
        blocked: response.status === 204,
        skipped: false,
        reason: response.status === 204 ? undefined : response.body,
        status: response.status,
      };
    } finally {
      await this.saveState(state);
    }
  }

  private async getInstallationToken(
    state: GitHubApiGuardStoredState,
    installationId: number,
  ): Promise<string> {
    const cached = state.token;
    const now = Date.now();
    if (cached && cached.expiresAtMs - TOKEN_CACHE_SKEW_MS > now) {
      return cached.token;
    }

    const appJwt = await createGitHubAppJwt(this.env.GITHUB_APP_ID, this.env.GITHUB_APP_PRIVATE_KEY);
    const response = await this.performFetch(state, {
      installationId,
      repo: "",
      path: `/app/installations/${installationId}/access_tokens`,
      method: "POST",
      headers: {
        authorization: `Bearer ${appJwt}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({}),
      tokenKind: "app_jwt",
    });
    if (!response.ok) {
      throw new Error(`token_exchange_failed_${response.status}:${response.body}`);
    }
    const payload = JSON.parse(response.body) as Record<string, unknown>;
    const token = typeof payload.token === "string" ? payload.token : "";
    if (!token) {
      throw new Error("token_exchange_missing_token");
    }
    const expiresAtRaw = typeof payload.expires_at === "string" ? payload.expires_at : "";
    const expiresAtMs = Date.parse(expiresAtRaw);
    state.token = {
      token,
      expiresAtMs: Number.isNaN(expiresAtMs) ? now + (50 * 60 * 1000) : expiresAtMs,
    };
    return token;
  }

  private async waitForPacing(
    state: GitHubApiGuardStoredState,
    method: string,
    contentGenerating: boolean,
  ): Promise<void> {
    const waitMs = calculatePacingWaitMs(state, method, contentGenerating, Date.now());
    if (waitMs > 0) {
      await sleep(waitMs);
    }
  }

  private async performFetch(
    state: GitHubApiGuardStoredState,
    input: {
      installationId: number;
      repo: string;
      path: string;
      method: string;
      headers: Record<string, string>;
      body?: string;
      contentGenerating?: boolean;
      apiVersion?: string;
      tokenKind: "app_jwt" | "installation" | "moderation";
    },
  ): Promise<GitHubApiGuardResponse> {
    this.clearExpiredBlock(state);
    if (this.isBlocked(state)) return suppressedResponse(state);

    const method = input.method.toUpperCase();
    const mutative = isMutative(method);
    const contentGenerating = Boolean(input.contentGenerating);
    await this.waitForPacing(state, method, contentGenerating);

    const startMs = Date.now();
    const response = await fetch(`https://api.github.com${input.path}`, {
      method,
      headers: {
        "user-agent": "github-minesweeper-webhook",
        accept: "application/vnd.github+json",
        "x-github-api-version": input.apiVersion ?? "2022-11-28",
        ...input.headers,
      },
      body: input.body,
    });
    const body = await response.text();
    const rate = readRateLimitHeaders(response.headers);
    const durationMs = Date.now() - startMs;
    updateRateLimitState(state, response.status, rate, Date.now());
    if (mutative) state.lastMutativeMs = Date.now();
    if (contentGenerating) state.lastContentGeneratingMs = Date.now();

    console.log("github_api_response", {
      installationId: input.installationId,
      repo: input.repo || null,
      method,
      endpoint: endpointFamily(input.path),
      status: response.status,
      durationMs,
      resource: rate.resource || null,
      limit: rate.limit,
      used: rate.used,
      remaining: rate.remaining,
      reset: rate.reset,
      retryAfter: rate.retryAfter || null,
      mutative,
      contentGenerating,
      tokenKind: input.tokenKind,
      blockedUntilMs: state.blockedUntilMs || null,
      blockReason: state.blockReason || null,
    });

    return {
      status: response.status,
      ok: response.ok,
      headers: headersToRecord(response.headers),
      body,
    };
  }

}

export async function guardedGitHubRequest(
  env: { GITHUB_API_GUARD: DurableObjectNamespace<GitHubApiGuard> },
  input: GitHubApiGuardRequest,
): Promise<GitHubApiGuardResponse> {
  const stub = env.GITHUB_API_GUARD.getByName(String(input.installationId));
  return stub.request(input);
}

export async function guardedBlockGitHubUser(
  env: { GITHUB_API_GUARD: DurableObjectNamespace<GitHubApiGuard> },
  input: GitHubApiGuardBlockUserRequest,
): Promise<GitHubApiGuardBlockUserResponse> {
  const stub = env.GITHUB_API_GUARD.getByName(String(input.installationId));
  return stub.blockUser(input);
}
