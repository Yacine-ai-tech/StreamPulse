import { useState } from "react";
import { Terminal, Copy, Check, Code2, Globe, Shield, Zap, BookOpen } from "lucide-react";

const BASE_URL = "https://gateway.ysiddo-ai-projects.app/streampulse";

type Snippets = { curl: string; python: string; node: string };

interface Endpoint {
  method: "GET" | "POST" | "WS";
  path: string;
  category: "General" | "Ingestion" | "Webhooks" | "Pipeline" | "Live Streaming";
  auth: string;
  desc: string;
  note?: string;
  headers?: { name: string; required: boolean; desc: string }[];
  query?: { name: string; desc: string }[];
  bodyLabel?: string;
  body?: string | null;
  response: string;
  snippets: Snippets;
}

const CATEGORIES: Endpoint["category"][] = ["General", "Ingestion", "Webhooks", "Pipeline", "Live Streaming"];

const ENDPOINTS: Endpoint[] = [
  {
    method: "GET",
    path: "/",
    category: "General",
    auth: "Public",
    desc: "Serves the StreamPulse dashboard SPA. Excluded from the OpenAPI schema (docs at /docs).",
    note: "Falls back to {\"service\":\"streampulse\",\"docs\":\"/docs\"} if frontend/dist/index.html hasn't been built into the backend image.",
    body: null,
    response: `{"service": "streampulse", "docs": "/docs"}`,
    snippets: {
      curl: `curl "${BASE_URL}/"`,
      python: `import requests\n\nresp = requests.get("${BASE_URL}/")\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/");\nconsole.log(await res.json());`,
    },
  },
  {
    method: "GET",
    path: "/health",
    category: "General",
    auth: "Public",
    desc: "Liveness + database connectivity check.",
    note: "The DB ping is cached for up to 10s (not re-checked on every call). status is \"degraded\" (HTTP 200, not 503) if the cached check last failed.",
    body: null,
    response: `{
  "status": "ok",
  "service": "streampulse",
  "version": "0.1.0",
  "database": "ok"
}`,
    snippets: {
      curl: `curl "${BASE_URL}/health"`,
      python: `import requests\n\nresp = requests.get("${BASE_URL}/health")\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/health");\nconsole.log(await res.json());`,
    },
  },
  {
    method: "POST",
    path: "/ingest/json",
    category: "Ingestion",
    auth: "Optional X-Demo-Session-Id",
    desc: "Ingest a batch of arbitrary JSON records. Shared entry point: /ingest/csv, /ingest/email and both webhook routes all normalize into this same call.",
    note: "Each record is run through the 3-tier classifier (domain + confidence + method fields are appended), stored, broadcast to every connected /live client, and — if EXTERNAL_WEBHOOK_URL is configured — forwarded downstream (e.g. to IntelAI) as a fire-and-forget task.",
    headers: [
      { name: "X-Demo-Session-Id", required: false, desc: "Browser/demo visitor id. Omit for real integrations — data stays globally visible by design (see Pipeline notes)." },
    ],
    bodyLabel: "application/json",
    body: `{
  "records": [
    {"metric": "revenue", "value": 128000, "period": "2026-Q3"}
  ],
  "source": "manual_json"
}`,
    response: `{
  "source": "manual_json",
  "records_in": 1,
  "records_inserted": 1,
  "log_id": 42
}`,
    snippets: {
      curl: `curl -X POST "${BASE_URL}/ingest/json" \\\n  -H "Content-Type: application/json" \\\n  -d '{"records":[{"metric":"revenue","value":128000,"period":"2026-Q3"}],"source":"manual_json"}'`,
      python: `import requests\n\nresp = requests.post(\n    "${BASE_URL}/ingest/json",\n    json={\n        "records": [{"metric": "revenue", "value": 128000, "period": "2026-Q3"}],\n        "source": "manual_json",\n    },\n)\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/ingest/json", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({\n    records: [{ metric: "revenue", value: 128000, period: "2026-Q3" }],\n    source: "manual_json",\n  }),\n});\nconsole.log(await res.json());`,
    },
  },
  {
    method: "POST",
    path: "/ingest/csv",
    category: "Ingestion",
    auth: "Optional X-Demo-Session-Id",
    desc: "Upload a CSV file; each row becomes one record. Column headers are used as record keys (metric, value, period, category, ... — anything matching IngestJsonRequest fields is picked up).",
    note: "Parsed rows are handed to the same handler as /ingest/json, so the response shape (and classification/broadcast/forwarding behavior) is identical.",
    headers: [
      { name: "X-Demo-Session-Id", required: false, desc: "Same as /ingest/json." },
    ],
    bodyLabel: "multipart/form-data",
    body: `file:   <binary CSV>\nsource: csv_upload   # optional form field, this is the default`,
    response: `{
  "source": "csv_upload",
  "records_in": 25,
  "records_inserted": 25,
  "log_id": 43
}`,
    snippets: {
      curl: `curl -X POST "${BASE_URL}/ingest/csv" \\\n  -F "file=@metrics.csv" \\\n  -F "source=csv_upload"`,
      python: `import requests\n\nwith open("metrics.csv", "rb") as f:\n    resp = requests.post(\n        "${BASE_URL}/ingest/csv",\n        files={"file": f},\n        data={"source": "csv_upload"},\n    )\nprint(resp.json())`,
      node: `const form = new FormData();\nform.append("file", fileBlob, "metrics.csv");\nform.append("source", "csv_upload");\nconst res = await fetch("${BASE_URL}/ingest/csv", { method: "POST", body: form });\nconsole.log(await res.json());`,
    },
  },
  {
    method: "POST",
    path: "/ingest/email",
    category: "Ingestion",
    auth: "Optional X-Demo-Session-Id",
    desc: "Accept a Gmail-style JSON payload (subject/from/body) and treat it as a single record.",
    note: "Wraps the payload as {\"source\":\"email\",\"raw\":payload,\"metric\":payload.subject} and reuses /ingest/json — same response shape, source is always \"email\".",
    headers: [
      { name: "X-Demo-Session-Id", required: false, desc: "Same as /ingest/json." },
    ],
    bodyLabel: "application/json",
    body: `{
  "subject": "Q3 revenue update",
  "from": "cfo@example.com",
  "body": "We closed Q3 at 128k in revenue, up 12% QoQ."
}`,
    response: `{
  "source": "email",
  "records_in": 1,
  "records_inserted": 1,
  "log_id": 44
}`,
    snippets: {
      curl: `curl -X POST "${BASE_URL}/ingest/email" \\\n  -H "Content-Type: application/json" \\\n  -d '{"subject":"Q3 revenue update","from":"cfo@example.com","body":"We closed Q3 at 128k in revenue."}'`,
      python: `import requests\n\nresp = requests.post(\n    "${BASE_URL}/ingest/email",\n    json={\n        "subject": "Q3 revenue update",\n        "from": "cfo@example.com",\n        "body": "We closed Q3 at 128k in revenue.",\n    },\n)\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/ingest/email", {\n  method: "POST",\n  headers: { "Content-Type": "application/json" },\n  body: JSON.stringify({ subject: "Q3 revenue update", from: "cfo@example.com", body: "..." }),\n});\nconsole.log(await res.json());`,
    },
  },
  {
    method: "POST",
    path: "/webhook/{source_name}",
    category: "Webhooks",
    auth: "HMAC-SHA256 (X-Signature-256)",
    desc: "Generic signed webhook receiver. {source_name} is a free-form label (e.g. github, clickup, n8n) recorded as the record's source.",
    note: "No X-Demo-Session-Id is read here on purpose: real external webhook callers (n8n, CRMs, GitHub, etc.) aren't browsers, so their data always stays globally visible — that's the point of a public ingestion demo.",
    headers: [
      { name: "X-Signature-256", required: true, desc: "sha256=<hex HMAC-SHA256 of the raw request body, keyed with WEBHOOK_SECRET>. Missing or mismatched signature returns 401 {\"detail\":\"invalid_signature\"}." },
    ],
    bodyLabel: "application/json",
    body: `# Accepted shapes, in order:
#   {"records": [ {...}, ... ]}
#   [ {...}, ... ]
#   { ...single record... }
# Non-KPI fields (title/body/action/subject/text) are auto-derived into metric/value/category
{"text": "New high-value invoice received", "value": 15400, "category": "Finance"}`,
    response: `{
  "source": "github",
  "records_in": 1,
  "records_inserted": 1,
  "log_id": 45
}`,
    snippets: {
      curl: `BODY='{"text":"New high-value invoice received","value":15400,"category":"Finance"}'\nSIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')\ncurl -X POST "${BASE_URL}/webhook/github" \\\n  -H "Content-Type: application/json" \\\n  -H "X-Signature-256: sha256=$SIG" \\\n  -d "$BODY"`,
      python: `import hmac, hashlib, json, requests\n\nbody = json.dumps({"text": "New high-value invoice received", "value": 15400, "category": "Finance"}).encode()\nsig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()\n\nresp = requests.post(\n    "${BASE_URL}/webhook/github",\n    data=body,\n    headers={"Content-Type": "application/json", "X-Signature-256": f"sha256={sig}"},\n)\nprint(resp.json())`,
      node: `import crypto from "crypto";\n\nconst body = JSON.stringify({ text: "New high-value invoice received", value: 15400, category: "Finance" });\nconst sig = crypto.createHmac("sha256", process.env.WEBHOOK_SECRET).update(body).digest("hex");\n\nconst res = await fetch("${BASE_URL}/webhook/github", {\n  method: "POST",\n  headers: { "Content-Type": "application/json", "X-Signature-256": \`sha256=\${sig}\` },\n  body,\n});\nconsole.log(await res.json());`,
    },
  },
  {
    method: "POST",
    path: "/webhook/{source_name}/with-vision",
    category: "Webhooks",
    auth: "HMAC-SHA256 (X-Signature-256)",
    desc: "Same signed ingestion as /webhook/{source_name}, plus vision enrichment: any record whose raw payload carries an image_url is composed with DocIntel's /classify-image before storage.",
    note: "For each parsed record with raw.image_url set, the image is downloaded and POSTed to {DOCINTEL_URL}/classify-image (categories: tractor, lathe, crane, forklift, excavator, other); the returned category/confidence are merged in as image_category / image_confidence. Vision enrichment is best-effort — a failed DocIntel call is logged and the record still ingests without the image fields. A malformed payload overall returns 400 {\"detail\":\"invalid_payload\"}.",
    headers: [
      { name: "X-Signature-256", required: true, desc: "Same HMAC-SHA256 scheme as /webhook/{source_name}." },
    ],
    bodyLabel: "application/json",
    body: `{
  "records": [
    {"text": "Equipment photo attached", "image_url": "https://example.com/forklift.jpg"}
  ]
}`,
    response: `{
  "source": "auction_aggregator",
  "records_in": 1,
  "records_inserted": 1,
  "log_id": 46
}
// stored record additionally carries:
// "image_category": "forklift", "image_confidence": 0.94`,
    snippets: {
      curl: `BODY='{"records":[{"text":"Equipment photo attached","image_url":"https://example.com/forklift.jpg"}]}'\nSIG=$(echo -n "$BODY" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* //')\ncurl -X POST "${BASE_URL}/webhook/auction_aggregator/with-vision" \\\n  -H "Content-Type: application/json" \\\n  -H "X-Signature-256: sha256=$SIG" \\\n  -d "$BODY"`,
      python: `import hmac, hashlib, json, requests\n\npayload = {"records": [{"text": "Equipment photo attached", "image_url": "https://example.com/forklift.jpg"}]}\nbody = json.dumps(payload).encode()\nsig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()\n\nresp = requests.post(\n    "${BASE_URL}/webhook/auction_aggregator/with-vision",\n    data=body,\n    headers={"Content-Type": "application/json", "X-Signature-256": f"sha256={sig}"},\n)\nprint(resp.json())`,
      node: `import crypto from "crypto";\n\nconst body = JSON.stringify({ records: [{ text: "Equipment photo attached", image_url: "https://example.com/forklift.jpg" }] });\nconst sig = crypto.createHmac("sha256", process.env.WEBHOOK_SECRET).update(body).digest("hex");\n\nconst res = await fetch("${BASE_URL}/webhook/auction_aggregator/with-vision", {\n  method: "POST",\n  headers: { "Content-Type": "application/json", "X-Signature-256": \`sha256=\${sig}\` },\n  body,\n});\nconsole.log(await res.json());`,
    },
  },
  {
    method: "GET",
    path: "/pipeline/status",
    category: "Pipeline",
    auth: "Public",
    desc: "Live counters for the pipeline: connected WebSocket clients plus aggregate stats read straight from the store.",
    body: null,
    response: `{
  "status": "ok",
  "connected_clients": 3,
  "ingestion_events": 128,
  "failed_events": 2,
  "records_stored": 540,
  "distinct_sources": 6,
  "backend": "postgres"
}`,
    snippets: {
      curl: `curl "${BASE_URL}/pipeline/status"`,
      python: `import requests\n\nresp = requests.get("${BASE_URL}/pipeline/status")\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/pipeline/status");\nconsole.log(await res.json());`,
    },
  },
  {
    method: "POST",
    path: "/pipeline/replay/{log_id}",
    category: "Pipeline",
    auth: "Optional X-Demo-Session-Id",
    desc: "Re-ingest the stored payload of a past ingestion event — a real replay, not a simulation: it re-runs the original records through classification and storage as a new event.",
    note: "Ownership is enforced: a log_id that belongs to a different visitor's session 404s instead of replaying their stored payload. Returns 422 {\"detail\":\"no_stored_payload\"} if the original event has no records to replay.",
    headers: [
      { name: "X-Demo-Session-Id", required: false, desc: "Must match the session that created log_id, if that event was session-scoped." },
    ],
    body: null,
    response: `{
  "source": "replay:manual_json",
  "records_in": 1,
  "records_inserted": 1,
  "log_id": 47
}`,
    snippets: {
      curl: `curl -X POST "${BASE_URL}/pipeline/replay/42"`,
      python: `import requests\n\nresp = requests.post("${BASE_URL}/pipeline/replay/42")\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/pipeline/replay/42", { method: "POST" });\nconsole.log(await res.json());`,
    },
  },
  {
    method: "GET",
    path: "/pipeline/history",
    category: "Pipeline",
    auth: "Optional X-Demo-Session-Id",
    desc: "Recent ingestion events (most recent first), including the truncated stored payload each one can be replayed from.",
    note: "Implementation note (recent fix): when DEMO_SESSION_SCOPING is enabled (default), results are scoped to rows with owner_session_id IS NULL (real webhooks/n8n/CRM sources — always globally visible) OR owner_session_id matching the caller's X-Demo-Session-Id. A demo visitor no longer sees every other visitor's test events.",
    query: [{ name: "limit", desc: "Max rows to return. Default 100." }],
    headers: [
      { name: "X-Demo-Session-Id", required: false, desc: "Scopes results to this visitor's own events (plus session-less/global events)." },
    ],
    body: null,
    response: `{
  "history": [
    {
      "id": 47, "source": "manual_json", "status": "completed",
      "records": 1, "error": null, "owner_session_id": null,
      "created_at": "2026-08-09T10:00:00Z", "updated_at": "2026-08-09T10:00:00Z"
    }
  ]
}`,
    snippets: {
      curl: `curl "${BASE_URL}/pipeline/history?limit=20"`,
      python: `import requests\n\nresp = requests.get("${BASE_URL}/pipeline/history", params={"limit": 20})\nprint(resp.json())`,
      node: `const res = await fetch("${BASE_URL}/pipeline/history?limit=20");\nconsole.log(await res.json());`,
    },
  },
  {
    method: "WS",
    path: "/live",
    category: "Live Streaming",
    auth: "Public",
    desc: "WebSocket feed of every ingest event as it's broadcast — the primary channel behind the Live Operations dashboard.",
    note: "The server sends {\"event\":\"ingest\",\"source\":...,\"records\":[...]} for each completed ingestion, and a {\"type\":\"ping\",\"timestamp\":...} keepalive every 30s of client silence. When MESSAGE_BROKER=redis or kafka is configured, broadcasts are also published on that broker so multiple StreamPulse instances stay in sync — otherwise broadcast is local-process only.",
    body: null,
    response: `{"event": "ingest", "source": "manual_json", "records": [{"metric": "revenue", "value": 128000, "domain": "Finance", "confidence": 0.8, "method": "keyword"}]}`,
    snippets: {
      curl: `# curl doesn't speak WebSocket; use websocat or a WS client library\nwebsocat "wss://gateway.ysiddo-ai-projects.app/streampulse/live"`,
      python: `import asyncio, websockets, json\n\nasync def main():\n    async with websockets.connect("wss://gateway.ysiddo-ai-projects.app/streampulse/live") as ws:\n        async for msg in ws:\n            print(json.loads(msg))\n\nasyncio.run(main())`,
      node: `const ws = new WebSocket("wss://gateway.ysiddo-ai-projects.app/streampulse/live");\nws.onmessage = (e) => console.log(JSON.parse(e.data));`,
    },
  },
  {
    method: "GET",
    path: "/live/sse",
    category: "Live Streaming",
    auth: "Optional X-Demo-Session-Id or ?session_id=",
    desc: "Server-Sent Events fallback for clients that can't use WebSocket — pushes the 5 most recent pipeline history rows every 5 seconds.",
    note: "Browsers' native EventSource can't set custom headers, so this endpoint also accepts the demo session id as a ?session_id= query param; the X-Demo-Session-Id header still wins if a client sends both.",
    query: [{ name: "session_id", desc: "Same role as X-Demo-Session-Id, for EventSource clients." }],
    headers: [
      { name: "X-Demo-Session-Id", required: false, desc: "Takes priority over ?session_id= when both are present." },
    ],
    body: null,
    response: `data: [{"id": 47, "source": "manual_json", "status": "completed", "records": 1, ...}]\n\n(repeats every 5s while the connection is open)`,
    snippets: {
      curl: `curl -N "${BASE_URL}/live/sse?session_id=demo-123"`,
      python: `import requests\n\nwith requests.get("${BASE_URL}/live/sse", params={"session_id": "demo-123"}, stream=True) as r:\n    for line in r.iter_lines():\n        if line:\n            print(line.decode())`,
      node: `const es = new EventSource("${BASE_URL}/live/sse?session_id=demo-123");\nes.onmessage = (e) => console.log(JSON.parse(e.data));`,
    },
  },
];

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
      style={{ background: "none", border: "none", cursor: "pointer", color: copied ? "#4ade80" : "#94a3b8", padding: "4px" }}
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div style={{ position: "relative", background: "rgba(0,0,0,0.4)", borderRadius: 8, padding: "14px 40px 14px 14px", fontFamily: "monospace", fontSize: "0.78rem", color: "#e2e8f0", whiteSpace: "pre-wrap", wordBreak: "break-word", lineHeight: 1.6 }}>
      <div style={{ position: "absolute", top: 8, right: 8 }}><CopyBtn text={code} /></div>
      {code}
    </div>
  );
}

