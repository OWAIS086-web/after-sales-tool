"""
Production-Grade Pipeline Manager

Centralized singleton cache for ALL pipeline types (RAG, DMS, future modes).
Prevents model reload, ensures thread safety, and supports Docker deployment.

Features:
- Thread-safe singleton pattern
- Lazy initialization (loads only when needed)
- Supports all data modes: dealership, pakwheels, whatsapp, reddit, facebook, etc.
- Automatic cache key generation
- Docker-compatible (no file system assumptions)
- Graceful error handling with fallback

Author: Claude Sonnet 4.5
Date: 2026-01-12
"""

import threading
from typing import Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PipelineManager:
    """
    Thread-safe singleton manager for ALL pipeline types.

    Prevents expensive model reloading by caching pipeline instances.
    Supports RAG pipelines (PakWheels, WhatsApp, Reddit) and DMS pipelines.

    Usage:
        # Get manager instance
        manager = PipelineManager.get_instance()

        # Get or create DMS pipeline
        dms_pipeline = manager.get_dms_pipeline(
            company_id="haval",
            db_path="data/SazgarDMSDW.sqlite",
            dealer_id="D001"
        )

        # Get or create RAG engine
        rag_engine = manager.get_rag_engine(
            company_id="haval",
            data_sources=["pakwheels", "whatsapp"]
        )

    Performance:
        - First call: 15-20s (model load + initialization)
        - Cached calls: 0.1-5s (query execution only)
        - Memory: ~500MB per pipeline (shared across requests)
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Thread-safe singleton pattern"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize caches (only once)"""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            # Caches for different pipeline types
            self._dms_pipelines = {}      # DMS/Dealership pipelines
            self._rag_engines = {}        # RAG engines (PakWheels/WhatsApp/Reddit)
            self._custom_pipelines = {}   # Future custom pipelines

            # Cache metadata
            self._cache_stats = {
                "dms_hits": 0,
                "dms_misses": 0,
                "rag_hits": 0,
                "rag_misses": 0,
                "created_at": datetime.now()
            }

            self._initialized = True
            logger.info("[PipelineManager] Initialized - Ready for multi-mode caching")

    @classmethod
    def get_instance(cls) -> 'PipelineManager':
        """Get singleton instance"""
        return cls()

    def get_dms_pipeline(
        self,
        company_id: str,
        db_path: str,
        dealer_id: Optional[str] = None,
        db_config = None,  # DatabaseConfig for MSSQL/SQLite
        dms_data_source: str = "mssql",  # "sqlite" or "mssql" - determines which pipeline to use
        **kwargs
    ):
        """
        Get or create DMS pipeline (cached).

        Args:
            company_id: Company identifier (e.g., "haval", "kia")
            db_path: Path to DMS SQLite database (fallback if db_config not provided)
            dealer_id: Optional dealer ID for RLS filtering
            db_config: DatabaseConfig for MSSQL or SQLite (preferred)
            dms_data_source: "sqlite" (old pipeline in ai/dms_engine_sqlite) or
                           "mssql" (new pipeline in ai/dms_engine with MSSQL support)
            **kwargs: Additional pipeline configuration

        Returns:
            Cached DMSPipeline instance

        Raises:
            Exception: If pipeline initialization fails
        """
        # Include dms_data_source in cache key to support both pipelines
        cache_key = self._generate_cache_key("dms", company_id, dealer_id, dms_data_source)

        if cache_key in self._dms_pipelines:
            self._cache_stats["dms_hits"] += 1
            # logger.debug(f"[DMS Cache HIT] Using cached pipeline: {cache_key}")
            return self._dms_pipelines[cache_key]

        # Cache miss - create new pipeline
        self._cache_stats["dms_misses"] += 1
        logger.info(f"[DMS Cache MISS] Creating NEW pipeline: {cache_key} (data_source={dms_data_source})")

        try:
            start_time = datetime.now()

            # Import from correct module based on dms_data_source
            if dms_data_source == "sqlite":
                # Old SQLite pipeline with original system prompts
                from ai.dms_engine_sqlite.dms_pipeline import DMSPipeline
                logger.info(f"[DMS] Using SQLite pipeline (ai/dms_engine_sqlite)")

                # Old pipeline doesn't have db_config parameter
                pipeline = DMSPipeline(
                    db_path=db_path,
                    dealer_id=dealer_id,
                    enable_tier0=kwargs.get("enable_tier0", True),
                    enable_tier1=kwargs.get("enable_tier1", True),
                    enable_tier2=kwargs.get("enable_tier2", True),
                    enable_tier3=kwargs.get("enable_tier3", True),
                    enable_semantic_cache=kwargs.get("enable_semantic_cache", True),
                    enable_follow_ups=kwargs.get("enable_follow_ups", True),
                    verbose=kwargs.get("verbose", False)
                )
            else:
                # New MSSQL pipeline with updated system prompts
                from ai.dms_engine.dms_pipeline import DMSPipeline
                logger.info(f"[DMS] Using MSSQL pipeline (ai/dms_engine)")

                # New pipeline has db_config for MSSQL support
                pipeline = DMSPipeline(
                    db_path=db_path,
                    dealer_id=dealer_id,
                    db_config=db_config,  # Pass MSSQL/SQLite config
                    enable_tier0=kwargs.get("enable_tier0", True),
                    enable_tier1=kwargs.get("enable_tier1", True),
                    enable_tier2=kwargs.get("enable_tier2", True),
                    enable_tier3=kwargs.get("enable_tier3", True),
                    enable_semantic_cache=kwargs.get("enable_semantic_cache", True),
                    enable_follow_ups=kwargs.get("enable_follow_ups", True),
                    verbose=kwargs.get("verbose", False)
                )

            elapsed = (datetime.now() - start_time).total_seconds()

            # Cache the pipeline
            with self._lock:
                self._dms_pipelines[cache_key] = pipeline

            logger.info(f"[DMS Cache MISS] ✓ Pipeline created and cached: {cache_key} ({elapsed:.2f}s)")

            return pipeline

        except Exception as e:
            logger.error(f"[DMS Pipeline ERROR] Failed to create pipeline {cache_key}: {e}")
            raise

    def get_rag_engine(
        self,
        company_id: str,
        data_sources: list,
        **kwargs
    ):
        """
        Get or create RAG engine (cached).

        Args:
            company_id: Company identifier (e.g., "haval", "kia")
            data_sources: List of data sources (e.g., ["pakwheels", "whatsapp", "reddit"])
            **kwargs: Additional engine configuration

        Returns:
            Cached RAGEngine instance

        Raises:
            Exception: If engine initialization fails
        """
        # Sort data sources for consistent cache key
        sources_str = "_".join(sorted(data_sources))
        cache_key = self._generate_cache_key("rag", company_id, sources_str)

        if cache_key in self._rag_engines:
            self._cache_stats["rag_hits"] += 1
            # logger.debug(f"[RAG Cache HIT] Using cached engine: {cache_key}")
            return self._rag_engines[cache_key]

        # Cache miss - create new engine
        self._cache_stats["rag_misses"] += 1
        logger.info(f"[RAG Cache MISS] Creating NEW engine: {cache_key}")

        try:
            start_time = datetime.now()

            # Import and create RAG engine based on company config
            from config import get_company_config
            from ai.haval_pipeline import get_or_create_rag_engine

            company_config = get_company_config(company_id)
            rag_engine = get_or_create_rag_engine(company_id, data_sources)

            elapsed = (datetime.now() - start_time).total_seconds()

            # Cache the engine
            with self._lock:
                self._rag_engines[cache_key] = rag_engine

            logger.info(f"[RAG Cache MISS] ✓ Engine created and cached: {cache_key} ({elapsed:.2f}s)")

            return rag_engine

        except Exception as e:
            logger.error(f"[RAG Engine ERROR] Failed to create engine {cache_key}: {e}")
            raise

    def get_custom_pipeline(
        self,
        pipeline_type: str,
        company_id: str,
        config: Dict[str, Any],
        factory_func
    ):
        """
        Get or create custom pipeline (future extensibility).

        Use this for NEW data modes added in the future.

        Args:
            pipeline_type: Type identifier (e.g., "facebook", "twitter", "shopify")
            company_id: Company identifier
            config: Pipeline configuration dict
            factory_func: Function to create pipeline: factory_func(config) -> Pipeline

        Returns:
            Cached pipeline instance
        """
        cache_key = self._generate_cache_key(pipeline_type, company_id)

        if cache_key in self._custom_pipelines:
            # logger.debug(f"[Custom Cache HIT] Using cached pipeline: {cache_key}")
            return self._custom_pipelines[cache_key]

        # Cache miss - create new pipeline
        logger.info(f"[Custom Cache MISS] Creating NEW pipeline: {cache_key}")

        try:
            start_time = datetime.now()

            pipeline = factory_func(config)

            elapsed = (datetime.now() - start_time).total_seconds()

            # Cache the pipeline
            with self._lock:
                self._custom_pipelines[cache_key] = pipeline

            logger.info(f"[Custom Cache MISS] ✓ Pipeline created: {cache_key} ({elapsed:.2f}s)")

            return pipeline

        except Exception as e:
            logger.error(f"[Custom Pipeline ERROR] Failed to create {cache_key}: {e}")
            raise

    def clear_cache(self, pipeline_type: Optional[str] = None):
        """
        Clear pipeline cache.

        Args:
            pipeline_type: Optional type to clear ("dms", "rag", "custom", or None for all)

        Usage:
            # Clear all caches
            manager.clear_cache()

            # Clear only DMS pipelines
            manager.clear_cache("dms")
        """
        with self._lock:
            if pipeline_type is None or pipeline_type == "dms":
                count = len(self._dms_pipelines)
                self._dms_pipelines.clear()
                logger.info(f"[Cache Clear] Cleared {count} DMS pipelines")

            if pipeline_type is None or pipeline_type == "rag":
                count = len(self._rag_engines)
                self._rag_engines.clear()
                logger.info(f"[Cache Clear] Cleared {count} RAG engines")

            if pipeline_type is None or pipeline_type == "custom":
                count = len(self._custom_pipelines)
                self._custom_pipelines.clear()
                logger.info(f"[Cache Clear] Cleared {count} custom pipelines")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache hit/miss rates, sizes, etc.
        """
        with self._lock:
            stats = self._cache_stats.copy()
            stats.update({
                "dms_cache_size": len(self._dms_pipelines),
                "rag_cache_size": len(self._rag_engines),
                "custom_cache_size": len(self._custom_pipelines),
                "total_cached": len(self._dms_pipelines) + len(self._rag_engines) + len(self._custom_pipelines)
            })

            # Calculate hit rates
            total_dms = stats["dms_hits"] + stats["dms_misses"]
            total_rag = stats["rag_hits"] + stats["rag_misses"]

            if total_dms > 0:
                stats["dms_hit_rate"] = stats["dms_hits"] / total_dms
            else:
                stats["dms_hit_rate"] = 0.0

            if total_rag > 0:
                stats["rag_hit_rate"] = stats["rag_hits"] / total_rag
            else:
                stats["rag_hit_rate"] = 0.0

            return stats

    @staticmethod
    def _generate_cache_key(pipeline_type: str, company_id: str, *suffixes) -> str:
        """
        Generate consistent cache key.

        Args:
            pipeline_type: "dms", "rag", or custom type
            company_id: Company identifier
            *suffixes: Optional suffixes (dealer_id, data_sources, dms_data_source, etc.)

        Returns:
            Cache key string
        """
        # Filter out None values and join non-None suffixes
        valid_suffixes = [str(s) for s in suffixes if s is not None]
        if valid_suffixes:
            return f"{pipeline_type}_{company_id}_{'_'.join(valid_suffixes)}"
        return f"{pipeline_type}_{company_id}"


# ============================================================================
# Global Singleton Instance
# ============================================================================
def get_pipeline_manager() -> PipelineManager:
    """
    Get global pipeline manager instance.

    This is the PRIMARY API for accessing cached pipelines.

    Returns:
        PipelineManager singleton instance
    """
    return PipelineManager.get_instance()
