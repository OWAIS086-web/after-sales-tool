# ai/haval_pipeline.py
from __future__ import annotations

import json
import logging
import os
import pickle
import traceback
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

from datetime import datetime, timezone

from ai.embeddings import SentenceTransformerEmbedder
from ai.enrichment import (EnrichmentMetrics, EnrichmentState, classify_blocks,
                           compute_enrichment_metrics)
from ai.io_utils import load_raw_posts_from_json
from ai.llm_client import GeminiClient, GrokClient
from ai.rag_engine import RAGEngine
from ai.reply_merge import group_posts_into_conversation_blocks
from ai.text_cleaning import raw_to_clean_posts
from ai.time_analytics import compute_daily_stats, compute_weekly_stats
from ai.utils.facebook_data import facebook_posts_to_conversation_blocks
from ai.utils.whatsapp_data import (merge_whatsapp_blocks,
                                    whatsapp_json_to_conversation_blocks)
from ai.vector_store import ChromaVectorStore
from config import get_llm_for_component

logger = logging.getLogger(__name__)

# NEW: backend-only toggle (no UI)
ENABLE_ENRICHMENT = os.getenv("HAVAL_ENABLE_ENRICHMENT", "1").lower() in (
    "1",
    "true",
    "yes",
    "on",
)

_enrichment_state = EnrichmentState()


_status_lock = Lock()

# Internal global state for this demo
_pipeline_status: Dict[str, Any] = {
    "status": "idle",       # idle | processing | enriching | indexing | separating_mixed_blocks | ready | failed
    "error": None,
    "topic_url": None,
    "json_path": None,
    "total_posts": 0,
    "total_blocks": 0,
    "enrichment_metrics": None,
    "current_step": None,
}

_rag_engine: Optional[RAGEngine] = None
_blocks: List[Any] = []
_daily_stats: List[Any] = []
_weekly_stats: List[Any] = []
_chat_history: Dict[str, List[Dict[str, str]]] = {}

# Multi-company support: Store vector stores per company
_company_vector_stores: Dict[str, Dict[str, ChromaVectorStore]] = {}
_company_rag_engines: Dict[str, RAGEngine] = {}

# Default paths for Haval (backward compatibility)
pakwheels_persist_path = "data/chroma_pakwheels"
whatsapp_persist_path = "data/chroma_whatsapp"
Path(pakwheels_persist_path).mkdir(parents=True, exist_ok=True)
Path(whatsapp_persist_path).mkdir(parents=True, exist_ok=True)
Path("data").mkdir(parents=True, exist_ok=True)

STATE_FILE = Path("data") / "haval_h6_pipeline_state.pkl"

# Global embedder (shared across all companies)
embedder = SentenceTransformerEmbedder()
# print("[HavalPipeline] Embedder initialized.")

# Initialize default Haval vector stores (backward compatibility)
pakwheels_vs = ChromaVectorStore(
    persist_path=pakwheels_persist_path,
    collection_name="pakwheels_blocks",
    embedder=embedder,
    blocks_file="data/pakwheels_blocks.pkl",
)

whatsapp_vs = ChromaVectorStore(
    persist_path=whatsapp_persist_path,
    collection_name="whatsapp_blocks",
    embedder=embedder,
    blocks_file="data/whatsapp_blocks.pkl",
)

# Initialize Reddit vector store for Haval
reddit_persist_path = "data/chroma_reddit"
Path(reddit_persist_path).mkdir(parents=True, exist_ok=True)

reddit_vs = ChromaVectorStore(
    persist_path=reddit_persist_path,
    collection_name="reddit_blocks",
    embedder=embedder,
    blocks_file="data/reddit_blocks_haval.pkl",
)

# Auto-index Reddit data if not already indexed
try:
    blocks_in_memory = len(reddit_vs.blocks_by_id)
    blocks_in_chroma = reddit_vs.collection.count()
    
    if blocks_in_memory > 0 and blocks_in_chroma == 0:
        # print(f"[HavalPipeline] Auto-indexing {blocks_in_memory} Reddit blocks into ChromaDB...")
        reddit_vs.index_blocks(list(reddit_vs.blocks_by_id.values()))
        # print(f"[HavalPipeline] ✅ Reddit data indexed successfully ({reddit_vs.collection.count()} blocks)")
    elif blocks_in_chroma > 0:
        # print(f"[HavalPipeline] Reddit store ready with {blocks_in_chroma} blocks indexed")
        pass
except Exception as e:
    # print(f"[HavalPipeline] Warning: Reddit auto-indexing failed: {e}")
    pass

# Initialize Lucid vector store for Haval
lucid_persist_path = "data/chroma_lucid"
Path(lucid_persist_path).mkdir(parents=True, exist_ok=True)

lucid_vs = ChromaVectorStore(
    persist_path=lucid_persist_path,
    collection_name="lucid_blocks",
    embedder=embedder,
    blocks_file="data/lucid_blocks.pkl",
)

# Auto-index Lucid data if not already indexed
try:
    blocks_in_memory = len(lucid_vs.blocks_by_id)
    blocks_in_chroma = lucid_vs.collection.count()
    
    if blocks_in_memory > 0 and blocks_in_chroma == 0:
        # print(f"[HavalPipeline] Auto-indexing {blocks_in_memory} Lucid blocks into ChromaDB...")
        lucid_vs.index_blocks(list(lucid_vs.blocks_by_id.values()))
        # print(f"[HavalPipeline] ✅ Lucid data indexed successfully ({lucid_vs.collection.count()} blocks)")
    elif blocks_in_chroma > 0:
        # print(f"[HavalPipeline] Lucid store ready with {blocks_in_chroma} blocks indexed")
        pass
except Exception as e:
    # print(f"[HavalPipeline] Warning: Lucid auto-indexing failed: {e}")
    pass

# Register Haval stores
_company_vector_stores["haval"] = {
    "pakwheels": pakwheels_vs,
    "whatsapp": whatsapp_vs,
    "reddit": reddit_vs,
    "lucid": lucid_vs,
}

# Initialize Lucid company vector stores (Lucid has Lucid Forum and Reddit Lucid data)
lucid_company_lucid_persist_path = "data/chroma_lucid"
Path(lucid_company_lucid_persist_path).mkdir(parents=True, exist_ok=True)

lucid_company_lucid_vs = ChromaVectorStore(
    persist_path=lucid_company_lucid_persist_path,
    collection_name="lucid_blocks",
    embedder=embedder,
    blocks_file="data/lucid_blocks.pkl",
)

