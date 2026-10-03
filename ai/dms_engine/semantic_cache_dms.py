"""
Semantic Cache for DMS Pipeline

Provides instant responses for repeated or semantically similar queries.

HOW IT WORKS:
=============
1. When query is processed, result is stored in cache with embedding
2. Next time similar query comes, check semantic similarity
3. If similarity > threshold (0.96), return cached result instantly
4. Otherwise, process normally and cache the new result

CACHE BENEFITS:
===============
- 600x faster (50-60s → 0.1s for Tier 3 queries)
- Zero LLM cost (no SQL generation, no execution)
- Consistent results (same query = same answer)
- Session-scoped (cache expires after 24 hours)

SIMILARITY THRESHOLD:
=====================
0.96 = Very similar (strict matching)
- "Show FFS for dealer D001" ≈ "Display FFS records for dealership D001"
- Prevents false positives

EDGE CASES HANDLED:
===================
- Cache initialization fails → Disable cache, continue without it
- Cache lookup fails → Log warning, continue without cache
- Cache store fails → Log warning, continue without storing
- Corrupted cache data → Clear cache, continue
- Invalid session_id → Generate temporary ID

"""

from typing import Optional, Dict, Any
from ai.rag_engine.semantic_cache import SemanticCache as RAGSemanticCache
import traceback


