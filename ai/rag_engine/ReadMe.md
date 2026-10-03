# RAG Engine

## File Structure

```
ai/rag_engine/
├── __init__.py                  (17 lines)   - Package exports
├── query_classification.py      (196 lines)  - Query domain and type classification
├── query_optimizer.py           (405 lines)  - Query decomposition and optimization
├── prompt_builder.py            (209 lines)  - System prompt construction
├── citation_builder.py          (227 lines)  - Context and citation formatting
└── core.py                      (642 lines)  - Main RAGEngine class
```

**Total modular code:**

## Module Breakdown

### 1. `query_classification.py` (COMPLETED)
**Purpose:** Query domain and type detection

**Functions:**
- `classify_query_domain()` - LLM-based domain classification (in_domain, out_of_domain, small_talk)
- `is_broad_insight_question()` - Detect pattern/trend questions
- `is_statistical_query()` - Detect counting/aggregation queries
- `extract_customer_name()` - Extract customer names from WhatsApp queries

**Original lines:** 63-590 (various sections)

---

### 2. `query_optimizer.py` (COMPLETED)
**Purpose:** Query decomposition and semantic optimization

**Functions:**
- `optimize_queries()` - Main optimization orchestrator (lines 592-872)
- `extract_json_block()` - JSON parsing helper (lines 441-458)
- `parse_iso_or_none()` - ISO datetime parsing (lines 460-475)
- `format_range()` - Time range formatting (lines 477-489)
- `has_enriched_metadata()` - Check metadata availability (lines 578-590)

**Features:**
- Sub-query decomposition (1-5 focused queries)
- Time window extraction from natural language
- Metadata filter generation (variants, sentiments, tags)
- Semantic search optimization

---

### 3. `prompt_builder.py` (COMPLETED)
**Purpose:** System prompt construction for different modes

**Functions:**
- `messages_with_system()` - Build message list with history (lines 46-61)
- `build_thinking_prompt()` - Comprehensive analysis mode (lines 1182-1276)
- `build_non_thinking_prompt()` - Clean statistics mode (lines 1127-1180)

**Modes:**
- **Thinking Mode:** Detailed structure with charts, citations, recommendations
- **Non-Thinking Mode:** Clean statistics only, no emojis/citations

---

### 4. `citation_builder.py` (COMPLETED)
**Purpose:** Context and citation formatting

**Functions:**
- `build_context()` - Format retrieved blocks for LLM (lines 873-921)
- `build_citations()` - Generate human-readable references (lines 923-1072)

**Features:**
- Summary-first context building
- Metadata-rich citations (variant, sentiment, tags)
- PakWheels vs WhatsApp source detection
- Time window filtering for accurate citations
- Similarity threshold filtering

---

### 5. `core.py` (COMPLETED)
**Purpose:** Main RAG engine orchestration

**Class:** `RAGEngine`

**Methods:**
- `__init__()` - Initialize with vector stores and LLM (lines 24-44)
- `answer()` - Main RAG entry point (lines 1278-1628)
- `_get_whatsapp_messages_by_customer()` - Database retrieval (lines 283-330)
- `_handle_whatsapp_customer_query()` - Customer-specific handler (lines 332-439)
- `_fallback_answer()` - Generate fallback response (lines 1074-1125)

**Features:**
- Dual vector store support (PakWheels + WhatsApp)
- Query classification and routing
- Dynamic retrieval strategies (thinking vs non-thinking)
- Customer-specific WhatsApp conversation handling
- Citation time filtering

---

## Key Improvements

### 1. Reusability
- All helper methods converted to standalone functions
- Easy to test individual components
- Can be imported and used independently

### 2. Maintainability
- Clear separation of concerns
- Each module has a single, well-defined purpose
- Comprehensive docstrings at module and function level

### 3. Discoverability
- Module-level documentation explains purpose
- Function signatures clearly show inputs/outputs
- Type hints preserved throughout

### 54. Backward Compatibility
- Original API preserved (`from ai.rag_engine import RAGEngine`)
- All functionality maintained
- No breaking changes

## Migration Notes

### For Developers
1. **No changes needed** for existing code that imports `RAGEngine`
2. Can now import individual functions for testing:
   ```python
   from ai.rag_engine.query_optimizer import extract_json_block
   ```
3. Clear module boundaries make debugging easier


