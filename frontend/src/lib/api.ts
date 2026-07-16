/** Typed client for the StreamPulse API (shapes verified in GAP_REPORT.md §1). */

export type ClassifiedRecord = Record<string, unknown> & {
  domain?: string;
  confidence?: number;
  method?: "keyword" | "llm";
  image_category?: string | null;
  image_confidence?: number | null;
};

export type IngestResult = {
  source: string;
  records_in: number;
  records_inserted: number;
  log_id: number;
};

export type HistoryRow = {
  id: number;
  source: string;
  status: string;
  records: number;
  error: string | null;
  payload: string | null;
  created_at: string;
  updated_at: string;
};

export type LiveEvent = {
  event: string; // "ingest"
  source: string;
  records: ClassifiedRecord[];
  receivedAt: number; // added client-side
};

const BASE = import.meta.env.VITE_API_BASE_URL || "";
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

async function req<T>(path: string, init?: RequestInit, retryCount = 0): Promise<T> {
  try {
    const res = await fetch(BASE + path, init);
    if (!res.ok) {
      if (res.status >= 500 && retryCount < 5) {
        await delay(2000 * (retryCount + 1));
        return req<T>(path, init, retryCount + 1);
      }
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch { /* keep statusText */ }
      throw new ApiError(res.status, detail);
    }
    return res.json() as Promise<T>;
  } catch (err: any) {
    if ((err instanceof TypeError || err.message === 'Failed to fetch') && retryCount < 5) {
      await delay(2000 * (retryCount + 1));
      return req<T>(path, init, retryCount + 1);
    }
    throw err;
  }
}

const post = (body: unknown) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => req<{ status: string }>("/health"),
  status: () => req<{ status: string; connected_clients: number }>("/pipeline/status"),
  history: (limit = 100) => req<{ history: HistoryRow[] }>(`/pipeline/history?limit=${limit}`),
  ingestJson: (records: Record<string, unknown>[], source: string) =>
    req<IngestResult>("/ingest/json", post({ records, source })),
  ingestEmail: (payload: Record<string, unknown>) =>
    req<IngestResult>("/ingest/email", post(payload)),
  ingestCsv: (file: File, source: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source", source);
    return req<IngestResult>("/ingest/csv", { method: "POST", body: fd });
  },
  replay: (logId: number) =>
    req<IngestResult>(`/pipeline/replay/${logId}`, { method: "POST" }),
  /** Webhook call with real HMAC-SHA256 signature computed in-browser (WebCrypto).
   *  The secret never leaves the browser except as the signature header. */
  async webhook(source: string, body: string, secret: string, vision = false) {
    const enc = new TextEncoder();
    const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
    const sigBuf = await crypto.subtle.sign("HMAC", key, enc.encode(body));
    const sig = Array.from(new Uint8Array(sigBuf)).map((b) => b.toString(16).padStart(2, "0")).join("");
    return req<IngestResult>(`/webhook/${encodeURIComponent(source)}${vision ? "/with-vision" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Signature-256": `sha256=${sig}` },
      body,
    });
  },
};

/** Live stream helper: WebSocket with keepalive + automatic SSE fallback. */
export function openLive(
  onEvent: (ev: LiveEvent) => void,
  onState: (s: "ws" | "sse" | "connecting" | "down") => void,
): () => void {
  let ws: WebSocket | null = null;
  let es: EventSource | null = null;
  let keepalive: number | undefined;
  let closed = false;

  const startSSE = () => {
    if (closed) return;
    onState("connecting");
    es = new EventSource("/live/sse");
    es.onopen = () => onState("sse");
    es.onerror = () => { es?.close(); onState("down"); };
    // SSE payload is recent history, not per-ingest events — used as a fallback signal only.
  };

  const startWS = () => {
    if (closed) return;
    onState("connecting");
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/live`);
    ws.onopen = () => {
      onState("ws");
      keepalive = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000);
    };
    ws.onmessage = (m) => {
      try {
        const data = JSON.parse(m.data);
        if (data.event === "ingest") onEvent({ ...data, receivedAt: Date.now() });
      } catch { /* ignore non-JSON frames */ }
    };
    ws.onclose = () => {
      window.clearInterval(keepalive);
      if (!closed) startSSE();
    };
    ws.onerror = () => ws?.close();
  };

  startWS();
  return () => {
    closed = true;
    window.clearInterval(keepalive);
    ws?.close();
    es?.close();
  };
}

export function parsePayload(row: HistoryRow): unknown {
  try {
    return row.payload ? JSON.parse(row.payload) : null;
  } catch {
    return row.payload;
  }
}
