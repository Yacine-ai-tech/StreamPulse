"""
Real-Time Data Pipeline — Live ingestion from email, sheets, webhooks, APIs.

Integrates with all domain services (Finance, HR, Operations, Logistics, IT, ESG)
to provide streaming data updates with automatic routing, transformation, and storage.

FEATURES:
- Multi-source data ingestion (Gmail, Sheets, N8N, Webhooks, APIs)
- Auto-classification to domains (Finance, HR, Operations, etc.)
- Real-time validation & transformation
- Duplicate detection & merging
- Anomaly detection & alerts
- Audit trail & change tracking
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

import os

from core.config import settings
from core.logger import get_logger
from store import (
    log_data_ingestion,
    update_ingestion_log,
    store_kpi_metrics,
)

# Optional: the full-platform connector dispatcher (Gmail/Sheets). StreamPulse runs standalone
# without it — the pipeline guards on `self.dispatcher` being None, so this stays importable.
try:
    from integrations import IntegrationTypeEnum, get_dispatcher  # type: ignore
except ImportError:
    IntegrationTypeEnum = None  # type: ignore
    get_dispatcher = None  # type: ignore

log = get_logger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# TIER 2 EMBEDDER (lazy-loaded sentence-transformers model, cached by name)
# ════════════════════════════════════════════════════════════════════════════

_embedder_cache: Dict[str, Any] = {}

# Multiple, diversely-phrased prototypes per domain instead of one -- a single short
# prototype sentence is a noisy target for cosine similarity against real (often
# keyword-poor, paraphrased) input text. Matching against several phrasings per domain
# and taking the best (max-pooled) similarity is the standard fix for prototype-based
# zero-shot classification. Includes "Growth" as its own domain -- it was previously
# missing from this tier entirely (silently replaced by "General"), so any genuinely
# Growth-related content could never be correctly classified by this tier no matter how
# good the embeddings were. Shared by classify() and eval/calibrate_embedding_threshold.py
# so the benchmark measures the exact same matching logic production uses.
DOMAIN_PROTOTYPES: Dict[str, List[str]] = {
    "Finance": [
        "finance revenue profit margin cash flow ebitda",
        "quarterly earnings, expenses, and profitability",
        "we brought in more money and kept more of it after costs",
        "balance sheet, income statement, and financial reporting",
        "budget planning and cost control",
        "money coming in and going out of the business",
    ],
    "Operations": [
        "operations supply chain inventory logistics throughput",
        "manufacturing efficiency and production capacity",
        "goods moving through the warehouse and delivery network",
        "process quality, defects, and cycle time",
        "procurement and vendor management",
        "how smoothly the day to day work gets done",
    ],
    "Growth": [
        "growth marketing customer acquisition retention churn",
        "new customer signups and expanding into new markets",
        "how many people are trying the product and sticking with it",
        "marketing campaigns, conversion rates, and word of mouth",
        "recurring revenue and account expansion",
        "winning new business and keeping existing customers longer",
    ],
    "People": [
        "hr people employee turnover hiring retention",
        "staff engagement, training, and workforce planning",
        "hiring new team members and people leaving the company",
        "compensation, benefits, and employee satisfaction",
        "how happy and how long people stay working here",
        "recruiting talent and building the team",
    ],
    "ESG": [
        "esg sustainability carbon diversity governance",
        "environmental impact and emissions reduction",
        "corporate responsibility and board oversight",
        "workplace safety and community impact",
        "how the company treats the planet and its people fairly",
        "diversity, ethics, and long-term stewardship",
    ],
    "IT_Ops": [
        "it uptime latency incident deployment devops",
        "system reliability and infrastructure performance",
        "software releases, outages, and technical incidents",
        "cybersecurity and data protection",
        "keeping the servers and systems running smoothly",
        "engineering velocity and platform stability",
    ],
    # "General" has two jobs: catch genuine corporate/business content that doesn't
    # fit the other five domains, AND catch content that isn't business-related at
    # all. Prototypes limited to "corporate news" phrasing lose that second job --
    # cosine similarity between short embeddings and unrelated text sits in a
    # nontrivial baseline band regardless of true relevance, so a narrowly-scoped
    # General can be out-competed by another domain's vaguest prototype on totally
    # off-topic input (e.g. "the weather is nice today" beating out to Operations'
    # "how smoothly the day to day work gets done"). Mixing in genuinely unrelated,
    # everyday phrasing gives General a fighting chance at winning that contest too.
    "General": [
        "general company update news announcement",
        "corporate communications and press releases",
        "leadership changes and strategic announcements",
        "company culture and internal news",
        "miscellaneous business update not tied to one department",
        "broad organizational news",
        "the weather, sports, or something unrelated to work",
        "a personal message with nothing to do with the business",
        "small talk or a topic that has nothing to do with any department",
    ],
}

_PROTO_DOMAINS = list(DOMAIN_PROTOTYPES.keys())
_FLAT_PROTOTYPES: List[str] = []
_PROTO_DOMAIN_IDX: List[int] = []
for _d_idx, _d in enumerate(_PROTO_DOMAINS):
    for _p in DOMAIN_PROTOTYPES[_d]:
        _FLAT_PROTOTYPES.append(_p)
        _PROTO_DOMAIN_IDX.append(_d_idx)


def _dot_product(v1, v2):
    return sum(x * y for x, y in zip(v1, v2))


def _magnitude(v):
    return sum(x * x for x in v) ** 0.5


def embedding_domain_match(content: str) -> Optional[Tuple[str, float, List[float]]]:
    """Embed `content` and score it against every domain's prototypes, returning
    (best_domain, best_similarity, content_embedding) -- max-pooled per domain across
    that domain's prototype phrasings. The raw content embedding is returned too so
    callers can persist it (e.g. the pgvector cache) without a second embed call.
    Returns None if the remote embedding call didn't succeed. Does NOT apply
    CLASSIFIER_EMBEDDING_THRESHOLD -- callers decide what to do with the raw score
    (classify() thresholds it; the calibration script sweeps it)."""
    inputs = [content[:500]] + _FLAT_PROTOTYPES
    embeddings = _embed(inputs, model=settings.STREAMPULSE_EMBED_MODEL)
    if not embeddings or len(embeddings) != len(inputs):
        return None

    content_emb = embeddings[0]
    proto_embs = embeddings[1:]
    c_mag = _magnitude(content_emb)

    best_per_domain = [-1.0] * len(_PROTO_DOMAINS)
    for p_emb, d_idx in zip(proto_embs, _PROTO_DOMAIN_IDX):
        p_mag = _magnitude(p_emb)
        if c_mag > 0 and p_mag > 0:
            score = _dot_product(content_emb, p_emb) / (c_mag * p_mag)
            if score > best_per_domain[d_idx]:
                best_per_domain[d_idx] = score

    best_score = -1.0
    best_domain = "General"
    for d_idx, score in enumerate(best_per_domain):
        if score > best_score:
            best_score = score
            best_domain = _PROTO_DOMAINS[d_idx]
    return best_domain, best_score, content_emb

# Remote embedding host is a shared, modest-capacity inference box: it sleeps when
# idle (a cold wake can take 60-120s) and can degrade under concurrent load from
# other callers. A single short-timeout attempt can't tell "cold" apart from "down",
# so the first attempt gets a generous budget and later attempts back off instead of
# hammering a host that may still be waking up.
_EMBED_TIMEOUTS = (60.0, 15.0)  # seconds, one per attempt
_EMBED_BACKOFF_SECONDS = 2.0    # doubled between attempts


def _is_valid_embedding(vec: Any) -> bool:
    """Reject degenerate responses (wrong dimensionality, all-zero/near-constant
    vectors) that would otherwise look like a successful call but aren't a genuine
    BGE-M3 encoding — e.g. a misconfigured host silently returning a placeholder."""
    if not isinstance(vec, (list, tuple)) or len(vec) != 1024:
        return False
    try:
        floats = [float(x) for x in vec]
    except (TypeError, ValueError):
        return False
    mean = sum(floats) / len(floats)
    variance = sum((x - mean) ** 2 for x in floats) / len(floats)
    return variance > 1e-8


def _embed(inputs: List[str], model: str) -> List[List[float]]:
    """Encode `inputs` with a local sentence-transformers model (BGE by default).
    The model is loaded once per name and reused across calls.
    If INFERENCE_MODE is remote, calls the configured remote embedding host instead,
    retrying with backoff to ride out cold starts / transient contention on that
    shared host before giving up."""

    if settings.INFERENCE_MODE == "remote":
        url = settings.EMBEDDING_ENDPOINT
        if url:
            import httpx
            import numpy as np
            h = {"Content-Type": "application/json", "User-Agent": "StreamPulse/1.0"}
            if settings.INFERENCE_TOKEN:
                h["Authorization"] = "Bearer " + settings.INFERENCE_TOKEN

            for attempt, timeout in enumerate(_EMBED_TIMEOUTS):
                try:
                    with httpx.Client(timeout=timeout) as client:
                        if "huggingface.co" in url:
                            resp = client.post(url, json={"inputs": inputs}, headers=h)
                            resp.raise_for_status()

                            data = resp.json()
                            # Simple feature extraction might return 3D arrays
                            arr = np.asarray(data, dtype=float)
                            if arr.ndim == 3:
                                arr = arr.mean(axis=1)
                            result = arr.tolist()
                        else:
                            payload = {"texts": inputs, "model": model}
                            resp = client.post(url.rstrip("/") + "/embed", json=payload, headers=h)
                            resp.raise_for_status()
                            result = resp.json()["embeddings"]

                    if result and all(_is_valid_embedding(v) for v in result):
                        return result
                    log.warning(
                        "Remote embedding attempt %d/%d returned a suspicious result "
                        "(wrong shape or near-zero variance) -- treating as a failure",
                        attempt + 1, len(_EMBED_TIMEOUTS),
                    )
                except Exception as e:
                    log.warning(
                        "Remote embedding attempt %d/%d failed: %s",
                        attempt + 1, len(_EMBED_TIMEOUTS), e,
                    )

                if attempt < len(_EMBED_TIMEOUTS) - 1:
                    time.sleep(_EMBED_BACKOFF_SECONDS * (2 ** attempt))

            # Every attempt failed or returned a degenerate result.
            # Do not fall back to local if it fails, to prevent OOM in memory-constrained environments.
            # Just return an empty list or let it fail over.
            return []

    from sentence_transformers import SentenceTransformer

    embedder = _embedder_cache.get(model)
    if embedder is None:
        embedder = SentenceTransformer(model)
        _embedder_cache[model] = embedder
    return embedder.encode(inputs).tolist()

# ════════════════════════════════════════════════════════════════════════════
# CLASSIFICATION CACHE (Content Hash Caching)
# ════════════════════════════════════════════════════════════════════════════

_classification_cache: Dict[str, Dict[str, Any]] = {}
_cache_hits = 0
_cache_misses = 0

def _content_hash(content: str) -> str:
    """Generate SHA-256 hash of content for caching."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def _get_cached_classification(content: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached classification if available."""
    if not settings.CLASSIFIER_ENABLE_CACHE:
        return None
    
    content_hash = _content_hash(content)
    if content_hash in _classification_cache:
        global _cache_hits
        _cache_hits += 1
        return _classification_cache[content_hash]
    return None

