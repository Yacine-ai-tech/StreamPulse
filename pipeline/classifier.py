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
import json
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
    Tier 1: Fast Keyword matching
    Tier 2: Vector embedding similarity vs domain prototypes (BAAI/bge-large-en-v1.5)
    Tier 3: Zero-shot classification via Claude Haiku 4.5
    """
    domain, conf = DomainClassifier.classify(content or "")
    if fast_only or conf >= 0.5:
        return {"domain": domain, "confidence": round(float(conf), 3), "method": "keyword"}
        
    # Tier 2: Vector Embedding Fallback
    hf_token = os.getenv("HF_TOKEN", "").strip()
    if hf_token and os.getenv("STREAMPULSE_HYBRID_LLM") == "1":
        try:
            import urllib.request, json as _json
            url = "https://router.huggingface.co/hf-inference/models/BAAI/bge-large-en-v1.5"
            h = {"Authorization": f"Bearer {hf_token}", "Content-Type": "application/json"}
            
            domains = ["Finance", "Operations", "People", "ESG", "IT_Ops", "General"]
            prototypes = [
                "finance revenue profit margin cash flow ebitda",
                "operations supply chain inventory logistics throughput",
                "hr people employee turnover hiring retention",
                "esg sustainability carbon diversity governance",
                "it uptime latency incident deployment devops",
                "general company update news announcement"
            ]
            
            # Embed the content and prototypes
            inputs = [content[:500]] + prototypes
            body = _json.dumps({"inputs": inputs}).encode()
            req = urllib.request.Request(url, data=body, headers=h)
            res = urllib.request.urlopen(req, timeout=10)
            embeddings = _json.loads(res.read())
            
            if embeddings and len(embeddings) == len(inputs):
                # Calculate cosine similarity manually to avoid numpy dependency in this microservice
                content_emb = embeddings[0]
                proto_embs = embeddings[1:]
                
                best_score = -1.0
                best_domain = "General"
                
                def dot_product(v1, v2):
                    return sum(x * y for x, y in zip(v1, v2))
                def magnitude(v):
                    return sum(x * x for x in v) ** 0.5
                    
                c_mag = magnitude(content_emb)
                
                for idx, p_emb in enumerate(proto_embs):
                    p_mag = magnitude(p_emb)
                    if c_mag > 0 and p_mag > 0:
                        score = dot_product(content_emb, p_emb) / (c_mag * p_mag)
                        if score > best_score:
                            best_score = score
                            best_domain = domains[idx]
                            
                if best_score >= 0.5:
                    return {"domain": best_domain, "confidence": round(best_score, 3), "method": "vector_embedding"}
        except Exception as e:
            log.warning("Embedding classification failed: %s", e)

    if os.getenv("STREAMPULSE_HYBRID_LLM") != "1":
        return {"domain": domain, "confidence": round(float(conf), 3), "method": "keyword_low_conf"}

    # Tier 3: Zero-shot classification via LLM (Claude Haiku or Gemini)
    try:
        from litellm import completion
        labels = list(DOMAIN_PATTERNS.keys()) + ["General"]
        # Use GEMINI as fallback if OpenAI/Anthropic are unavailable, as requested by user
        model = settings.LLM_JUDGE
        if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY") and os.getenv("GEMINI_API_KEY"):
            model = "gemini/gemini-1.5-flash"
            
        resp = completion(
            model=model,
            messages=[{"role": "user", "content":
                       f"Classify this into exactly one label from {labels}. "
                       f"Reply with ONLY the label.\n\n{content[:1200]}"}],
            temperature=0.0,
        )
        label = (resp.choices[0].message.content or "").strip()
        if label in labels:
            return {"domain": label, "confidence": 0.7, "method": "llm"}
    except Exception as e:
        log.warning("LLM classify escalation failed: %s", e)
        
    return {"domain": domain, "confidence": round(float(conf), 3), "method": "keyword"}



__all__ = [
    "RealtimePipeline",
    "DataRecord",
    "DomainClassifier",
    "DataValidator",
    "classify",
    "get_realtime_pipeline",
]

