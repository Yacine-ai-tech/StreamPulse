import React from 'react';
import {
  BookOpen, Radio, Split, Webhook, Image, RotateCcw, Workflow,
  ShieldCheck, Terminal, CheckCircle2, AlertTriangle, Database, Activity,
} from 'lucide-react';

export default function UserGuidePage() {
  return (
    <div className="p-8 max-w-5xl mx-auto h-full overflow-y-auto">
      <div className="flex items-center gap-3 mb-8">
        <BookOpen className="w-10 h-10 text-blue-500" />
        <h1 className="text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-600">
          StreamPulse User Guide
        </h1>
      </div>

      <p className="text-lg text-gray-300 mb-8 leading-relaxed">
        StreamPulse is a real-time, multi-source data pipeline: JSON, CSV, email, and signed webhook payloads are
        ingested, run through a 3-tier domain classifier, persisted, and pushed live to the dashboard over WebSocket
        (with an SSE fallback) — with no manual tagging required.
      </p>

      <div className="space-y-8 text-gray-200">

        {/* What it is / how data flows */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Radio className="w-6 h-6 text-green-400" /> How Data Flows Through StreamPulse
          </h2>
          <div className="space-y-4">
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-blue-400 text-lg mb-2">1. Ingest</h3>
              <p className="text-sm text-gray-300">
                Records arrive via <code>POST /ingest/json</code> (raw JSON), <code>POST /ingest/csv</code> (file
                upload, one record per row), <code>POST /ingest/email</code> (Gmail-style payload treated as a
                single record), or a signed <code>POST /webhook/{'{source_name}'}</code> call. All four funnel
                through the same underlying handler, so every source gets identical classification, storage, and
                broadcast behavior.
              </p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-purple-400 text-lg mb-2">2. Classify</h3>
              <p className="text-sm text-gray-300">
                Each record is run through the hybrid domain classifier (see below) before it's stored — every row
                ends up tagged with a <code>domain</code>, <code>confidence</code>, and the <code>method</code> tier
                that produced it.
              </p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-amber-400 text-lg mb-2">3. Store &amp; broadcast</h3>
              <p className="text-sm text-gray-300">
                The classified record is persisted (Postgres in production, SQLite locally), broadcast to every
                connected <code>/live</code> WebSocket client, and — if <code>EXTERNAL_WEBHOOK_URL</code> is
                configured — forwarded downstream to another system (e.g. IntelAI) as a fire-and-forget call.
              </p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-cyan-400 text-lg mb-2">4. Watch it live</h3>
              <p className="text-sm text-gray-300">
                The dashboard (and any external client) can subscribe to <code>WS /live</code> for push updates, or
                fall back to <code>GET /live/sse</code> (polls the last 5 history rows every 5 seconds) when a
                WebSocket connection isn't available.
              </p>
            </div>
          </div>
        </section>

        {/* Classifier */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Split className="w-6 h-6 text-purple-400" /> The 3-Tier Hybrid Classifier
          </h2>
          <p className="text-sm text-gray-300 mb-4">
            Defined in <code>pipeline/classifier.py</code>, the classifier escalates through up to three tiers per
            record, stopping as soon as one is confident enough:
          </p>
          <ol className="space-y-3 text-sm text-gray-300 list-decimal list-inside mb-4">
            <li><span className="font-semibold text-gray-100">Tier 1 — Keyword matching.</span> Scores text against per-domain keyword lists across 6 domains (Finance, Growth, Operations, People, ESG, IT_Ops). Returns immediately once confidence ≥ 0.5. Free, near-instant.</li>
            <li><span className="font-semibold text-gray-100">Tier 2 — Vector embeddings.</span> Opt-in via <code>STREAMPULSE_HYBRID_LLM=1</code>. Embeds the text (BAAI/bge-m3 by default) and compares it against 6 domain prototype sentences by cosine similarity.</li>
            <li><span className="font-semibold text-gray-100">Tier 3 — LLM zero-shot escalation.</span> Also gated by <code>STREAMPULSE_HYBRID_LLM=1</code>. Asks the configured LLM (Claude Haiku by default, via <code>LLM_JUDGE</code>) to pick one of the 6 labels when the earlier tiers aren't confident.</li>
          </ol>

          <h3 className="font-semibold text-lg text-gray-100 mb-2">Measured accuracy (real benchmark)</h3>
          <p className="text-sm text-gray-300 mb-3">
            <code>eval/CLASSIFIER_BENCHMARK.md</code> reports a real run (2026-06-17) against{' '}
            <code>eval/domain_labeled.jsonl</code> — 24 hand-written examples across the 6 domains, deliberately{' '}
            <span className="italic">paraphrased to avoid the literal domain keywords</span> (e.g. "we brought in
            more money and kept more of it after bills" instead of "revenue/profit"), so the benchmark measures what
            each tier adds rather than rewarding a self-aligned keyword list:
          </p>
          <div className="overflow-x-auto mb-3">
            <table className="w-full text-sm text-left border border-gray-700 rounded-lg overflow-hidden">
              <thead className="bg-gray-900 text-gray-400">
                <tr>
                  <th className="p-3 font-medium">Tier</th>
                  <th className="p-3 font-medium">Accuracy</th>
                  <th className="p-3 font-medium">Macro-F1</th>
                </tr>
              </thead>
              <tbody className="bg-gray-900/40">
                <tr className="border-t border-gray-700">
                  <td className="p-3">Keyword only (Tier 1)</td>
                  <td className="p-3 font-mono text-amber-300">8.3%</td>
                  <td className="p-3 font-mono text-gray-400">0.105</td>
                </tr>
                <tr className="border-t border-gray-700">
                  <td className="p-3">Keyword → Vector embedding (Tier 2)</td>
                  <td className="p-3 font-mono text-amber-300">20.8%</td>
                  <td className="p-3 font-mono text-gray-400">0.253</td>
                </tr>
                <tr className="border-t border-gray-700">
                  <td className="p-3">Keyword → Embedding → LLM escalation (Tier 3)</td>
                  <td className="p-3 font-mono text-green-400">100.0%</td>
                  <td className="p-3 font-mono text-green-400">1.000</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-sm text-gray-300 mb-2">
            <span className="font-semibold text-gray-100">Headline:</span> on realistic keyword-poor text, plain
            keyword matching collapses to 8.3% while the full hybrid pipeline recovers it to 100.0% — the measured
            justification for paying for the LLM tier at all.
          </p>
          <p className="text-xs text-gray-400 leading-relaxed">
            <span className="font-semibold">Honest caveat (from the benchmark doc itself):</span> real streams are a
            mix of keyword-rich and keyword-poor text, so keyword-only would score well above 8.3% in production,
            and the LLM tier is opt-in and costs per call. The 24-example set is small and curated — treat 100.0% as
            "clearly separable on a small clean set," not a production guarantee. The embedding tier's 20.8% reflects
            real calls to a remote inference host and is sensitive to that host's availability at request time.
            Reproduce with{' '}
            <code>python eval/run_classifier_benchmark.py</code> and{' '}
            <code>STREAMPULSE_HYBRID_LLM=1 python eval/run_classifier_benchmark.py</code>.
          </p>
        </section>

        {/* HMAC webhooks */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Webhook className="w-6 h-6 text-orange-400" /> Signing Webhooks (HMAC-SHA256)
          </h2>
          <p className="text-sm text-gray-300 mb-3">
            <code>POST /webhook/{'{source_name}'}</code> and its vision variant both require a valid signature.{' '}
            <code>connectors/webhook_receiver.py</code> verifies it like this:
          </p>
          <ul className="list-disc list-inside text-sm text-gray-300 space-y-2 mb-4">
            <li>Compute <code>HMAC-SHA256(raw_request_body, key=WEBHOOK_SECRET)</code> as a hex digest.</li>
            <li>Send it in the <code>X-Signature-256</code> header, prefixed <code>sha256=</code> (e.g. <code>sha256=3f9a...</code>).</li>
            <li>The signature is verified with a constant-time comparison (<code>hmac.compare_digest</code>) against the <span className="italic">raw bytes</span> of the body — sign the exact bytes you send, before any client-side re-serialization.</li>
            <li>A missing or mismatched signature returns <code>401 {'{"detail":"invalid_signature"}'}</code>; malformed JSON returns <code>400 {'{"detail":"invalid_json"}'}</code>.</li>
          </ul>
          <p className="text-sm text-gray-300 mb-3">
            Real webhook callers (n8n, GitHub, a CRM) intentionally never send an <code>X-Demo-Session-Id</code>{' '}
            header — their data stays globally visible in the pipeline by design, since that header only exists to
            isolate anonymous demo visitors from each other (see below).
          </p>
          <div className="bg-gray-950 border border-gray-800 rounded-lg p-4 flex items-start gap-3">
            <Activity className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
            <p className="text-xs text-gray-300 leading-relaxed">
              <span className="font-semibold text-gray-100">Measured under load</span> (<code>eval/WEBHOOK_BENCHMARK.md</code>,{' '}
              <code>eval/THROUGHPUT_BENCHMARK.md</code>): 100/100 correctly-signed requests accepted and 10/10
              invalid signatures rejected across 100 concurrent requests; a separate 1,000-request stress test
              (2026-07-28, Postgres with connection pooling) measured 847 req/s peak throughput, 23ms average / 89ms
              P95 response time, 0.12% error rate, and 100% rejection of invalid signatures under load.
            </p>
          </div>
        </section>

        {/* Vision enrichment */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Image className="w-6 h-6 text-pink-400" /> Vision-Enriched Webhooks
          </h2>
          <p className="text-sm text-gray-300 mb-3">
            <code>POST /webhook/{'{source_name}'}/with-vision</code> accepts the same signed payload as the
            standard webhook route, but composes StreamPulse with DocIntel: for every parsed record whose raw
            payload carries an <code>image_url</code>, the image is downloaded and posted to{' '}
            <code>{'{DOCINTEL_URL}'}/classify-image</code> with a fixed category set (tractor, lathe, crane,
            forklift, excavator, other). The returned category and confidence are merged into the record as{' '}
            <code>image_category</code> and <code>image_confidence</code> before storage.
          </p>
          <p className="text-sm text-gray-300">
            Vision enrichment is best-effort: if the DocIntel call fails, the failure is logged and the record still
            ingests normally, just without the image fields. A malformed payload overall returns{' '}
            <code>400 {'{"detail":"invalid_payload"}'}</code>. The <code>auction_aggregator</code> n8n workflow (see
            below) is one real producer of this kind of image-bearing record.
          </p>
        </section>

        {/* Replay */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <RotateCcw className="w-6 h-6 text-cyan-400" /> Replaying a Past Event
          </h2>
          <p className="text-sm text-gray-300 mb-3">
            Every ingestion is logged with its (truncated) original payload. <code>POST /pipeline/replay/{'{log_id}'}</code>{' '}
            looks that payload up and re-ingests it as a brand-new event — a real replay through the full
            classify-store-broadcast pipeline, not a canned simulation. It returns <code>404</code> if the event
            doesn't exist (or isn't visible to the caller) and <code>422</code> if the original event had no stored
            payload to replay.
          </p>
          <p className="text-sm text-gray-300">
            Find a <code>log_id</code> to replay via <code>GET /pipeline/history</code>, which lists recent events
            newest-first.
          </p>
        </section>

        {/* Session scoping */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <ShieldCheck className="w-6 h-6 text-emerald-400" /> Demo Isolation Between Visitors
          </h2>
          <p className="text-sm text-gray-300 mb-3">
            <span className="font-semibold text-gray-100">Recent fix:</span> <code>GET /pipeline/history</code>,{' '}
            <code>GET /live/sse</code>, and <code>POST /pipeline/replay/{'{log_id}'}</code> now scope their results
            to the caller's own <code>X-Demo-Session-Id</code> — a browser-generated id the frontend sends with its
            own test traffic — plus any session-less data. Previously a demo visitor could see (and replay) every
            other visitor's test events by guessing a sequential <code>log_id</code>; ownership is now enforced in{' '}
            <code>store.py</code>.
          </p>
          <p className="text-sm text-gray-300">
            This is anonymous demo isolation, not production auth: real external webhooks, n8n workflows, and CRM
            sources never send <code>X-Demo-Session-Id</code>, so their data is always stored session-less and
            stays globally visible — that's the intended behavior of a public ingestion demo. Because browsers'
            native <code>EventSource</code> can't set custom headers, <code>/live/sse</code> also accepts the same
            id via a <code>?session_id=</code> query parameter (the header wins if both are present).
          </p>
        </section>

        {/* n8n */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Workflow className="w-6 h-6 text-violet-400" /> n8n Workflow Templates
          </h2>
          <p className="text-sm text-gray-300 mb-4">
            <code>connectors/n8n/</code> ships 5 importable workflow templates (Workflows → Import from File in
            n8n) plus a custom "StreamPulse Ingest" node (<code>n8n_node.json</code>) that computes the HMAC
            signature for you:
          </p>
          <div className="space-y-3">
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-gray-100 text-sm mb-1">auction_aggregator</h3>
              <p className="text-xs text-gray-400">Google Drive Trigger → Download File → Parse CSV/Excel → signed HMAC push to StreamPulse. Demonstrates file-based bulk ingestion.</p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-gray-100 text-sm mb-1">invoice_intake</h3>
              <p className="text-xs text-gray-400">Gmail Trigger → DocIntel Vision OCR → "Is High Value? (&gt;10k)" branch → ClickUp Alert → StreamPulse Ingest. Demonstrates cross-project composition (Gmail → DocIntel → StreamPulse → ClickUp).</p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-gray-100 text-sm mb-1">crm_sync</h3>
              <p className="text-xs text-gray-400">Hourly Trigger → Fetch ClickUp Tasks → StreamPulse Ingest → Google Sheets Audit Log. Demonstrates scheduled CRM polling with an external audit trail.</p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-gray-100 text-sm mb-1">uptime_alert</h3>
              <p className="text-xs text-gray-400">Schedule Trigger → Check KV Uptime Status → Filter DOWN Services → Send Alert Email. Demonstrates alerting on IT_Ops-domain data outside StreamPulse itself.</p>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-700">
              <h3 className="font-semibold text-gray-100 text-sm mb-1">master_trigger</h3>
              <p className="text-xs text-gray-400">Scheduled harness that triggers the auction_aggregator, invoice_intake, and crm_sync workflows and verifies StreamPulse's health — a smoke test for the other 3 templates.</p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-4">
            The backend also attempts a best-effort <code>n8n.auto_provision()</code> call in a background thread on
            startup; failures are logged and never block the API from starting — importing the templates manually is
            the reliable path today.
          </p>
        </section>

        {/* Env / setup */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Terminal className="w-6 h-6 text-blue-400" /> Local Setup
          </h2>
          <p className="text-sm text-gray-300 mb-3">
            Copy <code>.env.example</code> to <code>.env</code> and fill in real values. Key variables (see{' '}
            <code>core/config.py</code> and <code>.env.example</code> for the full list):
          </p>
          <ul className="list-disc list-inside text-sm font-mono text-green-300 space-y-2 ml-2 bg-gray-950 p-4 rounded-lg mb-3">
            <li>WEBHOOK_SECRET <span className="text-gray-500 font-sans">— HMAC key for /webhook/*</span></li>
            <li>POSTGRES_URL <span className="text-gray-500 font-sans">— defaults to local SQLite if unset</span></li>
            <li>MESSAGE_BROKER / REDIS_URL / KAFKA_BROKER_URL <span className="text-gray-500 font-sans">— optional multi-instance WS broadcast</span></li>
            <li>STREAMPULSE_HYBRID_LLM <span className="text-gray-500 font-sans">— set to 1 to enable classifier Tiers 2 &amp; 3</span></li>
            <li>DOCINTEL_URL <span className="text-gray-500 font-sans">— required for the vision webhook variant</span></li>
            <li>N8N_BASE_URL / N8N_API_KEY <span className="text-gray-500 font-sans">— for the n8n integration</span></li>
          </ul>
          <p className="text-sm text-gray-300">
            Start the backend with <code>uvicorn api:app</code> (or <code>docker-compose -f docker-compose.dev.yml up</code>),
            then run the frontend from <code>frontend/</code> with <code>npm run dev</code>.
          </p>
        </section>

        {/* Best practices */}
        <section className="bg-gray-800/50 backdrop-blur-md p-8 rounded-xl border border-gray-700 shadow-2xl">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2 text-white">
            <Database className="w-6 h-6 text-red-400" /> Security &amp; Best Practices
          </h2>
          <ul className="space-y-3">
            <li className="flex items-start gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">Never commit <code>.env</code> or hardcode <code>WEBHOOK_SECRET</code> — every credential is read from the environment.</span>
            </li>
            <li className="flex items-start gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">Sign the exact raw bytes you send to <code>/webhook/*</code> — re-serializing JSON client-side before signing (different key order, whitespace) will produce a signature that fails verification.</span>
            </li>
            <li className="flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <span className="text-sm text-gray-300">The LLM classifier tier (Tier 3) costs a real API call per escalated record — keep <code>STREAMPULSE_HYBRID_LLM</code> off in cost-sensitive environments unless the accuracy gap above matters for your data.</span>
            </li>
          </ul>
        </section>

      </div>
    </div>
  );
}