# Auto-index Lucid company data if not already indexed
try:
    blocks_in_memory = len(lucid_company_lucid_vs.blocks_by_id)
    blocks_in_chroma = lucid_company_lucid_vs.collection.count()
    
    if blocks_in_memory > 0 and blocks_in_chroma == 0:
        # print(f"[LucidPipeline] Auto-indexing {blocks_in_memory} Lucid blocks into ChromaDB...")
        lucid_company_lucid_vs.index_blocks(list(lucid_company_lucid_vs.blocks_by_id.values()))
        # print(f"[LucidPipeline] ✅ Lucid data indexed successfully ({lucid_company_lucid_vs.collection.count()} blocks)")
    elif blocks_in_chroma > 0:
        pass
        # print(f"[LucidPipeline] Lucid store ready with {blocks_in_chroma} blocks indexed")
except Exception as e:
    # print(f"[LucidPipeline] Warning: Lucid auto-indexing failed: {e}")
    pass

# Initialize Reddit Lucid store for Lucid company
lucid_company_reddit_lucid_persist_path = "data/chroma_reddit_lucid"
Path(lucid_company_reddit_lucid_persist_path).mkdir(parents=True, exist_ok=True)

lucid_company_reddit_lucid_vs = ChromaVectorStore(
    persist_path=lucid_company_reddit_lucid_persist_path,
    collection_name="lucid_reddit_lucid_blocks",
    embedder=embedder,
    blocks_file="data/reddit_blocks_lucid.pkl",  # Use existing reddit_blocks_lucid.pkl file
)

# Auto-index Reddit Lucid data if not already indexed
try:
    blocks_in_memory = len(lucid_company_reddit_lucid_vs.blocks_by_id)
    blocks_in_chroma = lucid_company_reddit_lucid_vs.collection.count()
    
    # print(f"[LucidPipeline] Reddit Lucid store status: {blocks_in_memory} blocks in memory, {blocks_in_chroma} in ChromaDB")
    
    if blocks_in_memory > 0 and blocks_in_chroma == 0:
        # print(f"[LucidPipeline] Auto-indexing {blocks_in_memory} Reddit Lucid blocks into ChromaDB...")
        lucid_company_reddit_lucid_vs.index_blocks(list(lucid_company_reddit_lucid_vs.blocks_by_id.values()))
        blocks_in_chroma_after = lucid_company_reddit_lucid_vs.collection.count()
        # print(f"[LucidPipeline] [OK] Reddit Lucid data indexed successfully ({blocks_in_chroma_after} blocks)")
        if blocks_in_chroma_after == 0:
            # print(f"[LucidPipeline] [WARNING] Indexing reported success but ChromaDB still shows 0 blocks!")
            pass
    elif blocks_in_chroma > 0:
        pass
        # print(f"[LucidPipeline] Reddit Lucid store ready with {blocks_in_chroma} blocks indexed")
    else:
        pass
        # print(f"[LucidPipeline] [WARNING] No Reddit Lucid blocks found in memory or ChromaDB!")
except Exception as e:
    # print(f"[LucidPipeline] [ERROR] Reddit Lucid auto-indexing failed: {e}")
    import traceback
    traceback.print_exc()

# Register Lucid company stores (Lucid Forum + Reddit Lucid data)
_company_vector_stores["lucid"] = {
    "lucid": lucid_company_lucid_vs,
    "reddit_lucid": lucid_company_reddit_lucid_vs,  # Use reddit_lucid key for consistency
}


def get_or_create_vector_store(company_id: str, source_type: str) -> Optional[ChromaVectorStore]:
    """
    Get or create a vector store for a specific company and source type.

    Args:
        company_id: Company identifier (e.g., "haval", "kia", "toyota")
        source_type: Source type ("pakwheels" or "whatsapp")

    Returns:
        ChromaVectorStore instance or None if not applicable
    """
    try:
        from config import get_company_config
        config = get_company_config(company_id)
    except Exception as e:
        # logger.error(f"Failed to get company config for {company_id}: {e}")
        return None

    # Check if company already has this vector store initialized
    if company_id in _company_vector_stores:
        if source_type in _company_vector_stores[company_id]:
            return _company_vector_stores[company_id][source_type]

    # Validate that the source is available for this company
    if source_type == "pakwheels" and not config.has_pakwheels:
        return None
    if source_type == "whatsapp" and not config.has_whatsapp:
        return None
    if source_type == "lucid" and not config.has_lucid:
        return None
    if source_type == "reddit_lucid" and not config.has_lucid:
        return None

    # Get paths from config
    if source_type == "pakwheels":
        persist_path = config.chroma_pakwheels_path
        blocks_file = config.pakwheels_blocks_file
        collection_name = f"{company_id}_pakwheels_blocks"
    elif source_type == "whatsapp":
        persist_path = config.chroma_whatsapp_path
        blocks_file = config.whatsapp_blocks_file
        collection_name = f"{company_id}_whatsapp_blocks"
    elif source_type == "reddit":
        persist_path = config.chroma_reddit_path
        blocks_file = config.reddit_blocks_file if hasattr(config, 'reddit_blocks_file') else f"data/reddit_blocks_{company_id}.pkl"
        collection_name = f"{company_id}_reddit_blocks"
    elif source_type == "reddit_lucid":
        persist_path = config.chroma_reddit_lucid_path if hasattr(config, 'chroma_reddit_lucid_path') else f"data/chroma_reddit_lucid"
        blocks_file = config.reddit_lucid_blocks_file if hasattr(config, 'reddit_lucid_blocks_file') else f"data/reddit_lucid_blocks_{company_id}.pkl"
        collection_name = f"{company_id}_reddit_lucid_blocks"
    elif source_type == "lucid":
        persist_path = config.chroma_lucid_path
        blocks_file = config.lucid_blocks_file if hasattr(config, 'lucid_blocks_file') else f"data/lucid_blocks_{company_id}.pkl"
        collection_name = f"{company_id}_lucid_blocks"
    else:
        # logger.error(f"Unknown source type: {source_type}")
        return None

    if not persist_path or not blocks_file:
        return None

    # Create directory if it doesn't exist
    Path(persist_path).mkdir(parents=True, exist_ok=True)

    # Create vector store
    try:
        vs = ChromaVectorStore(
            persist_path=persist_path,
            collection_name=collection_name,
            embedder=embedder,
            blocks_file=blocks_file,
        )

        # Auto-index data if blocks exist in pickle but not in ChromaDB
        try:
            blocks_in_memory = len(vs.blocks_by_id)
            blocks_in_chroma = vs.collection.count()
            
            if blocks_in_memory > 0 and blocks_in_chroma == 0:
                # logger.info(f"[HavalPipeline] Auto-indexing {blocks_in_memory} {source_type} blocks for {company_id}...")
                vs.index_blocks(list(vs.blocks_by_id.values()))
                # logger.info(f"[HavalPipeline] ✅ {source_type} data indexed successfully ({vs.collection.count()} blocks)")
            elif blocks_in_chroma > 0:
                pass
                # logger.info(f"[HavalPipeline] {source_type} store ready with {blocks_in_chroma} blocks for {company_id}")
        except Exception as e:
            pass
            # logger.warning(f"[HavalPipeline] Auto-indexing failed for {company_id}/{source_type}: {e}")

        # Register in cache
        if company_id not in _company_vector_stores:
            _company_vector_stores[company_id] = {}
        _company_vector_stores[company_id][source_type] = vs

        # logger.info(f"[HavalPipeline] Created vector store for {company_id}/{source_type}")
        return vs
    except Exception as e:
        # logger.error(f"Failed to create vector store for {company_id}/{source_type}: {e}")
        return None


