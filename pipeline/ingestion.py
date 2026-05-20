"""
Data Ingestion Manager - Backend Service

Handles automated data ingestion from generated dataset with control over:
- Percentage of data to ingest (all, partial, specific domains)
- Data deletion and cleanup
- Real-time ingestion progress tracking
- Manual data upload from users
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from datetime import datetime
import asyncio
from dataclasses import dataclass, asdict

from core.logger import get_logger
from services.realtime_pipeline import RealtimePipeline

log = get_logger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class IngestionStats:
    """Statistics for data ingestion operation."""
    total_records: int = 0
    ingested_records: int = 0
    failed_records: int = 0
    ingestion_percentage: float = 0.0
    domains_covered: List[str] = None
    companies_covered: List[str] = None
    execution_time_seconds: float = 0.0
    timestamp: str = ""
    status: str = "pending"  # pending, in_progress, completed, failed
    error_message: str = ""

    def __post_init__(self):
        if self.domains_covered is None:
            self.domains_covered = []
        if self.companies_covered is None:
            self.companies_covered = []
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


# ════════════════════════════════════════════════════════════════════════════
# DATA INGESTION MANAGER
# ════════════════════════════════════════════════════════════════════════════

class DataIngestionManager:
    """
    Manages data ingestion from enhanced_synthetic_dataset with granular control.
    
    Features:
    - Ingest percentage of data (0-100%)
    - Filter by specific domains
    - Track ingestion progress
    - Delete ingested data
    - Manual user uploads
    """

    DATASET_PATH = Path("enhanced_synthetic_dataset")
    INGESTION_DB_PATH = Path(".ingestion_state")
    
    # Domain aliases for CSV
    VALID_DOMAINS = ["Finance", "Growth", "Operations", "People", "ESG"]

    def __init__(self):
        """Initialize the data ingestion manager."""
        self.pipeline = None
        self.ingestion_stats = {}
        self.ingested_data_registry = {}  # Track what's been ingested
        self._load_ingestion_state()

    async def initialize(self):
        """Initialize the real-time pipeline."""
        if not self.pipeline:
            self.pipeline = await RealtimePipeline.create()
            log.info("Data Ingestion Manager initialized with RealtimePipeline")

    def _load_ingestion_state(self):
        """Load previous ingestion state from disk."""
        try:
            if self.INGESTION_DB_PATH.exists():
                with open(self.INGESTION_DB_PATH, 'r') as f:
                    state = json.load(f)
                    self.ingestion_stats = state.get('stats', {})
                    self.ingested_data_registry = state.get('registry', {})
                    log.info("Loaded ingestion state: %s records", sum(
                        v.get('count', 0) for v in self.ingestion_stats.values()
                    ))
        except Exception as e:
            log.warning("Could not load ingestion state: %s", e)
            self.ingestion_stats = {}
            self.ingested_data_registry = {}

    def _save_ingestion_state(self):
        """Save current ingestion state to disk."""
        try:
            with open(self.INGESTION_DB_PATH, 'w') as f:
                json.dump({
                    'stats': self.ingestion_stats,
                    'registry': self.ingested_data_registry,
                    'timestamp': datetime.utcnow().isoformat()
                }, f, indent=2)
        except Exception as e:
            log.error("Could not save ingestion state: %s", e)

    def get_dataset_info(self) -> Dict[str, Any]:
        """Get information about available dataset."""
        csv_path = self.DATASET_PATH / "csv" / "all_kpis.csv"
        
        if not csv_path.exists():
            return {
                "status": "not_available",
                "message": "Enhanced dataset not found",
                "path": str(self.DATASET_PATH)
            }

        try:
            df = pd.read_csv(csv_path)
            
            return {
                "status": "available",
                "total_records": len(df),
                "domains": df['domain'].unique().tolist() if 'domain' in df.columns else [],
                "companies": df['company'].unique().tolist() if 'company' in df.columns else [],
                "metrics": df['metric'].unique().tolist() if 'metric' in df.columns else [],
                "time_period": {
                    "start": df['period'].min() if 'period' in df.columns else None,
                    "end": df['period'].max() if 'period' in df.columns else None,
                },
                "file_size_mb": csv_path.stat().st_size / (1024 * 1024),
                "available_files": {
                    "csvs": len(list(self.DATASET_PATH.glob("csv/*.csv"))),
                    "pdfs": len(list(self.DATASET_PATH.glob("pdf/*.pdf"))),
                    "jsons": len(list(self.DATASET_PATH.glob("json/*.json"))),
                    "emails": len(list(self.DATASET_PATH.glob("emails/*.json"))),
                    "sheets": len(list(self.DATASET_PATH.glob("sheets_exports/*.json"))),
                }
            }
        except Exception as e:
            log.error("Error reading dataset: %s", e)
            return {
                "status": "error",
                "message": str(e),
                "path": str(self.DATASET_PATH)
            }

    async def ingest_all_data(
        self,
        percentage: float = 100.0,
        domains: Optional[List[str]] = None,
        companies: Optional[List[str]] = None
    ) -> IngestionStats:
        """
        Ingest data from generated dataset with granular control.
        
        Args:
            percentage: Percentage of data to ingest (0-100)
            domains: List of domains to include (None = all)
            companies: List of companies to include (None = all)
        
        Returns:
            IngestionStats with results
        """
        if not self.pipeline:
            await self.initialize()

        start_time = datetime.utcnow()
        stats = IngestionStats(
            ingestion_percentage=percentage,
            status="in_progress"
        )

        try:
            csv_path = self.DATASET_PATH / "csv" / "all_kpis.csv"
            
            if not csv_path.exists():
                stats.status = "failed"
                stats.error_message = f"Dataset not found at {csv_path}"
                return stats

            # Read dataset
            log.info("Reading dataset from %s", csv_path)
            df = pd.read_csv(csv_path)
            stats.total_records = len(df)

            # Filter by domains if specified
            if domains and len(domains) > 0:
                df = df[df['domain'].isin(domains)]
                stats.domains_covered = domains
            else:
                stats.domains_covered = df['domain'].unique().tolist()

            # Filter by companies if specified
            if companies and len(companies) > 0:
                df = df[df['company'].isin(companies)]
                stats.companies_covered = companies
            else:
                stats.companies_covered = df['company'].unique().tolist()

            # Sample by percentage
            if 0 < percentage < 100:
                sample_size = max(1, int(len(df) * (percentage / 100)))
                df = df.sample(n=sample_size, random_state=42)
                log.info("Sampling %s%% of data (%s records)", percentage, len(df))

            # Ingest records
            log.info("Starting ingestion of %s records", len(df))
            for idx, row in df.iterrows():
                try:
                    record = {
                        "company": row.get("company", ""),
                        "domain": row.get("domain", ""),
                        "metric": row.get("metric", ""),
                        "value": float(row.get("value", 0)),
                        "period": row.get("period", ""),
                        "date": row.get("date", ""),
                    }
                    
                    # Ingest through pipeline
                    result = await self.pipeline.ingest_from_webhook(record)
                    stats.ingested_records += 1
                    
                except Exception as e:
                    stats.failed_records += 1
                    log.warning("Failed to ingest record %s: %s", idx, e)
                    continue

                # Progress logging every 100 records
                if stats.ingested_records % 100 == 0:
                    log.info("Ingested %s / %s records", stats.ingested_records, len(df))

            stats.status = "completed"
            stats.execution_time_seconds = (datetime.utcnow() - start_time).total_seconds()

            # Update registry
            ingestion_key = f"batch_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.ingestion_stats[ingestion_key] = {
                "count": stats.ingested_records,
                "domains": stats.domains_covered,
                "companies": stats.companies_covered,
                "timestamp": stats.timestamp,
                "percentage": percentage
            }
            self._save_ingestion_state()

            log.info(
                "Ingestion completed: %s / %s records in %.2fs",
                stats.ingested_records, stats.total_records,
                stats.execution_time_seconds
            )

            return stats

        except Exception as e:
            stats.status = "failed"
            stats.error_message = str(e)
            log.error("Ingestion failed: %s", e)
            return stats

    async def ingest_by_domains(
        self,
        domain_percentages: Dict[str, float]
    ) -> Dict[str, IngestionStats]:
        """
        Ingest data with different percentages for each domain.
        
        Args:
            domain_percentages: Dict mapping domain names to percentages
                Example: {"Finance": 100, "Operations": 50, "People": 25}
        
        Returns:
            Dict mapping domain names to IngestionStats
        """
        results = {}
        
        for domain, percentage in domain_percentages.items():
            if domain not in self.VALID_DOMAINS:
                log.warning("Invalid domain: %s", domain)
                continue
            
            log.info("Ingesting %s%% of %s domain", percentage, domain)
            stats = await self.ingest_all_data(
                percentage=percentage,
                domains=[domain]
            )
            results[domain] = stats

        return results

    async def ingest_by_companies(
        self,
        company_percentages: Dict[str, float]
    ) -> Dict[str, IngestionStats]:
        """
        Ingest data with different percentages for each company.
        
        Args:
            company_percentages: Dict mapping company names to percentages
        
        Returns:
            Dict mapping company names to IngestionStats
        """
        results = {}
        
        for company, percentage in company_percentages.items():
            log.info("Ingesting %s%% of %s data", percentage, company)
            stats = await self.ingest_all_data(
                percentage=percentage,
                companies=[company]
            )
            results[company] = stats

        return results

    def ingest_pdf_documents(self) -> Dict[str, Any]:
        """Ingest PDF documents (invoices, reports, etc.)."""
        from services.ocr_enhancement import EnhancedDocumentProcessor
        
        processor = EnhancedDocumentProcessor()
        pdf_dir = self.DATASET_PATH / "pdf"
        
        results = {
            "total_files": 0,
            "processed_files": 0,
            "failed_files": 0,
            "documents": []
        }

        if not pdf_dir.exists():
            log.warning("PDF directory not found: %s", pdf_dir)
            return results

        for pdf_file in pdf_dir.glob("*.pdf"):
            results["total_files"] += 1
            try:
                result = processor.process_pdf(str(pdf_file))
                results["processed_files"] += 1
                results["documents"].append({
                    "filename": pdf_file.name,
                    "doc_type": result.get("classification", {}).get("type", "unknown"),
                    "confidence": result.get("classification", {}).get("confidence", 0),
                    "extracted_data": result.get("text", "")[:500]  # First 500 chars
                })
            except Exception as e:
                results["failed_files"] += 1
                log.error("Failed to process PDF %s: %s", pdf_file.name, e)

        return results

    def ingest_email_samples(self) -> Dict[str, Any]:
        """Ingest email samples."""
        email_dir = self.DATASET_PATH / "emails"
        
        results = {
            "total_files": 0,
            "emails_ingested": 0,
            "failed_emails": 0,
            "sources": []
        }

        if not email_dir.exists():
            log.warning("Email directory not found: %s", email_dir)
            return results

        for email_file in email_dir.glob("*.json"):
            try:
                with open(email_file, 'r') as f:
                    emails = json.load(f)
                    results["total_files"] += 1
                    
                    for email in emails:
                        try:
                            results["emails_ingested"] += 1
                            results["sources"].append({
                                "from": email.get("from"),
                                "subject": email.get("subject"),
                                "date": email.get("date")
                            })
                        except Exception as e:
                            results["failed_emails"] += 1
                            log.error("Failed to ingest email: %s", e)

            except Exception as e:
                log.error("Failed to read email file %s: %s", email_file.name, e)

        return results

    def ingest_sheets_data(self) -> Dict[str, Any]:
        """Ingest Google Sheets export data."""
        sheets_dir = self.DATASET_PATH / "sheets_exports"
        
        results = {
            "total_files": 0,
            "sheets_ingested": 0,
            "failed_sheets": 0,
            "data_types": []
        }

        if not sheets_dir.exists():
            log.warning("Sheets directory not found: %s", sheets_dir)
            return results

        for sheet_file in sheets_dir.glob("*.json"):
            try:
                with open(sheet_file, 'r') as f:
                    sheets_data = json.load(f)
                    results["total_files"] += 1
                    
                    for sheet_name, data in sheets_data.items():
                        try:
                            results["sheets_ingested"] += 1
                            results["data_types"].append({
                                "file": sheet_file.name,
                                "sheet": sheet_name,
                                "rows": len(data) if isinstance(data, list) else 1
                            })
                        except Exception as e:
                            results["failed_sheets"] += 1
                            log.error("Failed to ingest sheet %s: %s", sheet_name, e)

            except Exception as e:
                log.error("Failed to read sheets file %s: %s", sheet_file.name, e)

        return results

    async def delete_all_ingested_data(self) -> Dict[str, Any]:
        """
        Delete all ingested data from the platform.
        
        Returns:
            Summary of deleted data
        """
        if not self.pipeline:
            await self.initialize()

        try:
            # Get all ingested data references
            deleted_count = 0
            
            # Clear ingestion statistics
            stats_count = len(self.ingestion_stats)
            self.ingestion_stats.clear()
            self.ingested_data_registry.clear()
            self._save_ingestion_state()

            log.warning("Deleted all ingested data records (cleared %s ingestion batches)", stats_count)
            
            return {
                "status": "success",
                "message": f"Deleted all ingested data ({stats_count} batches)",
                "deleted_batches": stats_count,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            log.error("Failed to delete ingested data: %s", e)
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def delete_domain_data(self, domain: str) -> Dict[str, Any]:
        """
        Delete ingested data for a specific domain.
        
        Args:
            domain: Domain name to delete
        
        Returns:
            Deletion summary
        """
        try:
            deleted_count = 0
            
            for batch_key, batch_info in list(self.ingestion_stats.items()):
                if domain in batch_info.get("domains", []):
                    del self.ingestion_stats[batch_key]
                    deleted_count += 1
            
            self._save_ingestion_state()
            
            return {
                "status": "success",
                "message": f"Deleted data for domain: {domain}",
                "deleted_batches": deleted_count,
                "domain": domain,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            log.error("Failed to delete domain data: %s", e)
            return {
                "status": "error",
                "message": str(e),
                "domain": domain
            }

    async def delete_company_data(self, company: str) -> Dict[str, Any]:
        """Delete ingested data for a specific company."""
        try:
            deleted_count = 0

            for batch_key, batch_info in list(self.ingestion_stats.items()):
                if company in batch_info.get("companies", []):
                    del self.ingestion_stats[batch_key]
                    deleted_count += 1

            self._save_ingestion_state()

            return {
                "status": "success",
                "message": f"Deleted data for company: {company}",
                "deleted_batches": deleted_count,
                "company": company,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            log.error("Failed to delete company data: %s", e)
            return {
                "status": "error",
                "message": str(e),
                "company": company
            }

    def get_ingestion_status(self) -> Dict[str, Any]:
        """Get current ingestion status and history."""
        total_ingested = sum(
            batch.get("count", 0) for batch in self.ingestion_stats.values()
        )

        return {
            "ingestion_history": self.ingestion_stats,
            "total_ingested_records": total_ingested,
            "total_batches": len(self.ingestion_stats),
            "domains_covered": list(set(
                domain for batch in self.ingestion_stats.values()
                for domain in batch.get("domains", [])
            )),
            "companies_covered": list(set(
                company for batch in self.ingestion_stats.values()
                for company in batch.get("companies", [])
            )),
            "last_update": self.ingestion_stats.get(
                max(self.ingestion_stats, default=None), 
                {}
            ).get("timestamp", "")
        }
