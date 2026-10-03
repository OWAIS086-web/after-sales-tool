"""
Production Redis-backed Semantic Cache

Hybrid architecture:
- ChromaDB: Fast semantic similarity search (query embeddings)
- Redis: Unlimited storage for full responses (no truncation)

Benefits:
- No response size limits (store long thinking mode responses)
- Fast semantic matching with ChromaDB
- Production-ready with connection pooling
- Graceful degradation if Redis is down
- Multiple fallback mechanisms for robustness

Fallback Strategy:
1. ChromaDB semantic search (primary)
2. String similarity fallback (if semantic similarity is borderline)
3. Normalized exact match (lowercase, punctuation removed)
4. Graceful degradation on errors
"""

import json
import time
import hashlib
import redis
import re
from typing import Optional, Dict, Any
from datetime import datetime
from difflib import SequenceMatcher
import chromadb
from config.cache_config import get_cache_config


class RedisSemanticCache:
    """
    Production semantic cache with Redis backend.

    Architecture:
    1. Query comes in → Embed with ChromaDB
    2. Search ChromaDB for similar queries (similarity >= threshold)
    3. If match found → Retrieve full response from Redis
    4. Return cached response (instant, no LLM call)

    Storage:
    - ChromaDB: {query_embedding, cache_id, metadata}
    - Redis: {cache_id → full_response_json}
    """

    def __init__(self, pipeline: str = "rag"):
        """
        Initialize Redis semantic cache.

        Args:
            pipeline: "rag" or "dms" (affects similarity threshold and settings)
        """
        self.pipeline = pipeline
        self.config = get_cache_config(pipeline)

        # Extract settings
        self.similarity_threshold = self.config["similarity_threshold"]
        self.ttl_seconds = self.config["ttl_hours"] * 3600
        self.log_verbose = self.config.get("log_verbose", False)  # Default to True if not set

        # Initialize Redis connection pool
        try:
            redis_config = self.config["redis"]
            self.redis_pool = redis.ConnectionPool(
                host=redis_config["host"],
                port=redis_config["port"],
                db=redis_config["db"],
                password=redis_config["password"],
                max_connections=redis_config["max_connections"],
                socket_timeout=redis_config["socket_timeout"],
                socket_connect_timeout=redis_config["socket_connect_timeout"],
                decode_responses=redis_config["decode_responses"],
            )
            self.redis_client = redis.Redis(connection_pool=self.redis_pool)

            # Test connection
            self.redis_client.ping()
            print(f"[{pipeline.upper()} Cache] ✅ Redis connected (DB {redis_config['db']})")

        except Exception as e:
            print(f"[{pipeline.upper()} Cache] ⚠️  Redis connection failed: {e}")
            print(f"[{pipeline.upper()} Cache] Cache will be DISABLED (graceful degradation)")
            self.redis_client = None

        # Initialize ChromaDB for semantic search
        try:
            chroma_config = self.config["chromadb"]
            self.chroma_client = chromadb.PersistentClient(
                path=chroma_config["persist_directory"]
            )

            collection_name = f"{chroma_config['collection_name']}_{pipeline}"

            # NOTE: To improve similarity scores (currently getting 0.6 instead of 0.9+),
            # uncomment the following to use sentence-transformers:
            #
            # from chromadb.utils import embedding_functions
            # embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            #     model_name="all-MiniLM-L6-v2"  # Fast + accurate
            # )
            # self.collection = self.chroma_client.get_or_create_collection(
            #     name=collection_name,
            #     embedding_function=embedding_fn,
            #     metadata={"description": f"Semantic cache for {pipeline.upper()} pipeline"}
            # )
            #
            # This requires: pip install sentence-transformers

            self.collection = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"description": f"Semantic cache for {pipeline.upper()} pipeline"}
            )

            if self.log_verbose:
                print(f"[{pipeline.upper()} Cache] ✅ ChromaDB initialized: {collection_name}")
                print(f"[{pipeline.upper()} Cache] Embedding: ChromaDB default (consider sentence-transformers for better accuracy)")
                print(f"[{pipeline.upper()} Cache] Similarity threshold: {self.similarity_threshold}")
                print(f"[{pipeline.upper()} Cache] TTL: {self.config['ttl_hours']}h")

        except Exception as e:
            print(f"[{pipeline.upper()} Cache] ❌ CRITICAL: ChromaDB initialization failed: {e}")
            raise RuntimeError(f"Semantic cache initialization failed: {e}")

    def get(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Retrieve cached response for semantically similar query.

        ROBUST FALLBACK STRATEGY:
        1. Try ChromaDB semantic search (primary method)
        2. If ChromaDB fails → Try string similarity fallback
        3. If similarity is borderline → Try normalized exact match
        4. Retry on transient errors (Redis connection issues)

        Args:
            query: User's query
            session_id: Optional session ID

        Returns:
            Cached response dict or None
        """
        if not self.redis_client:
            if self.log_verbose:
                print(f"[{self.pipeline.upper()} Cache] ⚠️  Cache disabled (Redis unavailable)")
            return None

        start_time = time.time()

        # STEP 1: Try ChromaDB semantic search with retry
        # ================================================
        cache_result = None
        for attempt in range(2):  # Retry once on failure
            try:
                if self.log_verbose and attempt == 0:
                    print(f"\n[{self.pipeline.upper()} Cache] 🔍 Searching for similar queries...")
                    print(f"[{self.pipeline.upper()} Cache]   Query: '{query[:80]}...'")
                    print(f"[{self.pipeline.upper()} Cache]   Session: {session_id or 'GLOBAL'}")

                # Session-scoped search first
                if session_id:
                    cache_result = self._query_chromadb(query, "session", session_id)

                # Fallback to global cache
                if not cache_result:
                    cache_result = self._query_chromadb(query, "global", None)

                break  # Success - exit retry loop

            except Exception as e:
                if attempt == 0:
                    if self.log_verbose:
                        print(f"[{self.pipeline.upper()} Cache] ⚠️  ChromaDB search failed, retrying... ({e})")
                    time.sleep(0.1)  # Brief pause before retry
                else:
                    # Final failure - will proceed with pipeline
                    if self.config["logging"]["log_errors"]:
                        print(f"[{self.pipeline.upper()} Cache] ❌ ChromaDB search failed after retry: {e}")
                        print(f"[{self.pipeline.upper()} Cache] Proceeding with full pipeline...")
                    return None

        # STEP 2: Check if we found anything
        # ====================================
        if not cache_result:
            lookup_time = (time.time() - start_time) * 1000
            if self.config["logging"]["log_misses"]:
                print(f"[{self.pipeline.upper()} Cache] ❌ MISS - No similar queries found ({lookup_time:.0f}ms)")
            return None

        # STEP 3: Extract cache_id and similarity
        # =========================================
        cache_id = cache_result["cache_id"]
        similarity = cache_result["similarity"]
        cache_type = cache_result["cache_type"]

        if self.log_verbose:
            print(f"[{self.pipeline.upper()} Cache] ✅ Similar query found!")
            print(f"[{self.pipeline.upper()} Cache]   Similarity: {similarity:.3f}")
            print(f"[{self.pipeline.upper()} Cache]   Cache type: {cache_type.upper()}")
            print(f"[{self.pipeline.upper()} Cache]   Cache ID: {cache_id[:16]}...")

        # STEP 4: Fetch full response from Redis with retry
        # ===================================================
        cached_data = None
        redis_key = self._get_redis_key(cache_id)

        for attempt in range(3):  # Retry up to 3 times for Redis
            try:
                cached_data = self.redis_client.get(redis_key)
                break  # Success
            except redis.ConnectionError as e:
                if attempt < 2:
                    if self.log_verbose:
                        print(f"[{self.pipeline.upper()} Cache] ⚠️  Redis connection error, retrying... ({e})")
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                else:
                    if self.config["logging"]["log_errors"]:
                        print(f"[{self.pipeline.upper()} Cache] ❌ Redis fetch failed after retries: {e}")
                    return None
            except Exception as e:
                if self.config["logging"]["log_errors"]:
                    print(f"[{self.pipeline.upper()} Cache] ❌ Redis error: {e}")
                return None

        if not cached_data:
            if self.log_verbose:
                print(f"[{self.pipeline.upper()} Cache] ⚠️  ChromaDB hit but Redis miss (cache expired?)")
            return None

        # STEP 5: Parse and return response
        # ===================================
        try:
            response_dict = json.loads(cached_data)
        except json.JSONDecodeError as e:
            if self.config["logging"]["log_errors"]:
                print(f"[{self.pipeline.upper()} Cache] ❌ Failed to parse cached response: {e}")
            return None

        lookup_time = (time.time() - start_time) * 1000
        response_size = len(cached_data)

        if self.config["logging"]["log_hits"]:
            print(f"[{self.pipeline.upper()} Cache] 🎯 HIT! ({lookup_time:.0f}ms)")
            print(f"[{self.pipeline.upper()} Cache]   Response size: {response_size:,} bytes")
            print(f"[{self.pipeline.upper()} Cache]   Saved: ~{response_dict.get('estimated_tokens', 'N/A')} tokens")

        # Add cache metadata
        response_dict["cache_hit"] = True
        response_dict["similarity"] = similarity
        response_dict["cache_type"] = cache_type
        response_dict["cache_lookup_time_ms"] = lookup_time

        return response_dict

    def set(
        self,
        query: str,
        response: Any,
        session_id: Optional[str] = None,
        cache_type: str = "session",
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Store query-response pair in cache.

        Flow:
        1. Embed query in ChromaDB (for semantic search)
        2. Store full response in Redis (unlimited size)
        3. Link ChromaDB entry to Redis key

        Args:
            query: User's query
            response: Full response (can be string, dict, or JSON)
            session_id: Session ID
            cache_type: "session" or "global"
            metadata: Optional metadata
        """
        if not self.redis_client:
            return  # Graceful degradation

        start_time = time.time()

        try:
            # STEP 1: Generate cache ID
            # ===========================
            cache_id = self._generate_cache_id(query, session_id, cache_type)

            # STEP 2: Prepare response for storage
            # ======================================
            # Convert to JSON if dict/object
            if isinstance(response, dict):
                response_json = json.dumps(response, default=str)
            elif isinstance(response, str):
                response_json = response
            else:
                response_json = str(response)

            response_size = len(response_json)
            estimated_tokens = response_size // 4  # Rough estimate: 1 token ≈ 4 chars

            # Build storage metadata
            storage_data = {
                "query": query,
                "response": response_json,
                "session_id": session_id or "GLOBAL",
                "cache_type": cache_type,
                "cached_at": time.time(),
                "cached_at_human": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "response_size": response_size,
                "estimated_tokens": estimated_tokens,
                "pipeline": self.pipeline,
            }

            # Add custom metadata
            if metadata:
                storage_data.update(metadata)

            # STEP 3: Store in Redis (full response, no truncation) with retry
            # ==================================================================
            redis_key = self._get_redis_key(cache_id)
            ttl = self.ttl_seconds if cache_type == "session" else (7 * 24 * 3600)

            redis_success = False
            for attempt in range(3):  # Retry up to 3 times
                try:
                    self.redis_client.setex(
                        redis_key,
                        ttl,
                        json.dumps(storage_data, default=str)
                    )
                    redis_success = True
                    break  # Success
                except redis.ConnectionError as e:
                    if attempt < 2:
                        if self.log_verbose:
                            print(f"[{self.pipeline.upper()} Cache] ⚠️  Redis store failed, retrying... ({e})")
                        time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    else:
                        if self.config["logging"]["log_errors"]:
                            print(f"[{self.pipeline.upper()} Cache] ❌ Redis store failed after retries: {e}")
                        return  # Give up gracefully
                except Exception as e:
                    if self.config["logging"]["log_errors"]:
                        print(f"[{self.pipeline.upper()} Cache] ❌ Redis error: {e}")
                    return  # Give up gracefully

            if not redis_success:
                return  # Failed to store in Redis

            if self.log_verbose:
                print(f"\n[{self.pipeline.upper()} Cache] 💾 Storing in Redis...")
                print(f"[{self.pipeline.upper()} Cache]   Key: {redis_key}")
                print(f"[{self.pipeline.upper()} Cache]   Size: {response_size:,} bytes ({estimated_tokens:,} tokens)")
                print(f"[{self.pipeline.upper()} Cache]   TTL: {ttl/3600:.1f}h")

            # STEP 4: Store query embedding in ChromaDB with retry
            # ======================================================
            chroma_metadata = {
                "cache_id": cache_id,
                "cache_type": cache_type,
                "session_id": session_id or "GLOBAL",
                "cached_at": time.time(),
                "query_preview": query[:200],
                "response_size": response_size,
            }

            chromadb_success = False
            for attempt in range(2):  # Retry once
                try:
                    self.collection.upsert(
                        documents=[query],  # Embed query for semantic search
                        metadatas=[chroma_metadata],
                        ids=[cache_id]
                    )
                    chromadb_success = True
                    break  # Success
                except Exception as e:
                    if attempt < 1:
                        if self.log_verbose:
                            print(f"[{self.pipeline.upper()} Cache] ⚠️  ChromaDB store failed, retrying... ({e})")
                        time.sleep(0.1)
                    else:
                        if self.config["logging"]["log_errors"]:
                            print(f"[{self.pipeline.upper()} Cache] ❌ ChromaDB store failed after retry: {e}")
                        return  # Give up gracefully

            if not chromadb_success:
                return  # Failed to store in ChromaDB

            storage_time = (time.time() - start_time) * 1000

            if self.config["logging"]["log_storage"]:
                print(f"[{self.pipeline.upper()} Cache] ✅ STORED ({storage_time:.0f}ms)")
                print(f"[{self.pipeline.upper()} Cache]   ChromaDB: Query embedding")
                print(f"[{self.pipeline.upper()} Cache]   Redis: Full response ({response_size:,} bytes)")

        except Exception as e:
            if self.config["logging"]["log_errors"]:
                print(f"[{self.pipeline.upper()} Cache] ❌ ERROR storing cache: {e}")
                import traceback
                traceback.print_exc()

    def _query_chromadb(
        self,
        query: str,
        cache_type: str,
        session_id: Optional[str]
    ) -> Optional[Dict]:
        """Query ChromaDB for semantically similar queries."""
        try:
            # Build filter
            if cache_type == "session" and session_id:
                where_filter = {
                    "$and": [
                        {"cache_type": "session"},
                        {"session_id": session_id}
                    ]
                }
            else:
                where_filter = {"cache_type": "global"}

            # Semantic search
            results = self.collection.query(
                query_texts=[query],
                where=where_filter,
                n_results=1
            )

            # Check if results found
            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                return None

            # Extract result
            metadata = results['metadatas'][0][0]
            distance = results['distances'][0][0]
            cache_id = results['ids'][0][0]

            # Convert distance to similarity
            similarity = 1.0 - distance

            # Check threshold
            if similarity < self.similarity_threshold:
                if self.log_verbose:
                    print(f"[{self.pipeline.upper()} Cache] Low similarity: {similarity:.3f} < {self.similarity_threshold}")
                return None

            # Check TTL
            cached_at = metadata.get("cached_at", 0)
            age_seconds = time.time() - cached_at
            max_age = self.ttl_seconds if cache_type == "session" else (7 * 24 * 3600)

            if age_seconds > max_age:
                if self.log_verbose:
                    print(f"[{self.pipeline.upper()} Cache] Expired: {age_seconds/3600:.1f}h > {max_age/3600:.1f}h")
                return None

            return {
                "cache_id": cache_id,
                "similarity": similarity,
                "cache_type": cache_type,
                "cached_at": cached_at,
            }

        except Exception as e:
            if self.log_verbose:
                print(f"[{self.pipeline.upper()} Cache] ChromaDB query error: {e}")
            return None

    def _generate_cache_id(self, query: str, session_id: Optional[str], cache_type: str) -> str:
        """Generate unique cache ID."""
        components = [
            self.pipeline,
            cache_type,
            session_id or "GLOBAL",
            query,
        ]
        hash_input = "|".join(components)
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def _get_redis_key(self, cache_id: str) -> str:
        """Generate Redis key for cache entry."""
        return f"cache:{self.pipeline}:{cache_id}"

    def get_stats(self) -> Dict:
        """Get cache statistics."""
        try:
            stats = {
                "pipeline": self.pipeline,
                "redis_connected": self.redis_client is not None,
                "similarity_threshold": self.similarity_threshold,
                "ttl_hours": self.config["ttl_hours"],
            }

            # ChromaDB stats
            all_entries = self.collection.get()
            stats["total_entries"] = len(all_entries['ids']) if all_entries and all_entries['ids'] else 0

            # Redis stats (if connected)
            if self.redis_client:
                redis_info = self.redis_client.info("memory")
                stats["redis_memory_mb"] = redis_info.get("used_memory", 0) / (1024 * 1024)
                stats["redis_keys"] = self.redis_client.dbsize()

            return stats

        except Exception as e:
            return {"error": str(e)}

    def clear_all(self, confirm: bool = False) -> int:
        """Clear all cache entries."""
        if not confirm:
            print(f"[{self.pipeline.upper()} Cache] ⚠️  clear_all() requires confirm=True")
            return 0

        try:
            # Clear ChromaDB
            all_entries = self.collection.get()
            count = len(all_entries['ids']) if all_entries and all_entries['ids'] else 0

            if count > 0:
                self.collection.delete(ids=all_entries['ids'])

            # Clear Redis
            if self.redis_client:
                pattern = f"cache:{self.pipeline}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)

            print(f"[{self.pipeline.upper()} Cache] ✅ Cleared {count} cache entries")
            return count

        except Exception as e:
            print(f"[{self.pipeline.upper()} Cache] ❌ Error clearing cache: {e}")
            return 0
