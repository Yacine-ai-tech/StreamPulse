"""
Vector embedding cache using pgvector for StreamPulse classifier.

This module provides persistent storage for embedding vectors using pgvector,
enabling efficient similarity search and caching of classification results.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.config import settings
from core.logger import get_logger

log = get_logger(__name__)


class VectorCache:
    """Vector embedding cache with pgvector backend."""

    def __init__(self):
        self._enabled = settings.ENABLE_PGVECTOR
        self._conn = None
        
        if self._enabled:
            self._initialize_pgvector()
        else:
            log.info("pgvector cache disabled (ENABLE_PGVECTOR=false)")

    def _initialize_pgvector(self):
        """Initialize pgvector connection and schema."""
        try:
            import psycopg
            from psycopg import sql
            
            # Connect to PostgreSQL
            self._conn = psycopg.connect(settings.POSTGRES_URL)
            
            # Create pgvector extension if not exists
            with self._conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Create embedding cache table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS embedding_cache (
                        id SERIAL PRIMARY KEY,
                        content_hash VARCHAR(64) UNIQUE NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector(1024) NOT NULL,
                        classification_result JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create index on content_hash for fast lookup
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embedding_cache_hash 
                    ON embedding_cache(content_hash)
                """)
                
                # Create index on embedding for similarity search
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embedding_cache_embedding 
                    ON embedding_cache USING ivfflat (embedding vector_cosine_ops)
                """)
                
                self._conn.commit()
                log.info("pgvector cache initialized successfully")
                
        except ImportError:
            log.warning("psycopg not available, pgvector cache disabled")
            self._enabled = False
        except Exception as e:
            log.error("Failed to initialize pgvector cache: %s", e)
            self._enabled = False

    def get(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached classification by content hash."""
        if not self._enabled or not self._conn:
            return None
            
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT classification_result, last_accessed 
                    FROM embedding_cache 
                    WHERE content_hash = %s
                """, (content_hash,))
                
                result = cur.fetchone()
                if result:
                    # Update last accessed time
                    cur.execute("""
                        UPDATE embedding_cache 
                        SET last_accessed = CURRENT_TIMESTAMP 
                        WHERE content_hash = %s
                    """, (content_hash,))
                    self._conn.commit()
                    
                    return json.loads(result[0])
                    
        except Exception as e:
            log.error("Failed to retrieve from pgvector cache: %s", e)
            
        return None

    def set(self, content_hash: str, content: str, embedding: List[float], 
            classification_result: Dict[str, Any]) -> bool:
        """Store embedding and classification result."""
        if not self._enabled or not self._conn:
            return False
            
        try:
            with self._conn.cursor() as cur:
                # Convert embedding to pgvector format
                embedding_str = f"[{','.join(map(str, embedding))}]"
                result_json = json.dumps(classification_result)
                
                cur.execute("""
                    INSERT INTO embedding_cache 
                    (content_hash, content, embedding, classification_result)
                    VALUES (%s, %s, %s::vector, %s::jsonb)
                    ON CONFLICT (content_hash) 
                    DO UPDATE SET 
                        embedding = EXCLUDED.embedding,
                        classification_result = EXCLUDED.classification_result,
                        last_accessed = CURRENT_TIMESTAMP
                """, (content_hash, content, embedding_str, result_json))
                
                self._conn.commit()
                return True
                
        except Exception as e:
            log.error("Failed to store in pgvector cache: %s", e)
            self._conn.rollback()
            return False

    def find_similar(self, embedding: List[float], limit: int = 5, 
                    threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Find similar embeddings using cosine similarity."""
        if not self._enabled or not self._conn:
            return []
            
        try:
            with self._conn.cursor() as cur:
                embedding_str = f"[{','.join(map(str, embedding))}]"
                
                cur.execute("""
                    SELECT content_hash, content, classification_result, 
                           1 - (embedding <=> %s::vector) as similarity
                    FROM embedding_cache
                    WHERE 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """, (embedding_str, embedding_str, threshold, embedding_str, limit))
                
                results = []
                for row in cur.fetchall():
                    results.append({
                        "content_hash": row[0],
                        "content": row[1],
                        "classification_result": json.loads(row[2]),
                        "similarity": float(row[3])
                    })
                
                return results
                
        except Exception as e:
            log.error("Failed to find similar embeddings: %s", e)
            return []

    def cleanup_old_entries(self, days: int = 30) -> int:
        """Remove cache entries older than specified days."""
        if not self._enabled or not self._conn:
            return 0
            
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM embedding_cache 
                    WHERE last_accessed < CURRENT_TIMESTAMP - INTERVAL '%s days'
                """, (days,))
                
                deleted = cur.rowcount
                self._conn.commit()
                log.info("Cleaned up %d old cache entries", deleted)
                return deleted
                
        except Exception as e:
            log.error("Failed to cleanup old cache entries: %s", e)
            self._conn.rollback()
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._enabled or not self._conn:
            return {"enabled": False}
            
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM embedding_cache")
                total_entries = cur.fetchone()[0]
                
                cur.execute("""
                    SELECT COUNT(*) FROM embedding_cache 
                    WHERE last_accessed > CURRENT_TIMESTAMP - INTERVAL '7 days'
                """)
                recent_entries = cur.fetchone()[0]
                
                return {
                    "enabled": True,
                    "total_entries": total_entries,
                    "recent_entries": recent_entries,
                    "storage_backend": "pgvector"
                }
                
        except Exception as e:
            log.error("Failed to get cache stats: %s", e)
            return {"enabled": True, "error": str(e)}

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global instance
_vector_cache: Optional[VectorCache] = None


def get_vector_cache() -> VectorCache:
    """Get or create the global vector cache instance."""
    global _vector_cache
    if _vector_cache is None:
        _vector_cache = VectorCache()
    return _vector_cache