function methodColor(method: Endpoint["method"]) {
  if (method === "GET") return "#38bdf8";
  if (method === "WS") return "#2dd4bf";
  return "#a78bfa";
}

export default function ApiDocs() {
  const [lang, setLang] = useState<keyof Snippets>("curl");
  const [active, setActive] = useState(0);
  const ep = ENDPOINTS[active];

  return (
    <div style={{ padding: "24px 32px", maxWidth: 1180, color: "#e2e8f0" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <Terminal size={28} color="#f59e0b" />
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: 700, margin: 0 }}>StreamPulse API Reference</h1>
          <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>
            Ingest, classify, and stream real-time business data from any source — 12 endpoints across ingestion, signed webhooks, pipeline control, and live streaming.
          </p>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", gap: 12, margin: "20px 0" }}>
        {[
          { icon: Globe, label: "Base URL", value: BASE_URL, color: "#38bdf8" },
          { icon: Shield, label: "Webhook auth", value: "HMAC-SHA256 (X-Signature-256)", color: "#4ade80" },
          { icon: Zap, label: "Transport", value: "REST + WebSocket + SSE", color: "#f59e0b" },
          { icon: BookOpen, label: "Endpoints", value: "12", color: "#a78bfa" },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 10, padding: "12px 16px", display: "flex", gap: 10, alignItems: "center" }}>
            <Icon size={18} color={color} />
            <div>
              <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
              <div style={{ fontSize: "0.8rem", fontWeight: 600, wordBreak: "break-all" }}>{value}</div>
            </div>
          </div>
        ))}
      </div>

      <p style={{ fontSize: "0.78rem", color: "#64748b", margin: "0 0 20px", lineHeight: 1.6 }}>
        Note: if the deployment sets <code>REQUIRE_INTERNAL_TOKEN=true</code> (off by default), every route except <code>/</code>, <code>/health</code>,{" "}
        <code>/docs</code>, <code>/openapi.json</code>, <code>/api/redoc</code>, and static assets additionally requires an{" "}
        <code>X-OmniIntel-Internal-Token</code> header. This is a service-mesh concern for internal callers — it's independent of the per-webhook
        HMAC signing below.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "270px 1fr", gap: 20 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {CATEGORIES.map((cat) => (
            <div key={cat}>
              <div style={{ fontSize: "0.7rem", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 6 }}>{cat}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {ENDPOINTS.map((e, i) => e.category === cat && (
                  <button
                    key={i}
                    onClick={() => setActive(i)}
                    style={{
                      textAlign: "left",
                      background: active === i ? "rgba(124,58,237,0.15)" : "rgba(255,255,255,0.03)",
                      border: active === i ? "1px solid rgba(124,58,237,0.4)" : "1px solid rgba(255,255,255,0.07)",
                      borderRadius: 8,
                      padding: "10px 14px",
                      cursor: "pointer",
                    }}
                  >
                    <span style={{ fontSize: "0.68rem", fontWeight: 700, fontFamily: "monospace", background: `${methodColor(e.method)}26`, color: methodColor(e.method), borderRadius: 4, padding: "2px 6px", marginRight: 8 }}>{e.method}</span>
                    <span style={{ fontSize: "0.78rem", fontFamily: "monospace", color: active === i ? "#e2e8f0" : "#94a3b8" }}>{e.path}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "16px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
              <span style={{ fontSize: "0.75rem", fontWeight: 700, fontFamily: "monospace", background: `${methodColor(ep.method)}26`, color: methodColor(ep.method), borderRadius: 5, padding: "3px 8px" }}>{ep.method}</span>
              <code style={{ fontSize: "0.9rem" }}>{ep.method === "WS" ? "wss://" + BASE_URL.replace(/^https?:\/\//, "") + ep.path : BASE_URL + ep.path}</code>
              <span style={{ fontSize: "0.68rem", color: "#64748b", marginLeft: "auto" }}>{ep.auth}</span>
            </div>
            <p style={{ margin: 0, fontSize: "0.85rem", color: "#94a3b8" }}>{ep.desc}</p>
            {ep.note && <p style={{ margin: "10px 0 0", fontSize: "0.78rem", color: "#64748b", lineHeight: 1.6, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 10 }}>{ep.note}</p>}
            {(ep.headers?.length || ep.query?.length) ? (
              <div style={{ marginTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                {ep.headers?.map((h) => (
                  <div key={h.name} style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                    <code style={{ color: "#4ade80" }}>{h.name}</code>{h.required ? " (required)" : " (optional)"} — {h.desc}
                  </div>
                ))}
                {ep.query?.map((q) => (
                  <div key={q.name} style={{ fontSize: "0.75rem", color: "#94a3b8" }}>
                    <code style={{ color: "#38bdf8" }}>?{q.name}</code> — {q.desc}
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          {ep.body && (
            <div>
              <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
                <Code2 size={13} /> Request body{ep.bodyLabel ? ` (${ep.bodyLabel})` : ""}
              </div>
              <CodeBlock code={ep.body} />
            </div>
          )}

          <div>
            <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
              <span style={{ fontSize: "0.75rem", color: "#64748b", marginRight: 4 }}>Language:</span>
              {(["curl", "python", "node"] as (keyof Snippets)[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLang(l)}
                  style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid", borderColor: lang === l ? "#7c3aed" : "rgba(255,255,255,0.1)", background: lang === l ? "rgba(124,58,237,0.2)" : "transparent", color: lang === l ? "#c4b5fd" : "#94a3b8", cursor: "pointer", fontSize: "0.78rem", fontWeight: 600 }}
                >
                  {l}
                </button>
              ))}
            </div>
            <CodeBlock code={ep.snippets[lang]} />
          </div>

          <div>
            <div style={{ fontSize: "0.75rem", color: "#64748b", marginBottom: 6, display: "flex", alignItems: "center", gap: 6 }}>
              <Check size={13} color="#4ade80" /> Sample response
            </div>
            <CodeBlock code={ep.response} />
          </div>
        </div>
      </div>

      <div style={{ marginTop: 32, display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(360px,1fr))", gap: 20 }}>
        <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "18px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Zap size={16} color="#f59e0b" />
            <h2 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0 }}>How classification works (3 tiers)</h2>
          </div>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: 1.7, margin: "0 0 10px" }}>
            Every record passed to any ingestion or webhook route above runs through <code>pipeline/classifier.py</code>'s hybrid classifier before storage:
          </p>
          <ol style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: 1.8, margin: 0, paddingLeft: 18 }}>
            <li><strong style={{ color: "#e2e8f0" }}>Tier 1 — Keyword matching.</strong> Scores text against per-domain keyword lists (Finance, Growth, Operations, People, ESG, IT_Ops). Returns immediately if confidence ≥ 0.5. <code>method: "keyword"</code>.</li>
            <li><strong style={{ color: "#e2e8f0" }}>Tier 2 — Vector embeddings.</strong> Gated by <code>STREAMPULSE_HYBRID_LLM=1</code>. Embeds the text (BAAI/bge-large-en-v1.5 by default) and cosine-matches it against 6 domain prototype sentences. Returns if similarity ≥ 0.5. <code>method: "vector_embedding"</code>.</li>
            <li><strong style={{ color: "#e2e8f0" }}>Tier 3 — LLM zero-shot escalation.</strong> Also gated by <code>STREAMPULSE_HYBRID_LLM=1</code>. Asks the configured LLM (<code>LLM_JUDGE</code>, Claude Haiku by default; falls back to Gemini Flash if only <code>GEMINI_API_KEY</code> is set) to pick one of the 6 labels. <code>method: "llm"</code>.</li>
          </ol>
          <p style={{ fontSize: "0.75rem", color: "#64748b", lineHeight: 1.6, margin: "10px 0 0" }}>
            Every stored record carries its <code>domain</code>, <code>confidence</code>, and <code>method</code> — the decision path is always visible, not just the final label. See the User Guide for measured accuracy per tier.
          </p>
        </div>

        <div style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, padding: "18px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
            <Shield size={16} color="#4ade80" />
            <h2 style={{ fontSize: "0.95rem", fontWeight: 700, margin: 0 }}>n8n integration</h2>
          </div>
          <p style={{ fontSize: "0.8rem", color: "#94a3b8", lineHeight: 1.7, margin: "0 0 10px" }}>
            <code>connectors/n8n/</code> ships 5 ready-to-import workflow templates plus a custom "StreamPulse Ingest" node that pushes records with a correctly-computed <code>X-Signature-256</code> HMAC header:
          </p>
          <ul style={{ fontSize: "0.78rem", color: "#94a3b8", lineHeight: 1.8, margin: 0, paddingLeft: 18 }}>
            <li><code>auction_aggregator</code> — Google Drive file trigger → parse CSV/Excel → signed HMAC push.</li>
            <li><code>invoice_intake</code> — Gmail attachment → DocIntel OCR → ClickUp alert on high-value invoices → StreamPulse ingest.</li>
            <li><code>crm_sync</code> — hourly ClickUp task pull → StreamPulse ingest → Google Sheets audit log.</li>
            <li><code>uptime_alert</code> — scheduled uptime check → filters down services → email alert.</li>
            <li><code>master_trigger</code> — scheduled harness that exercises the other 3 workflows and verifies StreamPulse health.</li>
          </ul>
          <p style={{ fontSize: "0.75rem", color: "#64748b", lineHeight: 1.6, margin: "10px 0 0" }}>
            Templates are imported manually in n8n (Workflows → Import from File); the backend also attempts a best-effort <code>auto_provision()</code> call in a background thread on startup (errors are logged, never block startup).
          </p>
        </div>
      </div>
    </div>
  );
}