def get_vector_store_for_company(company_id: str, source_type: str) -> Optional[ChromaVectorStore]:
    """
    Get vector store for a specific company and source.
    Public API for external use.
    """
    return get_or_create_vector_store(company_id, source_type)


# ---------------------------------------------------------------------------
# Persistence helpers (save / restore pipeline state)
# ---------------------------------------------------------------------------

def _save_pipeline_state(
    blocks: List[Any],
    daily_stats: List[Any],
    weekly_stats: List[Any],
    pipeline_status: Dict[str, Any],
) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "blocks": blocks,
            "daily_stats": daily_stats,
            "weekly_stats": weekly_stats,
            # Only store a shallow copy so we don't hang on to live references
            "pipeline_status": dict(pipeline_status),
            "enrichment_state": _enrichment_state,
        }
        with STATE_FILE.open("wb") as f:
            pickle.dump(snapshot, f)
        # logger.info("[HavalPipeline] Saved pipeline state to %s", STATE_FILE)
    except Exception:
        logger.exception("[HavalPipeline] Failed to save pipeline state")


def _restore_pipeline_state_if_exists() -> None:
    """
    On module import / app start, try to restore a previously completed pipeline.

    This will:
    - Reload blocks, daily_stats, weekly_stats.
    - Rebuild vs.blocks_by_id.
    - Recreate the RAG engine with the current LLM (Grok preferred, fallback Gemini).
    - Mark the pipeline as 'ready' so chat & analytics are available out of the box.
    """
    global _rag_engine, _blocks, _daily_stats, _weekly_stats, _enrichment_state, reddit_vs

    if not STATE_FILE.exists():
        # logger.info("[HavalPipeline] No saved pipeline state found at %s", STATE_FILE)
        return

    try:
        with STATE_FILE.open("rb") as f:
            snapshot = pickle.load(f)
    except Exception:
        logger.exception("[HavalPipeline] Failed to load pipeline state from %s", STATE_FILE)
        return

    blocks = snapshot.get("blocks") or []
    daily_stats = snapshot.get("daily_stats") or []
    weekly_stats = snapshot.get("weekly_stats") or []
    saved_status = snapshot.get("pipeline_status") or {}
    enrichment_state = snapshot.get("enrichment_state") or EnrichmentState()

    _blocks = blocks
    _daily_stats = daily_stats
    _weekly_stats = weekly_stats
    _enrichment_state = _enrichment_state.set_prev_state(enrichment_state)

    # Rebuild in-memory mapping for the vector store so retrieval has full blocks
    # IMPORTANT: Only add blocks to their respective vector store based on block_id prefix
    try:
        for b in blocks:
            # Route blocks to correct vector store based on block_id prefix
            if "pakwheels" in b.block_id.lower():
                pakwheels_vs.blocks_by_id[b.block_id] = b
            elif "whatsapp" in b.block_id.lower():
                whatsapp_vs.blocks_by_id[b.block_id] = b
            elif "reddit" in b.block_id.lower():
                # Use the module-level Reddit vector store
                reddit_vs.blocks_by_id[b.block_id] = b
            else:
                # Unknown block type - log warning but don't fail
                pass
                # logger.warning(f"[HavalPipeline] Unknown block type during restore: {b.block_id}")

    except Exception:
        logger.exception("[HavalPipeline] Failed to rebuild blocks_by_id from snapshot")

    # Restore pipeline status (but make sure we're not stuck in a running state)
    with _status_lock:
        _pipeline_status.update(saved_status)
        if blocks and _pipeline_status.get("status") not in (
            "processing",
            "enriching",
            "indexing",
            "separating_mixed_blocks",
            "failed",
        ):
            _pipeline_status["status"] = "ready"
        _pipeline_status["current_step"] = "ready"

    # Re-create LLM and RAG engine on top of existing Chroma store
    try:
        from os import getenv

        # Initialize LLM from centralized config
        # logger.info("[HavalPipeline] Restoring RAG engine with configured LLM.")
        api_key = getenv("GEMINI_API_KEY")
        llm = get_llm_for_component("answer_generation", fallback_api_key=api_key)

        # Use the pre-initialized Reddit and Lucid stores (already created at module level)
        
        _rag_engine = RAGEngine(
            pakwheels_store=pakwheels_vs, 
            whatsapp_store=whatsapp_vs, 
            llm=llm,
            reddit_store=reddit_vs,
            lucid_store=lucid_vs,
            k=5,
            company_id="haval"
        )

        # logger.info(
        #     "[HavalPipeline] Restored pipeline state from disk. "
        #     "Blocks=%d, daily_stats=%d, weekly_stats=%d",
        #     len(blocks),
        #     len(daily_stats),
        #     len(weekly_stats),
        # )
    except Exception:
        logger.exception("[HavalPipeline] Failed to reinitialise RAG engine from snapshot")


# Try to restore any existing state immediately on import
_restore_pipeline_state_if_exists()


# ---------- Public helpers used by Flask ----------