def _cache_classification(content: str, result: Dict[str, Any]) -> None:
    """Cache classification result."""
    if not settings.CLASSIFIER_ENABLE_CACHE:
        return
    
    content_hash = _content_hash(content)
    _classification_cache[content_hash] = result
    global _cache_misses
    _cache_misses += 1

def get_cache_stats() -> Dict[str, Any]:
    """Get cache performance statistics."""
    total = _cache_hits + _cache_misses
    hit_rate = _cache_hits / total if total > 0 else 0.0
    return {
        "cache_hits": _cache_hits,
        "cache_misses": _cache_misses,
        "hit_rate": round(hit_rate, 3),
        "cache_size": len(_classification_cache)
    }

# ════════════════════════════════════════════════════════════════════════════
# DOMAIN ROUTING & CLASSIFICATION
# ════════════════════════════════════════════════════════════════════════════

DOMAIN_PATTERNS = {
    "Finance": {
        "keywords": [
            "revenue", "expense", "profit", "margin", "cash", "ebitda",
            "balance sheet", "p&l", "financial", "accounting", "budget",
            "forecast", "financial statement", "invoice", "receipt"
        ],
        "metrics": ["revenue", "gross_profit", "ebitda", "cash_flow", "debt_to_equity"],
    },
    "Operations": {
        "keywords": [
            "efficiency", "cycle", "throughput", "capacity", "downtime",
            "production", "process", "quality", "defect", "waste",
            "supply chain", "logistics", "procurement"
        ],
        "metrics": ["efficiency", "capacity_utilization", "quality_rate", "cycle_time"],
    },
    "Growth": {
        "keywords": [
            "revenue", "mrr", "arr", "churn", "nps", "cac", "ltv",
            "customer", "acquisition", "retention", "growth", "market"
        ],
        "metrics": ["mrr", "arr", "churn_rate", "nps", "cac", "ltv"],
    },
    "People": {
        "keywords": [
            "headcount", "turnover", "engagement", "salary", "training",
            "recruitment", "retention", "diversity", "hr", "employee",
            "workforce", "talent"
        ],
        "metrics": ["headcount", "turnover_rate", "engagement_score", "retention"],
    },
    "ESG": {
        "keywords": [
            "carbon", "emissions", "sustainability", "diversity", "safety",
            "esg", "environmental", "social", "governance", "green",
            "renewable", "safety incidents", "board diversity"
        ],
        "metrics": ["carbon_intensity", "diversity_index", "safety_incidents"],
    },
    "IT_Ops": {
        "keywords": [
            "uptime", "availability", "incident", "ticket", "infrastructure",
            "server", "deployment", "security", "vulnerability", "sla",
            "devops", "cloud", "ci/cd"
        ],
        "metrics": ["uptime", "ticket_resolution_time", "incident_count"],
    },
}


