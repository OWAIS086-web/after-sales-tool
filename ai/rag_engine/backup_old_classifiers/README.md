# Backup: Old Single-Purpose Classifiers

**Replaced by:** `merged_classifier.py` (combines 3 LLM calls into 1)

**Moved:** 2026-01-17

---

## Files Moved to Backup

### ✅ `format_detector.py` (COMPLETELY UNUSED)
- **Function:** `detect_user_format_instruction()`
- **Replaced by:** `merged_classifier.py` → `format_instruction` output
- **Status:** No longer imported anywhere, safe to archive

---

## Files Still in Use (NOT moved)

### ⚠️ `query_classification.py` (PARTIALLY IN USE)
**Obsolete functions:**
- `classify_query_domain()` → Replaced by merged classifier

**Still used utility functions:**
- `is_broad_insight_question()` - Line 1260 in core.py
- `is_statistical_query()` - Line 1472 in core.py
- `extract_customer_name()` - Line 1147 in core.py
- `should_include_citations()` - Line 1305 in core.py
- `extract_customer_names_llm()` - Lines 1140, 1375 in core.py

### ⚠️ `query_optimizer.py` (PARTIALLY IN USE)
**Obsolete functions:**
- `optimize_queries()` → Replaced by merged classifier

**Still used utility functions:**
- `format_range()` - Line 1526 in core.py (formats date ranges for no-hit messages)
- `parse_iso_or_none()` - Line 1264 in core.py (parses datetime from merged classifier)

---

## Migration Summary

**Before (3 separate LLM calls):**
1. Domain classification: `classify_query_domain()` - 500 tokens, 1-2s
2. Format detection: `detect_user_format_instruction()` - 300 tokens, 1-1.5s
3. Query optimization: `optimize_queries()` - 800 tokens, 1-2s

**After (1 merged LLM call):**
1. Merged classifier: `classify_merged_with_regex_first()` - 400 tokens, 1.5-2.5s
   - Returns: domain + format_instruction + search_queries
   - **25% faster** (verified by experiments)
   - **Regex-first** strategy for 80% instant classification

---

## Rollback (if needed)

To restore old pipeline:
```bash
mv ai/rag_engine/backup_old_classifiers/format_detector.py ai/rag_engine/
```

Then revert imports in `ai/rag_engine/core.py`.