def get_pipeline_status() -> Dict[str, Any]:
    """
    Return a JSON-serializable snapshot of the current pipeline state.
    """
    with _status_lock:
        status_copy = dict(_pipeline_status)
        metrics: Optional[EnrichmentMetrics] = _pipeline_status.get("enrichment_metrics")
        if metrics is not None:
            status_copy["enrichment_metrics"] = {
                "total_blocks": metrics.total_blocks,
                "status_counts": metrics.status_counts,
                "variant_counts": metrics.variant_counts,
                "sentiment_counts": metrics.sentiment_counts,
                "tag_counts": metrics.tag_counts,
            }
        else:
            status_copy["enrichment_metrics"] = None
        return status_copy


def reset_pipeline_status() -> Dict[str, Any]:
    """
    Force reset pipeline status to 'ready'.
    Use when pipeline is stuck in processing/enriching/indexing state.

    Returns:
        Dict with the new pipeline status
    """
    with _status_lock:
        old_status = _pipeline_status.get("status", "unknown")
        _pipeline_status["status"] = "ready"
        _pipeline_status["current_step"] = "ready"
        _pipeline_status["error"] = None
        # logger.info(f"[HavalPipeline] Pipeline status manually reset from '{old_status}' to 'ready'")
    return get_pipeline_status()


def get_rag_engine(company_id: str = "haval") -> Optional[RAGEngine]:
    """
    Return the ready RAG engine for a specific company.

    Args:
        company_id: Company identifier (e.g., "haval", "kia", "toyota", "lucid")

    Returns:
        RAGEngine instance for the company, or None if not initialized
    """
    # Try to get company-specific RAG engine first
    if company_id in _company_rag_engines:
        return _company_rag_engines[company_id]

    # Fallback to global _rag_engine for backward compatibility (Haval only)
    if company_id == "haval":
        return _rag_engine

    # Try to create RAG engine on-the-fly if vector stores exist
    try:
        from os import getenv

        # For Lucid company, use Lucid and Reddit Lucid stores
        if company_id == "lucid":
            lucid_vs = get_or_create_vector_store(company_id, "lucid")
            reddit_lucid_vs = get_or_create_vector_store(company_id, "reddit_lucid")
            
            if lucid_vs or reddit_lucid_vs:
                # Initialize LLM from centralized config
                api_key = getenv("GEMINI_API_KEY")
                llm = get_llm_for_component("answer_generation", fallback_api_key=api_key)

                rag = RAGEngine(
                    pakwheels_store=None,  # No PakWheels for Lucid
                    whatsapp_store=None,   # No WhatsApp for Lucid
                    llm=llm,
                    reddit_lucid_store=reddit_lucid_vs,  # Reddit Lucid store
                    lucid_store=lucid_vs,  # Lucid Forum store
                    k=5,
                    company_id=company_id  # Pass company_id for correct prompts/citations
                )
                _company_rag_engines[company_id] = rag
                # logger.info(f"[HavalPipeline] Created Lucid RAG engine with stores: lucid={bool(lucid_vs)}, reddit_lucid={bool(reddit_lucid_vs)}")
                return rag
        else:
            # For other companies (Haval, Kia, etc.), use all available stores
            pakwheels_vs = get_or_create_vector_store(company_id, "pakwheels")
            whatsapp_vs = get_or_create_vector_store(company_id, "whatsapp")
            reddit_vs = get_or_create_vector_store(company_id, "reddit")
            lucid_vs = get_or_create_vector_store(company_id, "lucid")

            # Only create if at least one vector store exists and has data
            if pakwheels_vs or whatsapp_vs or reddit_vs or lucid_vs:
                # Initialize LLM from centralized config
                api_key = getenv("GEMINI_API_KEY")
                llm = get_llm_for_component("answer_generation", fallback_api_key=api_key)

                rag = RAGEngine(
                    pakwheels_store=pakwheels_vs,
                    whatsapp_store=whatsapp_vs,
                    llm=llm,
                    reddit_store=reddit_vs,
                    lucid_store=lucid_vs,
                    k=5,
                    company_id=company_id  # Pass company_id for correct prompts/citations
                )
                _company_rag_engines[company_id] = rag
                # logger.info(f"[HavalPipeline] Created RAG engine on-demand for {company_id}")
                return rag
    except Exception as e:
        pass
        # logger.error(f"Failed to create RAG engine for {company_id}: {e}")

    return None


def get_chat_history(mode) -> List[Dict[str, str]]:
    """
    Return the current in-memory chat history for the Haval chatbot.
    """
    return _chat_history.get(mode, [])

def append_to_chat_history(query: str, answer: str, mode: str) -> None:
    """
    Append a message to the in-memory chat history for the Haval chatbot.
    """
    if mode not in _chat_history:
        _chat_history[mode] = []
    _chat_history[mode].append({"role": "user", "content": query})
    _chat_history[mode].append({"role": "assistant", "content": answer})


def start_haval_pipeline(
    json_path: str,
    topic_url: str,
    persist_dir: Optional[str] = None,
    sources: str = "Pakwheels",
    company_id: str = "haval"
) -> None:
    """
    Kick off the full pipeline in a background thread for any company.

    - Non-blocking: returns immediately.
    - If a pipeline is already running, it will not start a second one.
    - After successful completion, state is persisted so future restarts can
      reload blocks + RAG directly from disk without scraping again.

    Args:
        json_path: Path to scraped JSON data file
        topic_url: PakWheels thread URL
        persist_dir: Optional custom persist directory (deprecated)
        sources: Data source type ("Pakwheels", "Whatsapp", "Facebook")
        company_id: Company identifier (e.g., "haval", "kia", "toyota")
    """
    with _status_lock:
        if _pipeline_status["status"] in ("processing", "enriching", "indexing", "separating_mixed_blocks"):
            # logger.info(f"{company_id.title()} pipeline already running; skipping new start.")
            return

        _pipeline_status.update(
            {
                "status": "processing",
                "error": None,
                "topic_url": topic_url,
                "json_path": json_path,
                "total_posts": 0,
                "total_blocks": 0,
                "enrichment_metrics": None,
                "current_step": "load_posts",
                "company_id": company_id,
            }
        )

    t = Thread(
        target=_run_pipeline,
        args=(json_path, topic_url, sources, company_id),
        daemon=True,
    )
    t.start()


# ---------- Internal worker ----------