@dataclass
class DataRecord:
    """Standardized data record for ingestion pipeline."""
    source: str  # gmail, sheets, webhook, api, etc.
    domain: str  # Finance, HR, Operations, etc.
    metric_name: str  # revenue, headcount, etc.
    metric_value: float
    timestamp: str
    metadata: Dict[str, Any]
    user_id: Optional[str] = None
    confidence: float = 0.95

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "domain": self.domain,
            "metric": self.metric_name,
            "value": self.metric_value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "confidence": self.confidence,
        }


class DomainClassifier:
    """Classify data to appropriate domain based on content analysis."""

    @staticmethod
    def classify(text: str, hints: Optional[Dict[str, Any]] = None) -> Tuple[str, float]:
        """
        Classify text to domain with confidence score.

        Returns: (domain, confidence)
        """
        text_lower = text.lower()
        scores = {}

        for domain, patterns in DOMAIN_PATTERNS.items():
            score = 0
            keywords = patterns["keywords"]

            # Count keyword matches
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1

            # Boost score if hints match
            if hints and hints.get("domain") == domain:
                score += 5

            if hints and hints.get("metrics"):
                for metric in hints["metrics"]:
                    if metric in text_lower:
                        score += 2

            scores[domain] = score

        if not scores or max(scores.values()) == 0:
            return "General", 0.3

        best_domain = max(scores, key=scores.get)
        confidence = min(0.99, scores[best_domain] / 10)

        return best_domain, confidence

    @staticmethod
    def infer_metric(text: str, domain: str) -> Optional[str]:
        """Infer metric name from text."""
        text_lower = text.lower()
        domain_metrics = DOMAIN_PATTERNS.get(domain, {}).get("metrics", [])

        for metric in domain_metrics:
            if metric.replace("_", " ") in text_lower or metric in text_lower:
                return metric

        return None


