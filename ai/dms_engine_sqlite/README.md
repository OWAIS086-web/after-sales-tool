# DMS RAG Engine - Phase 1 Complete

**Production-grade Text-to-SQL system for DMS structured data**

Reference: [DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md](../../docs/DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md)

---

## ✅ Phase 1: Foundation & Metadata (COMPLETE)

### Step 1.1: Generate Table Metadata

**Script**: `metadata/generate_metadata.py`

Extracts schema from SQLite, uses LLM to generate business context:

```bash
# Generate metadata for all non-empty tables
python -m ai.dms_engine.metadata.generate_metadata

# Test on a single table first (recommended)
python -m ai.dms_engine.metadata.generate_metadata --tables RoMaster

# Test on multiple specific tables
python -m ai.dms_engine.metadata.generate_metadata --tables RoMaster Vehicleinf Dealers

# With options
python -m ai.dms_engine.metadata.generate_metadata \
  --db data/SazgarDMSDW.sqlite \
  --output data/dms_metadata \
  --skip-empty \
  --min-rows 0
```

**Output**: JSON files in `data/dms_metadata/` (one per table)

**Example**: `data/dms_metadata/RoMaster.json`
```json
{
  "table_name": "RoMaster",
  "business_name": "Repair Orders",
  "description": "Master table for all repair orders...",
  "business_domain": "service",
  "columns": [...],
  "foreign_keys": [...],
  "sample_queries": [...],
  "searchable_text": "RoMaster is the Repair Orders table..."
}
```

**Cost**: ~$0.002/table × 150 tables = **~$0.30 total** (using grok-3-fast)

---

### Step 1.2: Index Metadata into Vector Store

**Script**: `metadata/index_metadata.py`

Indexes `searchable_text` into ChromaDB for semantic search:

```bash
# Index metadata into ChromaDB
python -m ai.dms_engine.metadata.index_metadata

# With options
python -m ai.dms_engine.metadata.index_metadata \
  --metadata-dir data/dms_metadata \
  --company haval \
  --persist-path data/chroma_dms_haval \
  --pkl-file data/dms_haval_metadata.pkl
```

**Output**:
- ChromaDB: `data/chroma_dms_haval/` (vector index)
- PKL: `data/dms_haval_metadata.pkl` (full metadata objects)

**Usage in RAG Pipeline**:
```python
from ai.dms_engine.metadata.index_metadata import DMSMetadataVectorStore

# Load vector store
vector_store = DMSMetadataVectorStore(
    persist_path="data/chroma_dms_haval",
    collection_name="dms_haval_metadata",
    company="haval"
)

# LAYER 2: Semantic schema retrieval
results = vector_store.query_similar_tables(
    query="How many repair orders in Lahore?",
    top_k=10
)

# Returns: [{'table_name': 'RoMaster', 'relevance_score': 0.89, ...}, ...]
```

---

## 🔄 Complete Workflow

### 1. First Time Setup

```bash
# Step 1a: Test metadata generation on one table first
python -m ai.dms_engine.metadata.generate_metadata --tables RoMaster

# Step 1b: If test looks good, generate metadata for all tables
python -m ai.dms_engine.metadata.generate_metadata

# Step 2: Index into ChromaDB (Phase 1.2)
python -m ai.dms_engine.metadata.index_metadata
```

### 2. Update After Schema Changes

```bash
# Regenerate metadata for specific table
python -m ai.dms_engine.metadata.generate_metadata --tables RoMaster

# Re-index
python -m ai.dms_engine.metadata.index_metadata
```

---

## 📊 How Metadata Flows Through RAG Pipeline

See: [DMS_METADATA_USAGE_FLOW.md](../../docs/DMS_METADATA_USAGE_FLOW.md)

```
User Query → LAYER 2 (Schema Retrieval)
             ↓
        ChromaDB searches searchable_text
             ↓
        Returns top-K tables (RoMaster, Vehicleinf, Dealers)
             ↓
        LAYER 3 (Context Assembly)
             ↓
        Load full metadata from PKL
             ↓
        LAYER 4 (SQL Generation)
             ↓
        LLM generates SQL using columns, FKs, sample queries
```

---

## 🗂️ File Structure

```
ai/dms_engine/
├── README.md                    ← You are here
├── __init__.py
├── metadata/
│   ├── __init__.py
│   ├── generate_metadata.py    ← Phase 1.1: Generate JSON metadata
│   └── index_metadata.py       ← Phase 1.2: Index into ChromaDB
└── agents/                      ← Phase 2: Multi-agent system (TODO)

data/
├── dms_metadata/                ← JSON files (one per table)
│   ├── RoMaster.json
│   ├── InvoiceMaster.json
│   └── ...
├── chroma_dms_haval/            ← ChromaDB vector index
└── dms_haval_metadata.pkl       ← Full metadata objects (PKL)
```

---

## 🧪 Testing Semantic Search

After indexing, test the vector search:

```python
from ai.dms_engine.metadata.index_metadata import DMSMetadataVectorStore

vector_store = DMSMetadataVectorStore()

# Test queries
queries = [
    "repair orders and service history",
    "vehicle information and VIN numbers",
    "customer data and contact info",
    "invoices and payment records"
]

for query in queries:
    print(f"\nQuery: {query}")
    results = vector_store.query_similar_tables(query, top_k=5)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['table_name']:20} Score: {r['relevance_score']:.3f}")
```

**Expected Results**:
- "repair orders" → RoMaster, RoDetails (high scores)
- "vehicle information" → Vehicleinf, MODEL (high scores)
- "invoices" → InvoiceMaster, InvoiceDetail (high scores)

---

## ⏭️ Next Steps (Phase 2)

Once metadata is indexed, you can proceed to **Phase 2: Multi-Agent Pipeline**:

1. **Router Agent** - Query classification
2. **Schema Agent** - Uses this vector store for LAYER 2
3. **Decomposition Agent** - Break complex queries
4. **Generation Agent** - SQL generation with metadata context
5. **Validation Agent** - Security & syntax validation
6. **Correction Agent** - Self-correction loop

See: [DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md](../../docs/DMS_RAG_PRODUCTION_IMPLEMENTATION_PLAN.md) (Phase 2)

---

## 📝 Progress Tracking

See: [DMS_IMPLEMENTATION_PROGRESS.md](../../docs/DMS_IMPLEMENTATION_PROGRESS.md)

**Current Status**: ✅ Phase 1 Complete (Steps 1.1 & 1.2)