def _run_mix_block_separation(company_id: str = "haval", verbose: bool = False) -> None:
    """
    Run the mix_block.py logic to separate mixed blocks between PakWheels, WhatsApp, and Reddit vector stores.
    This is automatically called after the pipeline completes successfully.

    Args:
        company_id: Company identifier to use company-specific paths
        verbose: If True, print detailed logs. If False, only log important changes.
    """
    import os
    import pickle
    from datetime import datetime

    from config import get_company_config
    
    # Skip mix_block separation for Lucid company (only has Lucid Forum data, no mixing)
    if company_id == "lucid":
        if verbose:
            pass
            # print(f"[MixBlock] Skipping block separation for Lucid company (single data source)")
        return

    # Get company-specific paths from config
    try:
        config = get_company_config(company_id)
        pakwheels_pkl = config.pakwheels_blocks_file
        whatsapp_pkl = config.whatsapp_blocks_file if config.has_whatsapp else None
        reddit_pkl = getattr(config, 'reddit_blocks_file', None) if hasattr(config, 'has_reddit') and getattr(config, 'has_reddit', False) else None
    except Exception as e:
        # logger.error(f"[MixBlock] Failed to get company config for {company_id}: {e}")
        # Robust fallback: Check for company-specific files, then legacy Haval naming
        import os

        # Try company-specific naming first
        pakwheels_pkl = f"data/pakwheels_blocks_{company_id}.pkl"
        whatsapp_pkl = f"data/whatsapp_blocks_{company_id}.pkl"
        reddit_pkl = f"data/reddit_blocks_{company_id}.pkl"

        # Fall back to legacy Haval naming (no suffix) if files don't exist
        if company_id == "haval":
            if not os.path.exists(pakwheels_pkl):
                pakwheels_pkl = "data/pakwheels_blocks.pkl"
            if not os.path.exists(whatsapp_pkl):
                whatsapp_pkl = "data/whatsapp_blocks.pkl"
            # reddit_blocks_haval.pkl is the new standard, no legacy fallback

    if verbose:
        # print(f"[MixBlock] Starting block separation for {company_id}...")
        # print(f"[MixBlock]   PakWheels pkl: {pakwheels_pkl}")
        if whatsapp_pkl:
            pass
            # print(f"[MixBlock]   WhatsApp pkl: {whatsapp_pkl}")
        if reddit_pkl:
            pass
            # print(f"[MixBlock]   Reddit pkl: {reddit_pkl}")

    # Load all pkl files
    pakwheels_blocks = {}
    whatsapp_blocks = {}
    reddit_blocks = {}

    if os.path.exists(pakwheels_pkl):
        with open(pakwheels_pkl, 'rb') as f:
            pakwheels_blocks = pickle.load(f)
        if verbose:
            pass
            # print(f"[MixBlock] Loaded {len(pakwheels_blocks)} blocks from PakWheels pkl")

    # Only try to load WhatsApp pkl if it's configured for this company
    if whatsapp_pkl and os.path.exists(whatsapp_pkl):
        with open(whatsapp_pkl, 'rb') as f:
            whatsapp_blocks = pickle.load(f)
        if verbose:
            pass
            # print(f"[MixBlock] Loaded {len(whatsapp_blocks)} blocks from WhatsApp pkl")

    # Only try to load Reddit pkl if it's configured for this company
    if reddit_pkl and os.path.exists(reddit_pkl):
        with open(reddit_pkl, 'rb') as f:
            reddit_blocks = pickle.load(f)
        if verbose:
            pass
            # print(f"[MixBlock] Loaded {len(reddit_blocks)} blocks from Reddit pkl")

    # If all files are empty or don't exist, nothing to separate
    if not pakwheels_blocks and not whatsapp_blocks and not reddit_blocks:
        return

    # Separate blocks based on block_id prefix
    pakwheels_only = {}
    whatsapp_only = {}
    reddit_only = {}

    # Get company-specific prefixes
    pakwheels_prefix = f"{config.pakwheels_thread_id}:"
    whatsapp_prefix = "whatsapp_"
    reddit_prefix = "reddit_"

    # Process PakWheels pkl
    for block_id, block in pakwheels_blocks.items():
        if "pakwheels" in block_id.lower():
            # Any PakWheels block (any company, any naming convention)
            pakwheels_only[block_id] = block
        elif block_id.startswith(whatsapp_prefix):
            if whatsapp_pkl:  # Only separate WhatsApp if configured
                if verbose:
                    pass
                    # print(f"[MixBlock] Found WhatsApp block in PakWheels pkl: {block_id}")
                whatsapp_only[block_id] = block
        elif block_id.startswith(reddit_prefix) or "reddit" in block_id.lower():
            if reddit_pkl:  # Only separate Reddit if configured
                if verbose:
                    pass
                    # print(f"[MixBlock] Found Reddit block in PakWheels pkl: {block_id}")
                reddit_only[block_id] = block

    # Process WhatsApp pkl (only if configured for this company)
    if whatsapp_pkl:
        for block_id, block in whatsapp_blocks.items():
            if block_id.startswith(whatsapp_prefix):
                if block_id not in whatsapp_only:  # Avoid duplicates
                    whatsapp_only[block_id] = block
            elif "pakwheels" in block_id.lower():
                # Check for ANY PakWheels block (from any company, any naming convention)
                if verbose:
                    pass
                    # print(f"[MixBlock] Found PakWheels block in WhatsApp pkl: {block_id}")
                if block_id not in pakwheels_only:  # Avoid duplicates
                    pakwheels_only[block_id] = block
            elif block_id.startswith(reddit_prefix) or "reddit" in block_id.lower():
                if reddit_pkl:  # Only separate Reddit if configured
                    if verbose:
                        pass
                        # print(f"[MixBlock] Found Reddit block in WhatsApp pkl: {block_id}")
                    if block_id not in reddit_only:  # Avoid duplicates
                        reddit_only[block_id] = block

    # Process Reddit pkl (only if configured for this company)
    if reddit_pkl:
        for block_id, block in reddit_blocks.items():
            if block_id.startswith(reddit_prefix) or "reddit" in block_id.lower():
                if block_id not in reddit_only:  # Avoid duplicates
                    reddit_only[block_id] = block
            elif "pakwheels" in block_id.lower():
                # Check for ANY PakWheels block (from any company, any naming convention)
                if verbose:
                    pass
                    # print(f"[MixBlock] Found PakWheels block in Reddit pkl: {block_id}")
                if block_id not in pakwheels_only:  # Avoid duplicates
                    pakwheels_only[block_id] = block
            elif block_id.startswith(whatsapp_prefix):
                if whatsapp_pkl:  # Only separate WhatsApp if configured
                    if verbose:
                        pass
                        # print(f"[MixBlock] Found WhatsApp block in Reddit pkl: {block_id}")
                    if block_id not in whatsapp_only:  # Avoid duplicates
                        whatsapp_only[block_id] = block

    if verbose:
        pass
        # print(f"[MixBlock] Results: PakWheels={len(pakwheels_only)}, WhatsApp={len(whatsapp_only)}, Reddit={len(reddit_only)}")

    # Only proceed if there's actual separation needed
    original_pw_count = len([bid for bid in pakwheels_blocks.keys() if bid.startswith(pakwheels_prefix)])
    original_wa_count = len([bid for bid in whatsapp_blocks.keys() if bid.startswith(whatsapp_prefix)]) if whatsapp_pkl else 0
    original_reddit_count = len([bid for bid in reddit_blocks.keys() if bid.startswith(reddit_prefix) or "reddit" in bid.lower()]) if reddit_pkl else 0

    if (len(pakwheels_only) == original_pw_count and
        len(whatsapp_only) == original_wa_count and
        len(reddit_only) == original_reddit_count):
        # Blocks already separated, no changes needed - no need to log
        return

    # Backup originals (only log if actually backing up)
    if os.path.exists(pakwheels_pkl):
        backup = pakwheels_pkl + ".mixed_backup"
        if not os.path.exists(backup):  # Don't overwrite existing backup
            os.rename(pakwheels_pkl, backup)

    if whatsapp_pkl and os.path.exists(whatsapp_pkl):
        backup = whatsapp_pkl + ".mixed_backup"
        if not os.path.exists(backup):
            os.rename(whatsapp_pkl, backup)

    if reddit_pkl and os.path.exists(reddit_pkl):
        backup = reddit_pkl + ".mixed_backup"
        if not os.path.exists(backup):
            os.rename(reddit_pkl, backup)

    # Save separated blocks (these are important changes, always log)
    # print(f"[MixBlock] Separating blocks: PakWheels={len(pakwheels_only)}, WhatsApp={len(whatsapp_only)}, Reddit={len(reddit_only)}")
    with open(pakwheels_pkl, 'wb') as f:
        pickle.dump(pakwheels_only, f)

    if whatsapp_pkl:
        with open(whatsapp_pkl, 'wb') as f:
            pickle.dump(whatsapp_only, f)

    if reddit_pkl:
        with open(reddit_pkl, 'wb') as f:
            pickle.dump(reddit_only, f)