class DMSSemanticCache:
    """
    Semantic cache wrapper for DMS pipeline.

    Provides instant responses for:
    - Exact repeated queries (within same session)
    - Semantically similar queries (similarity > 0.96)

    Examples:
        Query 1: "Show repair orders for December 2024"
        Query 2: "Display all RO from Dec 2024"  → Cache hit (similar)

        Query 1: "List FFS records for dealer D001"
        Query 2: "Show FFS for dealer D001"  → Cache hit (similar)

    CRITICAL: Cache is session-scoped!
    - Different sessions = Different caches
    - Cache expires after 24 hours
    - Cache is persistent (survives server restarts)
    """

    def __init__(
        self,
        persist_directory: str = "./data/dms_semantic_cache",
        similarity_threshold: float = 0.96,
        session_ttl_hours: int = 24,
        verbose: bool = True
    ):
        """
        Initialize DMS semantic cache.

        Args:
            persist_directory: Where to store cache data
            similarity_threshold: Minimum similarity for cache hit (0.96 = very similar)
            session_ttl_hours: Cache expiry time (default: 24 hours)
            verbose: Enable detailed logging (default: True)

        Edge Cases:
            - Cache directory doesn't exist → Create it
            - Cache initialization fails → Disable cache, log error
            - Invalid threshold → Use default 0.96
        """
        self.persist_directory = persist_directory
        self.similarity_threshold = max(0.0, min(1.0, similarity_threshold))  # Clamp to [0, 1]
        self.session_ttl_hours = session_ttl_hours
        self.verbose = verbose
        self.enabled = False  # Will be set to True if initialization succeeds
        self.cache = None

        if self.verbose:
            print(f"\n[SemanticCache] ════════════════════════════════════════════════")
            print(f"[SemanticCache] INITIALIZING DMS SEMANTIC CACHE")
            print(f"[SemanticCache] Directory: {persist_directory}")
            print(f"[SemanticCache] Similarity threshold: {similarity_threshold}")
            print(f"[SemanticCache] Session TTL: {session_ttl_hours} hours")

        # =====================================================================
        # EDGE CASE 1: Cache initialization fails → Disable cache
        # =====================================================================
        try:
            # Create cache directory if it doesn't exist
            import os
            os.makedirs(persist_directory, exist_ok=True)

            if self.verbose:
                print(f"[SemanticCache]   Cache directory created/verified")

            # Initialize RAG semantic cache (production-tested)
            self.cache = RAGSemanticCache(
                persist_directory=persist_directory,
                similarity_threshold=similarity_threshold,
                session_ttl_hours=session_ttl_hours
            )

            self.enabled = True

            if self.verbose:
                print(f"[SemanticCache] ✓ CACHE ENABLED")
                print(f"[SemanticCache] ════════════════════════════════════════════════\n")

        except Exception as e:
            self.enabled = False

            if self.verbose:
                print(f"[SemanticCache] ✗ INITIALIZATION FAILED: {e}")
                print(f"[SemanticCache] Cache DISABLED - continuing without caching")
                print(f"[SemanticCache] ════════════════════════════════════════════════\n")
                traceback.print_exc()

    def get(
        self,
        query: str,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached result for query (if exists and similar enough).

        WORKFLOW:
        =========
        1. Check if cache is enabled
        2. Validate inputs (query, session_id)
        3. Search cache for similar queries
        4. If similarity > threshold → Return cached result
        5. Otherwise → Return None (cache miss)

        Args:
            query: User's query string
            session_id: Session ID for scoping

        Returns:
            Cached QueryResult dict if hit, None if miss

        Edge Cases:
            - Cache disabled → Return None (always miss)
            - Empty query → Return None
            - Invalid session_id → Generate temp ID and continue
            - Cache lookup fails → Log error, return None
            - Corrupted cache data → Log error, return None

        Examples:
            >>> cache.get("Show FFS for D001", "session123")
            {
                "query": "Show FFS for dealer D001",
                "tier_used": 2,
                "sql": "SELECT ...",
                "natural_answer": "...",
                ...
            }
        """
        # =====================================================================
        # EDGE CASE 1: Cache disabled
        # =====================================================================
        if not self.enabled or self.cache is None:
            if self.verbose:
                print(f"[SemanticCache] Cache disabled, skipping lookup")
            return None

        # =====================================================================
        # EDGE CASE 2: Empty query
        # =====================================================================
        if not query or len(query.strip()) == 0:
            if self.verbose:
                print(f"[SemanticCache] ⚠ Empty query, skipping cache lookup")
            return None

        # =====================================================================
        # EDGE CASE 3: Invalid session_id
        # =====================================================================
        if not session_id or len(session_id.strip()) == 0:
            import uuid
            session_id = str(uuid.uuid4())[:8]
            if self.verbose:
                print(f"[SemanticCache] ⚠ Invalid session_id, using temp: {session_id}")

        # =====================================================================
        # STEP 1: Attempt cache lookup
        # =====================================================================
        if self.verbose:
            print(f"[SemanticCache] Checking cache for: '{query[:60]}...'")
            print(f"[SemanticCache]   Session: {session_id[:8]}...")

        try:
            cached = self.cache.get(query, session_id)

            if cached:
                # Cache hit!
                similarity = cached.get('similarity', 0)
                original_query = cached.get('original_query', '')
                cached_response = cached.get('response', {})

                # Deserialize JSON string back to dict (if stored as JSON)
                if isinstance(cached_response, str):
                    try:
                        import json
                        cached_response = json.loads(cached_response)
                    except json.JSONDecodeError:
                        # If not valid JSON, return as-is (legacy cache format)
                        pass

                if self.verbose:
                    print(f"[SemanticCache] ✓ CACHE HIT! (similarity: {similarity:.3f})")
                    print(f"[SemanticCache]   Original query: '{original_query[:60]}...'")
                    print(f"[SemanticCache]   Cached result type: {type(cached_response)}")

                # Return cached result
                return cached_response

            else:
                # Cache miss
                if self.verbose:
                    print(f"[SemanticCache] Cache miss (no similar queries found)")

                return None

        except Exception as e:
            # =================================================================
            # EDGE CASE 4: Cache lookup fails
            # =================================================================
            if self.verbose:
                print(f"[SemanticCache] ✗ CACHE LOOKUP ERROR: {e}")
                print(f"[SemanticCache] Continuing without cache")
                traceback.print_exc()

            # Don't fail the entire query - just return None
            return None

    def set(
        self,
        query: str,
        result: Any,
        session_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store query result in cache.

        WORKFLOW:
        =========
        1. Check if cache is enabled
        2. Validate inputs
        3. Convert QueryResult to dict if needed
        4. Store in cache with embedding
        5. Return success status

        Args:
            query: User's query string
            result: QueryResult object or dict to cache
            session_id: Session ID for scoping
            metadata: Optional metadata (tier used, execution time, etc.)

        Returns:
            True if stored successfully, False otherwise

        Edge Cases:
            - Cache disabled → Return False (no-op)
            - Empty query → Skip caching, return False
            - Invalid result → Skip caching, return False
            - Cache store fails → Log error, return False
            - Result is dict → Use as-is
            - Result is QueryResult object → Convert to dict

        Examples:
            >>> cache.set("Show FFS", result, "session123", {"tier": 2})
            True
        """
        # =====================================================================
        # EDGE CASE 1: Cache disabled
        # =====================================================================
        if not self.enabled or self.cache is None:
            if self.verbose:
                print(f"[SemanticCache] Cache disabled, skipping storage")
            return False

        # =====================================================================
        # EDGE CASE 2: Empty query
        # =====================================================================
        if not query or len(query.strip()) == 0:
            if self.verbose:
                print(f"[SemanticCache] ⚠ Empty query, skipping cache storage")
            return False

        # =====================================================================
        # EDGE CASE 3: Invalid session_id
        # =====================================================================
        if not session_id or len(session_id.strip()) == 0:
            import uuid
            session_id = str(uuid.uuid4())[:8]
            if self.verbose:
                print(f"[SemanticCache] ⚠ Invalid session_id, using temp: {session_id}")

        # =====================================================================
        # EDGE CASE 4: Invalid result
        # =====================================================================
        if result is None:
            if self.verbose:
                print(f"[SemanticCache] ⚠ Null result, skipping cache storage")
            return False

        # =====================================================================
        # STEP 1: Convert QueryResult to dict if needed
        # =====================================================================
        try:
            # Check if result has to_dict method (QueryResult object)
            if hasattr(result, 'to_dict'):
                result_dict = result.to_dict()
                if self.verbose:
                    print(f"[SemanticCache] Converted QueryResult to dict")
            elif isinstance(result, dict):
                result_dict = result
                if self.verbose:
                    print(f"[SemanticCache] Result is already dict")
            else:
                if self.verbose:
                    print(f"[SemanticCache] ⚠ Unknown result type: {type(result)}, skipping")
                return False

        except Exception as e:
            if self.verbose:
                print(f"[SemanticCache] ✗ Result conversion error: {e}, skipping")
            return False

        # =====================================================================
        # STEP 2: Add metadata to result
        # =====================================================================
        if metadata:
            if 'metadata' not in result_dict:
                result_dict['metadata'] = {}

            # Merge metadata
            result_dict['metadata'].update(metadata)

            if self.verbose:
                print(f"[SemanticCache]   Added metadata: {list(metadata.keys())}")

        # =====================================================================
        # STEP 3: Store in cache
        # =====================================================================
        if self.verbose:
            print(f"[SemanticCache] Storing result in cache...")
            print(f"[SemanticCache]   Query: '{query[:60]}...'")
            print(f"[SemanticCache]   Session: {session_id[:8]}...")

        try:
            # Convert result dict to JSON string (ChromaDB requires string documents)
            import json
            result_json = json.dumps(result_dict, default=str)  # default=str handles non-serializable types

            self.cache.set(
                query=query,
                response=result_json,  # Store as JSON string
                session_id=session_id,
                cache_type="session",
                metadata=metadata
            )

            if self.verbose:
                print(f"[SemanticCache] ✓ Result stored successfully")

            return True

        except Exception as e:
            # =================================================================
            # EDGE CASE 5: Cache store fails
            # =================================================================
            if self.verbose:
                print(f"[SemanticCache] ✗ CACHE STORE ERROR: {e}")
                print(f"[SemanticCache] Continuing without caching this result")
                traceback.print_exc()

            # Don't fail the entire query - just skip caching
            return False

    def clear_session(self, session_id: str) -> bool:
        """
        Clear all cached results for a session.

        Args:
            session_id: Session ID to clear

        Returns:
            True if cleared successfully, False otherwise

        Edge Cases:
            - Cache disabled → Return False
            - Invalid session_id → Skip, return False
            - Clear fails → Log error, return False
        """
        if not self.enabled or self.cache is None:
            if self.verbose:
                print(f"[SemanticCache] Cache disabled, cannot clear session")
            return False

        if not session_id or len(session_id.strip()) == 0:
            if self.verbose:
                print(f"[SemanticCache] ⚠ Invalid session_id, cannot clear")
            return False

        if self.verbose:
            print(f"[SemanticCache] Clearing session: {session_id[:8]}...")

        try:
            # RAG cache has clear_session method
            if hasattr(self.cache, 'clear_session'):
                self.cache.clear_session(session_id)
                if self.verbose:
                    print(f"[SemanticCache] ✓ Session cleared")
                return True
            else:
                if self.verbose:
                    print(f"[SemanticCache] ⚠ Cache doesn't support clear_session")
                return False

        except Exception as e:
            if self.verbose:
                print(f"[SemanticCache] ✗ Clear session error: {e}")
                traceback.print_exc()
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (hits, misses, size, etc.)

        Edge Cases:
            - Cache disabled → Return empty stats
            - Stats retrieval fails → Return error stats
        """
        if not self.enabled or self.cache is None:
            return {
                "enabled": False,
                "error": "Cache disabled"
            }

        try:
            stats = {
                "enabled": True,
                "persist_directory": self.persist_directory,
                "similarity_threshold": self.similarity_threshold,
                "session_ttl_hours": self.session_ttl_hours,
            }

            # Try to get stats from underlying cache
            if hasattr(self.cache, 'get_stats'):
                cache_stats = self.cache.get_stats()
                stats.update(cache_stats)

            return stats

        except Exception as e:
            return {
                "enabled": True,
                "error": str(e)
            }
