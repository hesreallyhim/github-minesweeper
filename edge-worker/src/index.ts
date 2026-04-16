interface Env {
  GITHUB_WEBHOOK_SECRET: string;
  GITHUB_PAT: string;
  MINESWEEPER_SECRET: string;
  GAME_ROWS: string;
  GAME_COLS: string;
  GAME_MINES: string;
}

function json(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
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
    const hasSecret = Boolean(env.GITHUB_WEBHOOK_SECRET?.trim());
    if (!event) {
      return json(400, { error: "missing_event" });
    }
    if (!hasSecret) {
      return json(500, { error: "missing_webhook_secret" });
    }

    return json(501, {
      error: "not_implemented",
      detail: "Webhook verification + gameplay processing not yet wired.",
      event,
    });
  },
};