# ════════════════════════════════════════════════════════════════════════════
# DATA VALIDATION & TRANSFORMATION
# ════════════════════════════════════════════════════════════════════════════

class DataValidator:
    """Validate and transform ingested data."""

    @staticmethod
    def validate_numeric(value: Any) -> Tuple[bool, Optional[float]]:
        """Validate and convert to numeric value."""
        try:
            if isinstance(value, (int, float)):
                return True, float(value)
            elif isinstance(value, str):
                # Remove currency symbols, commas, percentages
                cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
                num = float(cleaned)
                return True, num
            else:
                return False, None
        except (ValueError, TypeError):
            return False, None

    @staticmethod
    def validate_timestamp(value: Any) -> Tuple[bool, Optional[str]]:
        """Validate and standardize timestamp."""
        try:
            if isinstance(value, str):
                # Try common formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return True, dt.isoformat()
                    except ValueError:
                        continue
            elif isinstance(value, datetime):
                return True, value.isoformat()

            return False, None
        except Exception:
            return False, None

    @staticmethod
    def deduplicate(records: List[DataRecord]) -> List[DataRecord]:
        """Remove duplicate records (same domain + metric + timestamp)."""
        seen = set()
        unique = []

        for record in records:
            key = (record.domain, record.metric_name, record.timestamp)
            if key not in seen:
                seen.add(key)
                unique.append(record)

        return unique

    @staticmethod
    def detect_anomalies(records: List[DataRecord]) -> List[Tuple[DataRecord, float]]:
        """Detect potential anomalies using statistical methods."""
        if len(records) < 3:
            return []

        anomalies = []
        df = pd.DataFrame([r.to_dict() for r in records])

        for domain in df["domain"].unique():
            domain_data = df[df["domain"] == domain]
            for metric in domain_data["metric"].unique():
                metric_data = domain_data[domain_data["metric"] == metric]
                if len(metric_data) < 3:
                    continue

                values = metric_data["value"].values
                mean = values.mean()
                std = values.std() or 0.1
                last_value = values[-1]

                z_score = abs((last_value - mean) / std)
                if z_score > 3:  # 3-sigma rule
                    anomaly_score = min(1.0, z_score / 5)
                    anomalies.append((records[-1], anomaly_score))

        return anomalies


