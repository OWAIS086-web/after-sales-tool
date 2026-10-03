"""
Production Semantic Cache Configuration

Configurable cache settings for RAG and DMS pipelines.
Redis-backed for unlimited response storage.
"""
import os

CACHE_CONFIG = {
    # RAG Pipeline Cache Settings (PakWheels, Reddit, WhatsApp)
    "rag": {
        "enabled": True,
        "similarity_threshold": 0.85,  # More lenient for RAG (85% similarity)
        "ttl_hours": 10,  # Session cache expires after 24h
        "backend": "redis",  # Use Redis for unlimited storage
        "max_response_size": None,  # No size limit with Redis
        "log_verbose": False,  # Detailed logging
    },

    # DMS Pipeline Cache Settings (Dealership Database)
    "dms": {
        "enabled": True,
        "similarity_threshold": 0.96,  # Strict for DMS (96% similarity)
        "ttl_hours": 24,  # Session cache expires after 24h
        "backend": "redis",  # Use Redis for unlimited storage
        "max_response_size": None,  # No size limit with Redis
        "log_verbose": False,  # Detailed logging

        # Additional DMS optimizations
        "cache_schema_relevance": True,  # Cache expensive schema calculations
        "cache_reformulations": True,  # Cache query reformulations
    },

    # Redis Connection Settings
    "redis": {
        "host": os.getenv("REDIS_HOST", "localhost"),  # Use 'redis' in Docker
        "port": int(os.getenv("REDIS_PORT", "6379")),
        "db": 1,  # Use DB 1 for semantic cache (DB 0 is conversational memory)
        "password": None,  # No password for local development
        "socket_timeout": 5,
        "socket_connect_timeout": 5,
        "max_connections": 50,  # Connection pool size
        "decode_responses": True,  # Auto-decode bytes to strings
    },

    # ChromaDB Settings (for semantic similarity search)
    "chromadb": {
        "persist_directory": "./data/semantic_cache",
        "collection_name": "semantic_cache_v2",
    },

    # Global Cache Settings
    "global": {
        "global_faq_ttl_days": 7,  # Global FAQ cache expires after 7 days
        "cleanup_interval_hours": 6,  # Clean expired entries every 6 hours
        "max_memory_mb": 512,  # Alert if Redis cache exceeds 512MB
    },

    # Logging Settings
    "logging": {
        "log_hits": False,  # Log cache hits
        "log_misses": False,  # Log cache misses
        "log_storage": True,  # Log cache storage operations
        "log_errors": True,  # Log cache errors
        "log_performance": True,  # Log performance metrics
    }
}


def get_cache_config(pipeline: str = "rag") -> dict:
    """
    Get cache configuration for a specific pipeline.

    Args:
        pipeline: "rag" or "dms"

    Returns:
        Cache configuration dict

    Example:
        >>> config = get_cache_config("rag")
        >>> config["similarity_threshold"]
        0.85
    """
    if pipeline not in ["rag", "dms"]:
        raise ValueError(f"Invalid pipeline: {pipeline}. Must be 'rag' or 'dms'")

    # Merge pipeline-specific config with global settings
    config = CACHE_CONFIG[pipeline].copy()
    config.update({
        "redis": CACHE_CONFIG["redis"],
        "chromadb": CACHE_CONFIG["chromadb"],
        "global": CACHE_CONFIG["global"],
        "logging": CACHE_CONFIG["logging"],
    })

    return config


def is_cache_enabled(pipeline: str = "rag") -> bool:
    """Check if cache is enabled for a pipeline."""
    return CACHE_CONFIG.get(pipeline, {}).get("enabled", False)


def get_similarity_threshold(pipeline: str = "rag") -> float:
    """Get similarity threshold for a pipeline."""
    return CACHE_CONFIG.get(pipeline, {}).get("similarity_threshold", 0.96)


def get_ttl_seconds(pipeline: str = "rag") -> int:
    """Get TTL in seconds for a pipeline."""
    hours = CACHE_CONFIG.get(pipeline, {}).get("ttl_hours", 24)
    return hours * 3600
