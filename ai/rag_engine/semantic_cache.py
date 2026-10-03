"""
Semantic Caching System

ChromaDB-backed semantic cache for instant, zero-cost responses to similar queries.
Supports session-scoped and global FAQ caching with automatic cleanup.

Features:
- Semantic similarity matching (threshold: 0.96)
- Session-scoped caching (per conversation)
- Separate ChromaDB collection
- Automatic TTL-based cleanup (24 hours for sessions)
"""

from __future__ import annotations
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import chromadb
from chromadb.config import Settings
import hashlib
import time


class SemanticCache:
    """
    Production-grade semantic caching system for RAG queries.

    Uses ChromaDB to store and retrieve cached responses based on semantic similarity.
    Supports both session-scoped (per-user) and global (all-users) caching strategies.

    Memory footprint: Minimal (ChromaDB handles storage efficiently)
    """

    def __init__(
        self,
        persist_directory: str = "./data/semantic_cache",
        collection_name: str = "semantic_cache_v1",
        similarity_threshold: float = 0.96,
        session_ttl_hours: int = 12,
    ):
        """
        Initialize semantic cache with ChromaDB backend.

        Args:
            persist_directory: Directory to persist ChromaDB data
            collection_name: Name of ChromaDB collection
            similarity_threshold: Minimum similarity score for cache hits (default: 0.96)
            session_ttl_hours: TTL for session-scoped cache entries (default: 12 hours)
        """
        self.similarity_threshold = similarity_threshold
        self.session_ttl_seconds = session_ttl_hours * 3600

        # Initialize ChromaDB client
        try:
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                )
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Semantic cache for RAG queries"}
            )

            # print(f"[SemanticCache] Initialized with collection '{collection_name}'")
            # print(f"[SemanticCache] Similarity threshold: {similarity_threshold}")
            # print(f"[SemanticCache] Session TTL: {session_ttl_hours} hours")

        except Exception as e:
            # print(f"[SemanticCache] CRITICAL: Failed to initialize ChromaDB: {e}")
            raise RuntimeError(f"Semantic cache initialization failed: {e}")

    def get(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Retrieve cached response for a semantically similar query.

        Search order:
        1. Session-scoped cache (if session_id provided)
        2. Global FAQ cache (if no session match)

        Args:
            query: User's query
            session_id: Optional session ID for session-scoped lookup

        Returns:
            Dict with cached response or None if no match:
                pass
            {
                "response": "cached response text",
                "original_query": "original query that was cached",
                "similarity": 0.98,
                "cached_at": 1234567890.0,
                "cache_type": "session" or "global",
            }
        """
        try:
            # Step 1: Check session cache (if session_id provided)
            if session_id:
                session_result = self._query_cache(
                    query,
                    cache_type="session",
                    session_id=session_id
                )

                if session_result:
                    # print(f"[SemanticCache] ✅ SESSION HIT (similarity: {session_result['similarity']:.3f})")
                    return session_result

            # Step 2: Check global FAQ cache
            global_result = self._query_cache(
                query,
                cache_type="global",
                session_id=None
            )

            if global_result:
                # print(f"[SemanticCache] ✅ GLOBAL HIT (similarity: {global_result['similarity']:.3f})")
                return global_result

            # No cache hit
            # print(f"[SemanticCache] ❌ MISS (no similar queries found)")
            return None

        except Exception as e:
            # print(f"[SemanticCache] Error during lookup: {e}")
            return None

    def set(
        self,
        query: str,
        response: str,
        session_id: Optional[str] = None,
        cache_type: str = "session",
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Store a query-response pair in the semantic cache.

        FIXED: Now embeds the QUERY (not response) for proper semantic matching.
        The response is stored in metadata for retrieval.

        Args:
            query: User's original query (will be embedded for similarity matching)
            response: AI's response to cache (stored in metadata)
            session_id: Session ID for session-scoped caching
            cache_type: "session" or "global"
            metadata: Optional additional metadata
        """
        if cache_type not in ["session", "global"]:
            raise ValueError(f"Invalid cache_type: {cache_type}. Must be 'session' or 'global'")

        # Generate unique ID
        cache_id = self._generate_cache_id(query, session_id, cache_type)

        # Build metadata with response (truncated if too large for ChromaDB)
        # ChromaDB metadata limit is ~few KB, so truncate large responses
        MAX_RESPONSE_SIZE = 10000  # 10KB limit to be safe
        response_truncated = response[:MAX_RESPONSE_SIZE] if len(response) > MAX_RESPONSE_SIZE else response

        cache_metadata = {
            "cache_type": cache_type,
            "session_id": session_id or "GLOBAL",
            "cached_at": time.time(),
            "original_query": query[:200],  # Store truncated query for debugging
            "response": response_truncated,  # ✅ FIXED: Store response (truncated if needed)
            "response_truncated": len(response) > MAX_RESPONSE_SIZE,  # Flag if truncated
            "response_full_size": len(response),  # Original size
        }

        # Add user metadata (but don't allow overwriting core fields)
        if metadata:
            # Filter out reserved keys
            metadata_copy = {k: v for k, v in metadata.items() if k not in ["response", "cache_type", "session_id", "cached_at"]}
            cache_metadata.update(metadata_copy)

        try:
            # ✅ FIXED: Embed the QUERY (not response) for semantic similarity matching
            # This allows query-to-query matching instead of query-to-response matching
            self.collection.add(
                documents=[query],  # ✅ FIXED: Embed query for similarity matching
                metadatas=[cache_metadata],
                ids=[cache_id]
            )

            if len(response) > MAX_RESPONSE_SIZE:
                pass
                # print(f"[SemanticCache] ⚠️  Response truncated ({len(response)} → {MAX_RESPONSE_SIZE} chars)")

            print(f"[SemanticCache] ✅ Stored {cache_type} cache: '{query[:50]}...'")

        except Exception as e:
            # print(f"[SemanticCache] ❌ ERROR storing cache: {e}")
            print(f"[SemanticCache]   Query: '{query[:100]}...'")
            # print(f"[SemanticCache]   Response size: {len(response)} chars")
            # print(f"[SemanticCache]   Session ID: {session_id}")
            # print(f"[SemanticCache]   Cache ID: {cache_id}")
            import traceback
            traceback.print_exc()

    def _query_cache(
        self,
        query: str,
        cache_type: str,
        session_id: Optional[str]
    ) -> Optional[Dict]:
        """
        Query ChromaDB for semantically similar cached responses.

        FIXED: Now retrieves response from metadata (where it's properly stored).
        Includes backward compatibility for old cache entries.

        Args:
            query: User's query
            cache_type: "session" or "global"
            session_id: Session ID (required for session cache)

        Returns:
            Cached result dict or None
        """
        # Build metadata filter with proper ChromaDB $and operator
        if cache_type == "session" and session_id:
            where_filter = {
                "$and": [
                    {"cache_type": cache_type},
                    {"session_id": session_id}
                ]
            }
        else:
            where_filter = {"cache_type": cache_type}

        try:
            # Query ChromaDB with semantic similarity
            results = self.collection.query(
                query_texts=[query],
                where=where_filter,
                n_results=1  # Get top match only
            )

            # Check if we got results
            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                return None

            # Extract result data
            metadata = results['metadatas'][0][0]
            distance = results['distances'][0][0]
            cache_id = results['ids'][0][0]

            # ✅ FIXED: Get response from metadata (not from documents)
            # Documents now contain the embedded query, not the response
            response = metadata.get('response', None)

            # Backward compatibility: If 'response' not in metadata, try documents
            # This handles old cache entries created before the fix
            if response is None:
                response = results['documents'][0][0]
                # print(f"[SemanticCache] ⚠️  OLD CACHE FORMAT DETECTED (cache_id: {cache_id[:8]}...)")
                # print(f"[SemanticCache] ⚠️  Consider clearing cache for better performance")

            # Sanity check: response should not be empty
            if not response or len(response.strip()) == 0:
                # print(f"[SemanticCache] ⚠️  Empty response in cache, skipping")
                return None

            # Convert distance to similarity (ChromaDB uses cosine distance)
            # Similarity = 1 - distance
            similarity = 1.0 - distance

            # Check if similarity meets threshold
            if similarity < self.similarity_threshold:
                # print(f"[SemanticCache] Low similarity: {similarity:.3f} < {self.similarity_threshold}")
                return None

            # Check TTL for session cache
            if cache_type == "session":
                cached_at = metadata.get("cached_at", 0)
                age_seconds = time.time() - cached_at

                if age_seconds > self.session_ttl_seconds:
                    # print(f"[SemanticCache] Expired: {age_seconds/3600:.1f}h > {self.session_ttl_seconds/3600}h")
                    # Clean up expired entry
                    self._delete_cache_entry(cache_id)
                    return None

            return {
                "response": response,
                "original_query": metadata.get("original_query", ""),
                "similarity": similarity,
                "cached_at": metadata.get("cached_at"),
                "cache_type": cache_type,
            }

        except Exception as e:
            print(f"[SemanticCache] ❌ ERROR querying cache: {e}")
            print(f"[SemanticCache]   Query: '{query[:100]}...'")
            # print(f"[SemanticCache]   Cache type: {cache_type}")
            # print(f"[SemanticCache]   Session ID: {session_id}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_cache_id(self, query: str, session_id: Optional[str], cache_type: str) -> str:
        """
        Generate unique cache ID for a query.

        Args:
            query: User's query
            session_id: Session ID
            cache_type: "session" or "global"

        Returns:
            Unique cache ID (hash-based)
        """
        # Combine query + session + cache_type for uniqueness
        unique_string = f"{cache_type}:{session_id or 'GLOBAL'}:{query}"
        hash_digest = hashlib.sha256(unique_string.encode()).hexdigest()[:16]

        return f"{cache_type}_{hash_digest}"

    def _delete_cache_entry(self, cache_id: str) -> None:
        """
        Delete a cache entry by ID.

        Args:
            cache_id: Cache entry ID to delete
        """
        try:
            self.collection.delete(ids=[cache_id])
            # print(f"[SemanticCache] Deleted expired cache entry: {cache_id}")
        except Exception as e:
            pass
            # print(f"[SemanticCache] Error deleting cache entry: {e}")

    def cleanup_expired_sessions(self) -> int:
        """
        Manually cleanup expired session cache entries.

        Returns:
            Number of entries cleaned up
        """
        try:
            # Get all session cache entries
            all_results = self.collection.get(
                where={"cache_type": "session"}
            )

            if not all_results or not all_results['ids']:
                return 0

            cleaned = 0
            current_time = time.time()

            for i, cache_id in enumerate(all_results['ids']):
                metadata = all_results['metadatas'][i]
                cached_at = metadata.get("cached_at", 0)
                age_seconds = current_time - cached_at

                if age_seconds > self.session_ttl_seconds:
                    self._delete_cache_entry(cache_id)
                    cleaned += 1

            if cleaned > 0:
                pass
                # print(f"[SemanticCache] Cleaned up {cleaned} expired session entries")

            return cleaned

        except Exception as e:
            # print(f"[SemanticCache] Error during cleanup: {e}")
            return 0

    def clear_session(self, session_id: str) -> int:
        """
        Clear all cache entries for a specific session.

        Args:
            session_id: Session ID to clear

        Returns:
            Number of entries deleted
        """
        try:
            # Get all cache entries for this session
            session_results = self.collection.get(
                where={
                    "cache_type": "session",
                    "session_id": session_id
                }
            )

            if not session_results or not session_results['ids']:
                return 0

            # Delete all entries
            self.collection.delete(ids=session_results['ids'])

            # print(f"[SemanticCache] Cleared {len(session_results['ids'])} cache entries for session {session_id[:8]}...")
            return len(session_results['ids'])

        except Exception as e:
            # print(f"[SemanticCache] Error clearing session: {e}")
            return 0

    def get_cache_stats(self) -> Dict:
        """
        Get statistics about the semantic cache.

        Returns:
            Dict with cache statistics
        """
        try:
            # Get all entries
            all_entries = self.collection.get()

            total_entries = len(all_entries['ids']) if all_entries and all_entries['ids'] else 0

            # Count by type and format
            session_count = 0
            global_count = 0
            old_format_count = 0  # Track old cache entries

            if all_entries and all_entries['metadatas']:
                for metadata in all_entries['metadatas']:
                    if metadata.get("cache_type") == "session":
                        session_count += 1
                    elif metadata.get("cache_type") == "global":
                        global_count += 1

                    # Check if using old format (no 'response' in metadata)
                    if 'response' not in metadata:
                        old_format_count += 1

            return {
                "total_entries": total_entries,
                "session_entries": session_count,
                "global_entries": global_count,
                "old_format_entries": old_format_count,
                "new_format_entries": total_entries - old_format_count,
                "similarity_threshold": self.similarity_threshold,
                "session_ttl_hours": self.session_ttl_seconds / 3600,
            }

        except Exception as e:
            # print(f"[SemanticCache] Error getting stats: {e}")
            return {
                "total_entries": 0,
                "session_entries": 0,
                "global_entries": 0,
                "old_format_entries": 0,
                "new_format_entries": 0,
                "error": str(e),
            }

    def clear_all(self, confirm: bool = False) -> int:
        """
        Clear entire cache (useful after fixing embedding bug).

        Args:
            confirm: Must be True to actually clear (safety mechanism)

        Returns:
            Number of entries deleted

        Example:
            >>> cache = SemanticCache()
            >>> cache.clear_all(confirm=True)  # Clear all cache entries
            42
        """
        if not confirm:
            # print(f"[SemanticCache] ⚠️  clear_all() requires confirm=True to proceed")
            # print(f"[SemanticCache] This will delete ALL cache entries permanently!")
            return 0

        try:
            # Get count before deletion
            all_entries = self.collection.get()
            count = len(all_entries['ids']) if all_entries and all_entries['ids'] else 0

            if count == 0:
                # print(f"[SemanticCache] Cache is already empty")
                return 0

            # Delete all entries
            self.collection.delete(
                ids=all_entries['ids']
            )

            # print(f"[SemanticCache] ✅ Cleared {count} cache entries")
            return count

        except Exception as e:
            # print(f"[SemanticCache] ❌ Error clearing cache: {e}")
            return 0

    def migrate_old_entries(self) -> int:
        """
        Migrate old cache entries to new format.

        Old format: documents=[response], metadata without 'response' field
        New format: documents=[query], metadata with 'response' field

        WARNING: This is a best-effort migration. Old entries cannot be perfectly
        migrated because we don't have the original query embeddings.
        It's better to clear old cache and let it rebuild naturally.

        Returns:
            Number of entries migrated (or -1 if migration not recommended)
        """
        # print(f"[SemanticCache] ⚠️  Migration not recommended!")
        # print(f"[SemanticCache] Old cache entries embed responses (wrong format)")
        print(f"[SemanticCache] Cannot recover original query embeddings")
        # print(f"[SemanticCache] Recommendation: Use clear_all(confirm=True) instead")
        # print(f"[SemanticCache] Cache will rebuild naturally with new queries")
        return -1

    def debug_cache_entry(self, query: str, session_id: Optional[str] = None) -> Dict:
        """
        Debug a specific cache lookup to see what's happening.

        Useful for understanding why cache hits/misses occur.

        Args:
            query: Query to debug
            session_id: Optional session ID

        Returns:
            Debug information dict

        Example:
            >>> cache.debug_cache_entry("How many FFS performed?", "session123")
            {
                "query": "How many FFS performed?",
                "session_id": "session123",
                "found_matches": 2,
                "top_match": {
                    "similarity": 0.98,
                    "original_query": "How many FFS inspections?",
                    "meets_threshold": True,
                    "cached_at": "2026-01-17 20:49:31",
                    "age_hours": 2.5,
                    "is_expired": False,
                    "has_response": True,
                    "format": "new"
                }
            }
        """
        try:
            # Build filter
            if session_id:
                where_filter = {
                    "$and": [
                        {"cache_type": "session"},
                        {"session_id": session_id}
                    ]
                }
            else:
                where_filter = {"cache_type": "global"}

            # Query for matches
            results = self.collection.query(
                query_texts=[query],
                where=where_filter,
                n_results=5  # Get top 5 for debugging
            )

            debug_info = {
                "query": query,
                "session_id": session_id or "GLOBAL",
                "found_matches": 0,
                "top_match": None,
                "all_matches": []
            }

            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                debug_info["message"] = "No cache entries found"
                return debug_info

            debug_info["found_matches"] = len(results['ids'][0])

            # Analyze each match
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                similarity = 1.0 - distance

                cached_at = metadata.get("cached_at", 0)
                age_seconds = time.time() - cached_at
                age_hours = age_seconds / 3600

                is_expired = age_seconds > self.session_ttl_seconds
                has_response = 'response' in metadata
                format_type = "new" if has_response else "old"

                match_info = {
                    "rank": i + 1,
                    "similarity": round(similarity, 4),
                    "original_query": metadata.get("original_query", "")[:100],
                    "meets_threshold": similarity >= self.similarity_threshold,
                    "cached_at": datetime.fromtimestamp(cached_at).strftime("%Y-%m-%d %H:%M:%S") if cached_at > 0 else "unknown",
                    "age_hours": round(age_hours, 2),
                    "is_expired": is_expired,
                    "has_response": has_response,
                    "format": format_type,
                }

                debug_info["all_matches"].append(match_info)

                # Store top match
                if i == 0:
                    debug_info["top_match"] = match_info

            return debug_info

        except Exception as e:
            return {
                "query": query,
                "session_id": session_id,
                "error": str(e)
            }


def get_semantic_cache(
    persist_directory: Optional[str] = None,
    similarity_threshold: float = 0.96
) -> SemanticCache:
    """
    Factory function to create SemanticCache instance.

    Args:
        persist_directory: Override default directory
        similarity_threshold: Override default threshold (0.96)

    Returns:
        Configured SemanticCache instance
    """
    persist_dir = persist_directory or "./data/semantic_cache"

    return SemanticCache(
        persist_directory=persist_dir,
        similarity_threshold=similarity_threshold
    )