# ════════════════════════════════════════════════════════════════════════════
# REAL-TIME PIPELINE
# ════════════════════════════════════════════════════════════════════════════

class RealtimePipeline:
    """Main real-time data ingestion pipeline."""

    def __init__(self):
        self.classifier = DomainClassifier()
        self.validator = DataValidator()
        self.dispatcher = None
        self.event_handlers: List[Callable] = []
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processing = False
        self.processed_count = 0
        self.error_count = 0

    async def initialize(self) -> None:
        """Initialize pipeline and integrations."""
        try:
            self.dispatcher = await get_dispatcher()
            log.info("RealtimePipeline initialized with dispatcher")
        except Exception as e:
            log.error("Failed to initialize pipeline: %s", e)

    async def ingest_from_email(self, user_email: str) -> int:
        """Ingest data from Gmail."""
        if not self.dispatcher:
            return 0

        gmail = self.dispatcher.get_integration(IntegrationTypeEnum.GMAIL)
        if not gmail or not gmail.active:
            return 0

        try:
            emails = await gmail.fetch_emails(user_email, max_results=10)
            records_processed = 0

            for email in emails:
                # Extract data from email body
                text = email.get("body", "")
                domain, confidence = self.classifier.classify(text)
                metric_name = self.classifier.infer_metric(text, domain)

                if metric_name and confidence > 0.5:
                    record = DataRecord(
                        source="gmail",
                        domain=domain,
                        metric_name=metric_name,
                        metric_value=0.0,  # Would extract from email
                        timestamp=datetime.utcnow().isoformat(),
                        metadata={"email_subject": email.get("subject")},
                        user_id=user_email,
                        confidence=confidence,
                    )
                    await self.process_record(record)
                    records_processed += 1

            return records_processed
        except Exception as e:
            log.error("Gmail ingestion error: %s", e)
            return 0

    async def ingest_from_sheets(self, sheet_id: str, range_name: str = "Sheet1!A1:Z1000") -> int:
        """Ingest data from Google Sheets."""
        if not self.dispatcher:
            return 0

        sheets = self.dispatcher.get_integration(IntegrationTypeEnum.SHEETS)
        if not sheets or not sheets.active:
            return 0

        try:
            data = await sheets.read_sheet(sheet_id, range_name)
            records_processed = 0

            if data:
                df = pd.DataFrame(data[1:], columns=data[0])

                for _, row in df.iterrows():
                    # Assume columns: metric, value, domain (or infer)
                    metric_name = row.get("metric", row.get("name"))
                    metric_value, is_valid = self.validator.validate_numeric(row.get("value"))

                    if not is_valid or not metric_name:
                        continue

                    domain = row.get("domain") or self.classifier.classify(str(metric_name))[0]

                    record = DataRecord(
                        source="sheets",
                        domain=domain,
                        metric_name=str(metric_name),
                        metric_value=metric_value,
                        timestamp=self.validator.validate_timestamp(row.get("date", datetime.utcnow()))[1] or datetime.utcnow().isoformat(),
                        metadata={"sheet_id": sheet_id},
                        confidence=0.9,
                    )
                    await self.process_record(record)
                    records_processed += 1

            return records_processed
        except Exception as e:
            log.error("Sheets ingestion error: %s", e)
            return 0

    async def ingest_from_webhook(self, payload: Dict[str, Any]) -> int:
        """Ingest data from webhook (N8N, custom)."""
        try:
            # Expect payload with: metric, value, domain, timestamp
            metric_name = payload.get("metric") or payload.get("name")
            metric_value, is_valid = self.validator.validate_numeric(payload.get("value"))

            if not is_valid or not metric_name:
                return 0

            domain = payload.get("domain") or self.classifier.classify(str(metric_name))[0]
            timestamp, is_valid = self.validator.validate_timestamp(payload.get("timestamp", datetime.utcnow()))

            if not is_valid:
                timestamp = datetime.utcnow().isoformat()

            record = DataRecord(
                source="webhook",
                domain=domain,
                metric_name=str(metric_name),
                metric_value=metric_value,
                timestamp=timestamp,
                metadata=payload.get("metadata", {}),
                user_id=payload.get("user_id"),
                confidence=payload.get("confidence", 0.95),
            )
            await self.process_record(record)
            return 1
        except Exception as e:
            log.error("Webhook ingestion error: %s", e)
            self.error_count += 1
            return 0

    async def process_record(self, record: DataRecord) -> None:
        """Process a single data record."""
        try:
            # Validate numeric value
            if not isinstance(record.metric_value, (int, float)):
                return

            # Log ingestion
            ingestion_id = log_data_ingestion(
                username=record.user_id or "system",
                filename=f"{record.domain}_{record.metric_name}",
                file_type="streaming",
                source=record.source,
                row_count=1,
            )

            # Store KPI metric
            kpi_df = pd.DataFrame([{
                "metric": record.metric_name,
                "category": record.domain,
                "value": record.metric_value,
                "period": record.timestamp,
                "confidence": record.confidence,
            }])
            store_kpi_metrics(kpi_df)

            # Update ingestion log
            update_ingestion_log(
                ingestion_id=ingestion_id,
                status="completed",
                row_count=1,
                ingested_at=datetime.utcnow(),
            )

            self.processed_count += 1

            # Call event handlers
            for handler in self.event_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(record)
                    else:
                        handler(record)
                except Exception as e:
                    log.error("Event handler error: %s", e)

        except Exception as e:
            log.error("Record processing error: %s", e)
            self.error_count += 1

    def register_handler(self, handler: Callable) -> None:
        """Register a handler to be called when data is ingested."""
        self.event_handlers.append(handler)

    async def process_queue(self) -> None:
        """Background task to process queued records."""
        self.processing = True
        while self.processing:
            try:
                record = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                await self.process_record(record)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                log.error("Queue processing error: %s", e)

    async def shutdown(self) -> None:
        """Shutdown pipeline."""
        self.processing = False
        log.info("RealtimePipeline shut down (processed=%d, errors=%d)", self.processed_count, self.error_count)

    def get_status(self) -> Dict[str, Any]:
        """Get pipeline status."""
        return {
            "initialized": self.dispatcher is not None,
            "processing": self.processing,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "queue_size": self.queue.qsize(),
        }