def _run_pipeline(json_path: str, topic_url: str, sources: str, company_id: str = "haval") -> None:
    global _rag_engine, _blocks, _daily_stats, _weekly_stats, _enrichment_state

    try:
        from os import getenv

        from config import get_company_config

        config = get_company_config(company_id)
        thread_id = config.pakwheels_thread_id

        # logger.info(f"[{config.name}Pipeline] Starting pipeline for {topic_url}, json={json_path}")
        # print(f"[{config.name}Pipeline] Starting pipeline for {topic_url}, json={json_path}")

        if sources == "Pakwheels":
            # Step 1: load raw posts from JSON file
            with _status_lock:
                _pipeline_status["status"] = "processing"
                _pipeline_status["current_step"] = "load_posts"

            raw_posts = load_raw_posts_from_json(json_path)

            # Step 2: cleaning + normalization
            with _status_lock:
                _pipeline_status["current_step"] = "clean_posts"

            clean_posts = raw_to_clean_posts(raw_posts, thread_id=thread_id)

            # print(f"[{config.name}Pipeline] Loaded {len(raw_posts)} raw posts, cleaned to {len(clean_posts)} posts.")

            # Step 3: merge replies into conversation blocks
            with _status_lock:
                _pipeline_status["current_step"] = "group_blocks"

            blocks = group_posts_into_conversation_blocks(clean_posts)

            # print(f"[HavalPipeline] Grouped into {len(blocks)} conversation blocks.")

            daily_stats = compute_daily_stats(clean_posts)
            weekly_stats = compute_weekly_stats(clean_posts)

            # print(f"[HavalPipeline] Processed {len(clean_posts)} posts into {len(blocks)} blocks.")
            # print(f"[HavalPipeline] Daily stats: {daily_stats}")
            # print(f"[HavalPipeline] Weekly stats: {weekly_stats}")

        elif sources == "Whatsapp":
            pass
            with _status_lock:
                _pipeline_status["status"] = "processing"
                _pipeline_status["current_step"] = "load_posts"

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse cutoff date from company config
            min_date = None
            if hasattr(config, 'wati_message_cutoff_date') and config.wati_message_cutoff_date:
                try:
                    min_date = datetime.fromisoformat(config.wati_message_cutoff_date)
                    if min_date.tzinfo is None:
                        min_date = min_date.replace(tzinfo=timezone.utc)
                    # print(f"[{config.name}Pipeline] Filtering WhatsApp messages from {min_date.date()} onwards")
                except ValueError as e:
                    pass
                    # logger.warning(f"Invalid wati_message_cutoff_date '{config.wati_message_cutoff_date}': {e}")
                    # print(f"[{config.name}Pipeline] Warning: Invalid date filter, proceeding without date filter")

            with _status_lock:
                _pipeline_status["current_step"] = "group_blocks"

            # Create blocks from new data with date filtering
            new_blocks_from_json = whatsapp_json_to_conversation_blocks(
                data,
                company_id=company_id,
                min_date=min_date
            )
            # print(f"[{config.name}Pipeline] Created {len(new_blocks_from_json)} blocks from filtered WATI data")

            # Get vector store to check for existing blocks
            target_vs = get_or_create_vector_store(company_id, "whatsapp")

            if target_vs is None:
                raise RuntimeError(f"Could not create WhatsApp vector store for {company_id}")

            # Separate new customers vs returning customers
            blocks_to_add = []      # New customers - will be enriched and indexed
            blocks_to_update = []   # Returning customers - will be merged, re-enriched, and updated

            for new_block in new_blocks_from_json:
                existing_block = target_vs.blocks_by_id.get(new_block.block_id)

                if existing_block:
                    # Returning customer - merge new messages into existing block
                    merged_block, new_msg_count = merge_whatsapp_blocks(
                        existing_block=existing_block,
                        new_events=data,  # Pass all events, merge function will filter by phone
                        min_date=min_date,
                        company_id=company_id,
                    )

                    if new_msg_count > 0:
                        # print(f"[{config.name}Pipeline] Merged {new_msg_count} new messages for phone {new_block.phone_number}")
                        blocks_to_update.append(merged_block)
                    # else: No new messages after deduplication, skip
                else:
                    # New customer
                    blocks_to_add.append(new_block)

            # print(f"[{config.name}Pipeline] Summary: {len(blocks_to_add)} new customers, {len(blocks_to_update)} returning customers with new messages")

            # Combine all blocks for enrichment (both new and updated need enrichment)
            blocks = blocks_to_add + blocks_to_update

            if not blocks:
                # print(f"[{config.name}Pipeline] No new or updated blocks to process. Pipeline complete.")
                with _status_lock:
                    _pipeline_status["status"] = "ready"
                    _pipeline_status["current_step"] = "ready"
                return

            # print(f"[{config.name}Pipeline] Processing {len(blocks)} blocks for enrichment and indexing")

        elif sources == "Facebook":
            pass
            with _status_lock:
                _pipeline_status["status"] = "processing"
                _pipeline_status["current_step"] = "load_posts"

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with _status_lock:
                _pipeline_status["current_step"] = "group_blocks"

            blocks = facebook_posts_to_conversation_blocks(data)
            # print(f"[HavalPipeline] Grouped into {len(blocks)} conversation blocks.")

        elif sources == "Reddit":
            pass
            with _status_lock:
                _pipeline_status["status"] = "processing"
                _pipeline_status["current_step"] = "load_posts"

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with _status_lock:
                _pipeline_status["current_step"] = "group_blocks"

            # Import Reddit data processing function
            from ai.utils.reddit_data import \
                reddit_posts_to_conversation_blocks
            blocks = reddit_posts_to_conversation_blocks(data)
            # print(f"[HavalPipeline] Grouped into {len(blocks)} conversation blocks from Reddit data.")

        elif sources == "Lucid Forum":
            pass
            with _status_lock:
                _pipeline_status["status"] = "processing"
                _pipeline_status["current_step"] = "load_posts"

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            with _status_lock:
                _pipeline_status["current_step"] = "group_blocks"

            # Import Lucid data processing function
            from ai.utils.lucid_data import \
                lucid_posts_to_conversation_blocks
            blocks = lucid_posts_to_conversation_blocks(data)
            # print(f"[HavalPipeline] Grouped into {len(blocks)} conversation blocks from Lucid Forum data.")

        # print(f"[HavalPipeline] Enrichment enabled: {ENABLE_ENRICHMENT}")

        with _status_lock:
            _pipeline_status["total_posts"] = len(clean_posts) if sources == "Pakwheels" else 0
            _pipeline_status["total_blocks"] = len(blocks)
            _pipeline_status["status"] = "enriching" if ENABLE_ENRICHMENT else "indexing"
            _pipeline_status["current_step"] = (
                "enrichment" if ENABLE_ENRICHMENT else "indexing_embeddings"
            )

        # Initialize LLM for enrichment from centralized config
        api_key = getenv("GEMINI_API_KEY")
        # print("[HavalPipeline] Initializing LLM for enrichment from centralized config.")
        llm = get_llm_for_component("enrichment", fallback_api_key=api_key)

        # NEW Step 3.5: Check for existing blocks and filter out duplicates BEFORE enrichment
        # print(f"[{config.name}Pipeline] Checking for existing blocks to avoid redundant AI calls...")

        # Select the appropriate vector store based on data source (company-aware)
        source_target_vs = None
        if sources == "Whatsapp":
            # For WhatsApp, target_vs was already created earlier in the merge logic
            source_target_vs = get_or_create_vector_store(company_id, "whatsapp")
        elif sources == "Reddit":
            source_target_vs = get_or_create_vector_store(company_id, "reddit")
        elif sources == "Lucid Forum":
            source_target_vs = get_or_create_vector_store(company_id, "lucid")
        else:  # Pakwheels or Facebook
            source_target_vs = get_or_create_vector_store(company_id, "pakwheels")

        if source_target_vs is None:
            raise RuntimeError(f"Could not create vector store for {company_id}/{sources}")

        blocks_to_enrich = []
        blocks_to_skip_count = 0
        blocks_to_update_count = 0 

        if sources == "Whatsapp":
            # WhatsApp filtering was already handled earlier (blocks_to_add, blocks_to_update)
            # Both need enrichment/indexing
            blocks_to_enrich = blocks
        else:
            existing_block_ids = set(source_target_vs.blocks_by_id.keys())
            for block in blocks:
                if block.block_id not in existing_block_ids:
                    blocks_to_enrich.append(block)
                else:
                    existing_block = source_target_vs.blocks_by_id[block.block_id]
                    # Deep check: If the block has more replies than what we have stored, re-enrich it
                    if len(block.replies) > len(existing_block.replies):
                        blocks_to_enrich.append(block)
                        blocks_to_update_count += 1
                    else:
                        blocks_to_skip_count += 1

        # print(f"[{config.name}Pipeline] Optimization: {len(blocks_to_enrich)} blocks need processing ({blocks_to_update_count} updates), {blocks_to_skip_count} skipped.")

        # Step 4 (optional): Enrichment (classification / sentiments / tags)
        results = None
        if ENABLE_ENRICHMENT and blocks_to_enrich:
            # print(f"[{config.name}Pipeline] Starting enrichment (classification / sentiment / tags)...")
            # print(f"  📊 Company: {config.full_name} (ID: {company_id})")
            print(f"  📂 Data Source: {sources}")
            results = classify_blocks(
                blocks_to_enrich,
                llm,
                _enrichment_state,
                log_progress=True,
                company_id=company_id,
                data_source=sources.lower(),
            )
            metrics = compute_enrichment_metrics(results)
            # print(f"[{config.name}Pipeline] Enrichment complete.")
            state = _enrichment_state

            with _status_lock:
                _pipeline_status["enrichment_metrics"] = metrics
                _pipeline_status["status"] = "indexing"
                _pipeline_status["current_step"] = "indexing_embeddings"
        elif not blocks_to_enrich:
            # print(f"[{config.name}Pipeline] No new or updated blocks to enrich. Skipping LLM calls.")
            results = []
            metrics = None
            state = _enrichment_state
        else:
            metrics = None  # type: ignore[assignment]
            results = None
            state = None

        # Step 5: Check for existing blocks and filter out duplicates (CLEANUP/DEDUPE handled above)
        # print(f"[{config.name}Pipeline] Proceeding to indexing...")

        # target_vs was only for WhatsApp earlier, let's unify
        target_vs = source_target_vs 
        if sources == "Whatsapp":
            target_persist_path = config.chroma_whatsapp_path
        elif sources == "Reddit":
            target_persist_path = config.chroma_reddit_path
        elif sources == "Lucid Forum":
            target_persist_path = config.chroma_lucid_path
        else:  # Pakwheels or Facebook
            target_persist_path = config.chroma_pakwheels_path

        if target_vs is None:
            raise RuntimeError(f"Could not create vector store for {company_id}/{sources}")

        # Step 6: Embeddings + Chroma indexing
        if sources == "Whatsapp":
            # WhatsApp indexing: we already separated blocks in the merge step
            # print(f"[{config.name}Pipeline] WhatsApp indexing: {len(blocks_to_add)} new, {len(blocks_to_update)} updates")

            with _status_lock:
                _pipeline_status["current_step"] = "indexing_embeddings"

            # Build result map for enrichment results
            result_map: Dict[str, Any] = {}
            if ENABLE_ENRICHMENT and results:
                for r in results:
                    result_map[r.block.block_id] = r

            # Handle updates first (delete old Chroma entry, add new one)
            for block in blocks_to_update:
                cls_result = result_map.get(block.block_id)
                target_vs.update_block(block, classification_result=cls_result)

            # Handle new blocks (normal indexing)
            if blocks_to_add:
                # Filter enrichment results to match new blocks
                new_block_results = [r for r in results if r.block.block_id in {b.block_id for b in blocks_to_add}] if results else None
                target_vs.index_blocks(blocks_to_add, classification_results=new_block_results)

            # print(f"[{config.name}Pipeline] WhatsApp indexing complete: {len(blocks_to_update)} updated, {len(blocks_to_add)} added")

        else:
            # Unified logic for non-WhatsApp sources using the pre-filtered blocks_to_enrich
            if not blocks_to_enrich:
                pass
                # print(f"[{config.name}Pipeline] No new or updated blocks to process. Indexing skipped.")
            else:
                # Build result map for enrichment results
                result_map: Dict[str, Any] = {}
                if ENABLE_ENRICHMENT and results:
                    for r in results:
                        result_map[r.block.block_id] = r

                with _status_lock:
                    _pipeline_status["current_step"] = "indexing_embeddings"

                # Handle updates (where len(replies) grew) and new additions
                # For non-WhatsApp, we can just use index_blocks which handles additions.
                # BUT for updates, we should call update_block to replace the old text/embedding.
                
                new_only = []
                update_only = []
                # Re-identify which ones are updates vs new in the enrichment batch
                existing_block_ids = set(target_vs.blocks_by_id.keys())
                
                for b in blocks_to_enrich:
                    if b.block_id in existing_block_ids:
                        target_vs.update_block(b, classification_result=result_map.get(b.block_id))
                    else:
                        new_only.append(b)
                
                if new_only:
                    # Filter enrichment results to match new blocks
                    new_results = [r for r in results if r.block.block_id in {b.block_id for b in new_only}] if results else None
                    target_vs.index_blocks(new_only, classification_results=new_results)

                # print(f"[{config.name}Pipeline] Indexing complete: {len(blocks_to_enrich)} blocks processed.")


        # print(f"[{config.name}Pipeline] Initializing RAG engine (LLM + vector store)...")

        with _status_lock:
            _pipeline_status["current_step"] = "init_rag"

        # Get company-specific vector stores for RAG engine
        company_pakwheels_vs = get_or_create_vector_store(company_id, "pakwheels")
        company_whatsapp_vs = get_or_create_vector_store(company_id, "whatsapp")
        company_reddit_vs = get_or_create_vector_store(company_id, "reddit")
        company_lucid_vs = get_or_create_vector_store(company_id, "lucid")

        rag = RAGEngine(
            pakwheels_store=company_pakwheels_vs,
            whatsapp_store=company_whatsapp_vs,
            llm=llm,
            reddit_store=company_reddit_vs,
            lucid_store=company_lucid_vs,
            k=5,
            state=state,
            company_id=company_id  # Pass company_id for correct prompts/citations
        )

        # Store RAG engine for this company
        _company_rag_engines[company_id] = rag

        # Step 7: Save in global state
        _blocks = blocks
        _daily_stats = daily_stats if sources == "Pakwheels" else []
        _weekly_stats = weekly_stats if sources == "Pakwheels" else []
        _rag_engine = rag
        _enrichment_state = state if state is not None else _enrichment_state

        with _status_lock:
            _pipeline_status["status"] = "ready"
            _pipeline_status["current_step"] = "ready"

            # Take a snapshot of status for persistence
            status_snapshot = dict(_pipeline_status)

        # Persist pipeline snapshot so next server start can reload directly
        _save_pipeline_state(blocks, _daily_stats, _weekly_stats, status_snapshot)

        # Step 8: Auto-run mix_block.py to separate mixed blocks (silent mode)
        with _status_lock:
            _pipeline_status["current_step"] = "separating_mixed_blocks"

        try:
            _run_mix_block_separation(company_id=company_id, verbose=False)

            # Refresh date spans in RAG engine after new data is added (silent)
            if company_id in _company_rag_engines:
                _company_rag_engines[company_id].refresh_date_spans()
        except Exception as mix_error:
            pass
            # logger.warning(f"[HavalPipeline] Block separation failed: {mix_error}")

        # Complaint classification removed

        # print("[HavalPipeline] Pipeline completed successfully.")
        # logger.info("[HavalPipeline] Pipeline completed successfully.")

    except Exception as e:
        # print(f"[HavalPipeline] ERROR in pipeline: {e}")
        traceback.print_exc()
        # logger.error("[HavalPipeline] Pipeline failed", exc_info=True)
        with _status_lock:
            _pipeline_status["status"] = "failed"
            _pipeline_status["current_step"] = "error"
            _pipeline_status["error"] = f"{e}"


def get_daily_weekly_stats():
    """
    Return (daily_stats, weekly_stats) from the last Haval pipeline run.

    These are whatever objects your time_analytics functions returned
    (typically lists of dicts or small dataclasses). For the Jinja template
    we just iterate over them.

    If the pipeline was restored from disk, these will reflect the last
    successful run prior to server restart.
    """
    with _status_lock:
        return _daily_stats, _weekly_stats