# ════════════════════════════════════════════════════════════════════════════
# SINGLETON PIPELINE
# ════════════════════════════════════════════════════════════════════════════

_pipeline: Optional[RealtimePipeline] = None


async def get_realtime_pipeline() -> RealtimePipeline:
    """Get or create singleton pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RealtimePipeline()
        await _pipeline.initialize()
    return _pipeline


def classify(content: str, fast_only: bool = False) -> Dict[str, Any]:
    """Hybrid domain classifier: fast keyword pass, vector embedding fallback, and LLM escalation.
    Tier 1: Fast Keyword matching (uses CLASSIFIER_KEYWORD_THRESHOLD)
    Tier 2: Vector embedding similarity vs domain prototypes (uses CLASSIFIER_EMBEDDING_THRESHOLD)
    Tier 3: Zero-shot classification via Claude Haiku 4.5 (uses CLASSIFIER_LLM_CONFIDENCE)
    Includes content hash caching for performance optimization.
    """
    # Check cache first
    cached = _get_cached_classification(content or "")
    if cached:
        return cached
    
    # Tier 1: Fast Keyword matching
    domain, conf = DomainClassifier.classify(content or "")
    if fast_only or conf >= settings.CLASSIFIER_KEYWORD_THRESHOLD:
        result = {"domain": domain, "confidence": round(float(conf), 3), "method": "keyword"}
        _cache_classification(content, result)
        return result

    # Tier 2: Vector embedding similarity
    if settings.STREAMPULSE_HYBRID_LLM == "1":
        content_hash = _content_hash(content or "")

        # Persistent pgvector cache (separate from the in-memory _classification_cache
        # above, which is per-process and cleared on restart). Optional -- gated by
        # ENABLE_PGVECTOR, same as the rest of the storage/ package.
        pg_cache = None
        if settings.ENABLE_PGVECTOR:
            try:
                from storage import get_vector_cache
                pg_cache = get_vector_cache()
                cached_pg = pg_cache.get(content_hash)
                if cached_pg:
                    _cache_classification(content, cached_pg)
                    return cached_pg
            except Exception as e:
                log.warning("pgvector cache lookup failed: %s", e)
                pg_cache = None

        try:
            match = embedding_domain_match(content or "")
            if match is not None:
                best_domain, best_score, content_emb = match
                if best_score >= settings.CLASSIFIER_EMBEDDING_THRESHOLD:
                    result = {"domain": best_domain, "confidence": round(best_score, 3), "method": "vector_embedding"}
                    _cache_classification(content, result)
                    if pg_cache is not None:
                        try:
                            pg_cache.set(content_hash, content or "", content_emb, result)
                        except Exception as e:
                            log.warning("pgvector cache write failed: %s", e)
                    return result
        except Exception as e:
            log.warning("Embedding classification failed: %s", e)

    if settings.STREAMPULSE_HYBRID_LLM != "1":
        result = {"domain": domain, "confidence": round(float(conf), 3), "method": "keyword_low_conf"}
        _cache_classification(content, result)
        return result

    # Tier 3: Zero-shot classification via LLM (Claude Haiku or Gemini)
    try:
        from litellm import completion
        labels = list(DOMAIN_PATTERNS.keys()) + ["General"]
        # Fall back to Gemini Flash when no Anthropic/OpenAI key is configured
        model = settings.LLM_JUDGE
        if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY") and os.getenv("GEMINI_API_KEY"):
            model = "gemini/gemini-2.5-flash"

        resp = completion(
            model=model,
            messages=[
                {"role": "system", "content": f"Classify the following document into exactly one label from {labels}. Reply with ONLY the label."},
                {"role": "user", "content": f"<document>\n{content[:1200]}\n</document>"}
            ],
            temperature=0.0,
        )
        label = (resp.choices[0].message.content or "").strip()
        if label in labels:
            result = {"domain": label, "confidence": settings.CLASSIFIER_LLM_CONFIDENCE, "method": "llm"}
            _cache_classification(content, result)
            return result
    except Exception as e:
        log.warning("LLM classify escalation failed: %s", e)

    result = {"domain": domain, "confidence": round(float(conf), 3), "method": "keyword_fallback"}
    # Do not cache this result to prevent cache poisoning during LLM outages
    return result


__all__ = [
    "RealtimePipeline",
    "DataRecord",
    "DomainClassifier",
    "DataValidator",
    "classify",
    "get_realtime_pipeline",
    "get_cache_stats",
    "_content_hash",
    "_get_cached_classification",
    "_cache_classification",
    "embedding_domain_match",
    "DOMAIN_PROTOTYPES",
]
