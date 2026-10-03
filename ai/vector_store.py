# haval_insights/vector_store.py
from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo
import chromadb  # type: ignore
import pickle
import os

from ai.embeddings import BaseEmbedder
from ai.models import ConversationBlock
from ai.enrichment import BlockClassificationResult


class RetrievedBlock:
    def __init__(self, block: ConversationBlock, score: float):
        self.block = block
        self.score = score
        # Filled by ChromaVectorStore.query with things like variant, sentiment, tags, etc.
        self.metadata: Optional[Dict[str, Any]] = None


class ChromaVectorStore:
    """
    Thin wrapper over Chroma for storing ConversationBlocks.

    Design:
    - We manage embeddings ourselves via BaseEmbedder.
    - Chroma uses a PersistentClient at `persist_path`.
    - We keep a mapping block_id -> ConversationBlock in memory (outside Chroma).
    """

    def __init__(
        self,
        persist_path: str,
        collection_name: str = "haval_h6_blocks",
        embedder: Optional[BaseEmbedder] = None,
        blocks_file: Optional[str] = None,
    ):
        import shutil
        try:
            self.client = chromadb.PersistentClient(path=persist_path)
        except (ValueError, AttributeError) as e:
            # Corrupted ChromaDB database - delete and recreate
            print(f"[VectorStore] ChromaDB corrupted at {persist_path}: {e}")
            print(f"[VectorStore] Deleting and recreating ChromaDB directory...")
            if os.path.exists(persist_path):
                shutil.rmtree(persist_path)
            os.makedirs(persist_path, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_path)
            print(f"[VectorStore] ChromaDB recreated successfully at {persist_path}")
        # No embedding_function because we provide embeddings manually
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = embedder
        self.blocks_file = blocks_file
        # Load blocks from disk if blocks_file is provided
        self._blocks_by_id: Dict[str, ConversationBlock] = self._load_blocks() if blocks_file else {}

    @property
    def blocks_by_id(self) -> Dict[str, ConversationBlock]:
        return self._blocks_by_id

    # ------------------------------------------------------------------
    # Persistence methods
    # ------------------------------------------------------------------
    def _load_blocks(self) -> Dict[str, ConversationBlock]:
        """
        Load blocks from pickle file on startup.
        Returns empty dict if file doesn't exist.
        """
        if not self.blocks_file:
            return {}

        if os.path.exists(self.blocks_file):
            try:
                with open(self.blocks_file, 'rb') as f:
                    blocks = pickle.load(f)
                    print(f"[VectorStore] Loaded {len(blocks)} blocks from {self.blocks_file}")
                    return blocks
            except Exception as e:
                print(f"[VectorStore] Warning: Failed to load blocks from {self.blocks_file}: {e}")
                return {}
        else:
            print(f"[VectorStore] No existing blocks file at {self.blocks_file}, starting fresh")
            return {}

    def _save_blocks(self) -> None:
        """
        Save blocks to pickle file after indexing.
        """
        if not self.blocks_file:
            return

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.blocks_file), exist_ok=True)

            with open(self.blocks_file, 'wb') as f:
                pickle.dump(self._blocks_by_id, f)
            print(f"[VectorStore] Saved {len(self._blocks_by_id)} blocks to {self.blocks_file}")
        except Exception as e:
            print(f"[VectorStore] Warning: Failed to save blocks to {self.blocks_file}: {e}")

    # ------------------------------------------------------------------
    # Metadata building helper
    # ------------------------------------------------------------------
    def _build_metadata(
        self,
        block: ConversationBlock,
        classification_result: Optional[BlockClassificationResult] = None,
    ) -> Dict[str, Any]:
        """
        Build Chroma metadata dictionary for a ConversationBlock.

        This is extracted from index_blocks to allow reuse in update_block.

        Args:
            block: The ConversationBlock to build metadata for
            classification_result: Optional enrichment result

        Returns:
            Dictionary of metadata suitable for Chroma storage
        """
        # Enrichment fields from block itself
        variant = getattr(block, "dominant_variant", None) or "Unknown"
        sentiment = getattr(block, "dominant_sentiment", None) or "unknown"

        tags_list = getattr(block, "aggregated_tags", None) or []
        tags_str = ",".join(tags_list) if tags_list else ""

        summary = getattr(block, "summary", "") or ""

        # Classification result (if provided)
        if classification_result is not None:
            classification_status = classification_result.status or "unknown"
            new_variants = classification_result.new_variants or []
            new_tags = classification_result.new_tags or []
        else:
            classification_status = "not_classified"
            new_variants = []
            new_tags = []

        new_variants_str = ",".join(new_variants) if new_variants else ""
        new_tags_str = ",".join(new_tags) if new_tags else ""

        # Base metadata
        metadata = {
            "thread_id": str(block.thread_id),
            "topic_title": str(block.topic_title),
            "root_username": str(block.root_post.username),
            "start_datetime": block.start_datetime.isoformat(),
            "end_datetime": block.end_datetime.isoformat(),
            "variant": str(variant),
            "sentiment": str(sentiment),
            "tags": tags_str,
            "summary": summary,
            "classification_status": classification_status,
            "new_variants": new_variants_str,
            "new_tags": new_tags_str,
        }

        # Add source-specific fields
        # Check thread_id first to determine source (most reliable)
        thread_id_lower = str(block.thread_id).lower()
        
        if "lucid" in thread_id_lower:
            metadata["source"] = "Lucid"
            # Store Lucid post link for citation building
            if hasattr(block.root_post, 'source_url') and block.root_post.source_url:
                metadata["post_link"] = str(block.root_post.source_url)
        elif hasattr(block, 'phone_number') and block.phone_number:
            metadata["phone_number"] = str(block.phone_number)
            metadata["source"] = "Whatsapp"
        elif "whatsapp" in thread_id_lower:
            metadata["source"] = "Whatsapp"
        elif "reddit" in thread_id_lower:
            metadata["source"] = "Reddit"
        elif hasattr(block.root_post, 'post_id') and block.root_post.post_id:
            metadata["post_id"] = str(block.root_post.post_id)
            if hasattr(block.root_post, 'post_number') and block.root_post.post_number:
                metadata["post_number"] = str(block.root_post.post_number)
            metadata["source"] = "PakWheels"
        else:
            metadata["source"] = "PakWheels"

        return metadata

    # ------------------------------------------------------------------
    # Block update (for returning customers with new messages)
    # ------------------------------------------------------------------
    def update_block(
        self,
        block: ConversationBlock,
        classification_result: Optional[BlockClassificationResult] = None,
    ) -> bool:
        """
        Update an existing block in both Chroma and pkl.

        This method handles the case where a returning customer sends new messages
        that have been merged into their existing block. It:
        1. Updates the in-memory _blocks_by_id mapping
        2. Deletes the old Chroma entry (if exists)
        3. Re-embeds the updated flattened_text
        4. Adds the new entry to Chroma
        5. Saves the updated pkl file

        Args:
            block: The updated ConversationBlock (with new messages merged)
            classification_result: Optional new enrichment result

        Returns:
            True if this was an update (block existed), False if it was new
        """
        if not self.embedder:
            raise RuntimeError("ChromaVectorStore requires an embedder to update blocks.")

        bid = block.block_id
        is_update = bid in self._blocks_by_id

        # 1. Update in-memory mapping
        self._blocks_by_id[bid] = block

        # 2. Delete old Chroma entry if exists
        if is_update:
            try:
                self.collection.delete(ids=[bid])
                print(f"[VectorStore] Deleted old Chroma entry for update: {bid}")
            except Exception as e:
                print(f"[VectorStore] Warning: Failed to delete old entry {bid}: {e}")
                # Continue anyway - the add will handle it

        # 3. Build metadata
        metadata = self._build_metadata(block, classification_result)

        # 4. Re-embed and add to Chroma
        embedding = self.embedder.embed([block.flattened_text])[0]

        self.collection.add(
            ids=[bid],
            documents=[block.flattened_text],
            metadatas=[metadata],
            embeddings=[embedding],
        )

        action = "Updated" if is_update else "Added"
        print(f"[VectorStore] {action} block in Chroma: {bid}")

        # 5. Save to disk
        self._save_blocks()

        return is_update

    def get_database_date_range(self) -> Optional[tuple[datetime, datetime, int]]:
        """
        Get the full date range of all data in this vector store.

        Returns:
            tuple of (earliest_date, latest_date, total_conversations) or None if no data
        """
        if not self._blocks_by_id:
            return None

        dates = []
        date_sources = {}  # Track which block each date came from

        for block in self._blocks_by_id.values():
            block_id = getattr(block, "block_id", "unknown")
            start_dt = getattr(block, "start_datetime", None)
            end_dt = getattr(block, "end_datetime", None)

            # Add both start and end dates
            if start_dt:
                if isinstance(start_dt, str):
                    try:
                        start_dt = datetime.fromisoformat(start_dt)
                    except:
                        continue
                if isinstance(start_dt, datetime):
                    dates.append(start_dt)
                    date_sources[start_dt] = f"{block_id} (start)"

            if end_dt:
                if isinstance(end_dt, str):
                    try:
                        end_dt = datetime.fromisoformat(end_dt)
                    except:
                        continue
                if isinstance(end_dt, datetime):
                    dates.append(end_dt)
                    date_sources[end_dt] = f"{block_id} (end)"

        if not dates:
            return None

        earliest = min(dates)
        latest = max(dates)

        # Debug: Print which blocks have the earliest/latest dates
        print(f"[VECTOR_STORE DEBUG] Date range for {self.collection.name}:")
        print(f"  Earliest: {earliest.strftime('%Y-%m-%d %H:%M:%S')} from {date_sources.get(earliest, 'unknown')}")
        print(f"  Latest: {latest.strftime('%Y-%m-%d %H:%M:%S')} from {date_sources.get(latest, 'unknown')}")
        print(f"  Total blocks: {len(self._blocks_by_id)}")

        return (earliest, latest, len(self._blocks_by_id))

    # ------------------------------------------------------------------
    # Indexing (enrichment-aware, deduplicated)
    # ------------------------------------------------------------------
    def index_blocks(
        self,
        blocks: List[ConversationBlock],
        classification_results: Optional[List[BlockClassificationResult]] = None,
    ) -> None:
        """
        Index conversation blocks into Chroma.

        - Uses block.block_id as the Chroma ID.
        - Stores flattened_text as the document.
        - Also stores metadata (author, dates, variant, sentiment, tags, summary,
          plus classification status / new_variants / new_tags when available).
        - Avoids duplicating blocks already present in the collection.

        classification_results:
        - Optional list of BlockClassificationResult.
        - If provided, we attach:
            * classification_status
            * new_variants (CSV)
            * new_tags (CSV)
          into the Chroma metadata for each block.
        """
        if not self.embedder:
            raise RuntimeError("ChromaVectorStore requires an embedder to index blocks.")

        if not blocks:
            return

        # Always refresh in-memory mapping with latest block objects
        for b in blocks:
            self._blocks_by_id[b.block_id] = b

        # Optional: map block_id -> classification result
        result_map: Dict[str, BlockClassificationResult] = {}
        if classification_results:
            for r in classification_results:
                # Last one wins if duplicates, but there shouldn't be any.
                result_map[r.block.block_id] = r

        # 1) Figure out which block_ids are already in Chroma
        all_ids: List[str] = [b.block_id for b in blocks]

        try:
            existing = self.collection.get(ids=all_ids, include=[])
            raw_ids = existing.get("ids", [])
            # Chroma can return either flat list or list-of-lists depending on version
            if raw_ids and isinstance(raw_ids[0], list):
                existing_ids = set(raw_ids[0])
            else:
                existing_ids = set(raw_ids)
        except Exception:
            # If anything goes wrong, assume nothing exists (fallback to full add)
            existing_ids = set()

        # 2) Keep only *new* blocks (not already indexed)
        new_blocks: List[ConversationBlock] = []
        seen_new_ids: set[str] = set()

        for b in blocks:
            bid = b.block_id
            if bid in existing_ids:
                # Already indexed in Chroma; skip to avoid duplication
                continue
            if bid in seen_new_ids:
                # Duplicated within this batch; keep only one
                continue
            seen_new_ids.add(bid)
            new_blocks.append(b)

        if not new_blocks:
            # Nothing new to index, but still save blocks to pickle if we updated _blocks_by_id
            if self._blocks_by_id:
                self._save_blocks()
            return

        # 3) Prepare payload for Chroma
        ids: List[str] = []
        docs: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for b in new_blocks:
            bid = b.block_id
            ids.append(bid)
            docs.append(b.flattened_text)

            # Enrichment fields from block itself (classify_block updates these in-place)
            variant = getattr(b, "dominant_variant", None) or "Unknown"
            sentiment = getattr(b, "dominant_sentiment", None) or "unknown"

            tags_list = getattr(b, "aggregated_tags", None) or []
            # store as CSV in Chroma metadata; full list will also be returned in RetrievedBlock.metadata
            tags_str = ",".join(tags_list) if tags_list else ""

            summary = getattr(b, "summary", "") or ""

            # Classification result (if provided)
            cls_res = result_map.get(bid)
            if cls_res is not None:
                classification_status = cls_res.status or "unknown"
                new_variants = cls_res.new_variants or []
                new_tags = cls_res.new_tags or []
            else:
                classification_status = "not_classified"
                new_variants = []
                new_tags = []

            new_variants_str = ",".join(new_variants) if new_variants else ""
            new_tags_str = ",".join(new_tags) if new_tags else ""

            # Coerce None -> safe strings (Chroma does NOT allow None)
            metadata = {
                "thread_id": str(b.thread_id),
                "topic_title": str(b.topic_title),
                "root_username": str(b.root_post.username),
                "start_datetime": b.start_datetime.isoformat(),
                "end_datetime": b.end_datetime.isoformat(),
                "variant": str(variant),
                "sentiment": str(sentiment),
                "tags": tags_str,
                "summary": summary,
                "classification_status": classification_status,
                "new_variants": new_variants_str,
                "new_tags": new_tags_str,
            }
            
            # Add source-specific fields for citation enhancement
            # Check thread_id first to determine source (most reliable)
            thread_id_lower = str(b.thread_id).lower()
            
            if "lucid" in thread_id_lower:
                metadata["source"] = "Lucid"
                # Store Lucid post link for citation building
                if hasattr(b.root_post, 'source_url') and b.root_post.source_url:
                    metadata["post_link"] = str(b.root_post.source_url)
                print(f"[VECTOR_STORE] Storing Lucid block {bid}")
            elif hasattr(b, 'phone_number') and b.phone_number:
                metadata["phone_number"] = str(b.phone_number)
                metadata["source"] = "Whatsapp"
                print(f"[VECTOR_STORE] Storing WhatsApp block {bid} with phone_number: {b.phone_number}")
            elif "whatsapp" in thread_id_lower:
                metadata["source"] = "Whatsapp"
                print(f"[VECTOR_STORE] Storing WhatsApp block {bid}")
            elif "reddit" in thread_id_lower:
                metadata["source"] = "Reddit"
                print(f"[VECTOR_STORE] Storing Reddit block {bid}")
            elif hasattr(b.root_post, 'post_id') and b.root_post.post_id:
                # Store both post_id and post_number if available
                metadata["post_id"] = str(b.root_post.post_id)
                if hasattr(b.root_post, 'post_number') and b.root_post.post_number:
                    metadata["post_number"] = str(b.root_post.post_number)
                metadata["source"] = "PakWheels"
                post_info = f"post_id: {b.root_post.post_id}"
                if hasattr(b.root_post, 'post_number') and b.root_post.post_number:
                    post_info += f", post_number: {b.root_post.post_number}"
                print(f"[VECTOR_STORE] Storing PakWheels block {bid} with {post_info}")
            else:
                metadata["source"] = "PakWheels"
                print(f"[VECTOR_STORE] Storing block {bid} with default source: PakWheels")

            # Coerce None -> safe strings (Chroma does NOT allow None)
            metadatas.append(metadata)

        # 4) Embed only the new docs and add them to Chroma
        embeddings = self.embedder.embed(docs)

        self.collection.add(
            ids=ids,
            documents=docs,
            metadatas=metadatas,
            embeddings=embeddings,
        )

        # 5) Persist blocks to disk for future app restarts
        self._save_blocks()

    # ------------------------------------------------------------------
    # Time-aware, diversity-aware, enrichment-aware query
    # ------------------------------------------------------------------
    def query(
        self,
        query_text: str,
        top_k: int = 5,
        start_dt: Optional[datetime] = None,
        end_dt: Optional[datetime] = None,
        variants: Optional[List[str]] = None,
        sentiments: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> List[RetrievedBlock]:
        """
        Semantic search for most relevant blocks, with:

        - Optional time window filter:
          * keep only blocks whose [start_datetime, end_datetime] overlaps
            [start_dt, end_dt].

        - Optional soft filters on:
          * variants (e.g. ["PHEV", "HEV"])
          * sentiments (e.g. ["negative"])
          * tags (e.g. ["fuel_economy", "brake_vibration"])

          These are "soft" in the sense that:
          - Matching blocks are preferred.
          - Non-matching blocks can still appear to fill up `top_k`
            (overlapping and non-overlapping).

        - Simple diversity (MMR-ish) post-processing so we don't keep
          returning essentially identical blocks for broad questions.
        """
        if not self.embedder:
            raise RuntimeError("ChromaVectorStore requires an embedder to query.")

        # 1) Embed the query
        q_emb = self.embedder.embed([query_text])[0]

        # 2) Fetch a larger candidate set, then down-select with diversity
        fetch_k = max(top_k * 5, top_k)
        # For broad/statistical queries, allow fetching more data (up to 1000)
        # For specific queries, cap at 100
        max_cap = 1000 if top_k >= 300 else 100
        fetch_k = min(fetch_k, max_cap)

        # Query ChromaDB (no source filtering needed - each vector store is source-specific)
        res = self.collection.query(
            query_embeddings=[q_emb],
            n_results=fetch_k,
            include=["metadatas", "distances", "documents"],
        )

        # Debug: Log result count
        result_count = len(res.get("ids", [[]])[0]) if res.get("ids") else 0
        # print(f"[VECTOR_STORE] ChromaDB returned {result_count} results")  # Verbose - commented out

        ids_lists = res.get("ids") or [[]]
        dist_lists = res.get("distances") or [[]]
        meta_lists = res.get("metadatas") or [[]]

        if not ids_lists or not ids_lists[0]:
            return []

        ids = ids_lists[0]
        distances = dist_lists[0]
        metas = meta_lists[0] if meta_lists else []

        # Normalise filter values to lowercase for comparison
        variant_filter = {v.lower() for v in variants} if variants else None
        sentiment_filter = {s.lower() for s in sentiments} if sentiments else None
        tag_filter = {t.lower() for t in tags} if tags else None

        def _extract_meta(block_id: str, meta_index: int) -> Dict[str, Any]:
            """
            Merge metadata from Chroma with runtime attributes on ConversationBlock.
            """
            b = self._blocks_by_id.get(block_id)
            base_meta: Dict[str, Any] = {}
            if metas and 0 <= meta_index < len(metas):
                raw_meta = metas[meta_index] or {}
                # make a shallow copy to avoid mutating Chroma's internal dict
                base_meta.update(raw_meta)

            if b:
                # Runtime fields take precedence
                v = getattr(b, "dominant_variant", None) or base_meta.get("variant", "Unknown")
                s = getattr(b, "dominant_sentiment", None) or base_meta.get("sentiment", "unknown")
                tags_list = getattr(b, "aggregated_tags", None)
                if tags_list is None:
                    tags_str = base_meta.get("tags", "") or ""
                    tags_list = [t for t in tags_str.split(",") if t]

                summary = getattr(b, "summary", None) or base_meta.get("summary", "")

                base_meta["variant"] = v
                base_meta["sentiment"] = s
                base_meta["tags"] = tags_list
                base_meta["summary"] = summary
                if hasattr(b, 'phone_number') and b.phone_number:
                    base_meta["phone_number"] = b.phone_number
                    base_meta["source"] = "Whatsapp"
                elif hasattr(b.root_post, 'post_id') and b.root_post.post_id:
                    base_meta["post_id"] = b.root_post.post_id
                    if hasattr(b.root_post, 'post_number') and b.root_post.post_number:
                        base_meta["post_number"] = b.root_post.post_number
                    base_meta["source"] = "PakWheels"
                
                # Ensure source is set from metadata if not already set
                if "source" not in base_meta:
                    if "whatsapp" in str(b.thread_id).lower():
                        base_meta["source"] = "Whatsapp"
                    else:
                        base_meta["source"] = "PakWheels"

            return base_meta

        # 3) Build candidate RetrievedBlock list, applying time filters
        candidates: List[RetrievedBlock] = []
        blocks_not_in_memory = 0

        for idx, (block_id, dist) in enumerate(zip(ids, distances)):
            b = self._blocks_by_id.get(block_id)
            if not b:
                blocks_not_in_memory += 1
                continue

            # Time-window and year filter if requested
            b_start = getattr(b, "start_datetime", None)
            b_end = getattr(b, "end_datetime", None)

            # Parse datetime if stored as string
            if isinstance(b_start, str):
                try:
                    b_start = datetime.fromisoformat(b_start)
                    # Make timezone-aware if naive
                    if b_start.tzinfo is None:
                        b_start = b_start.replace(tzinfo=ZoneInfo("Asia/Karachi"))
                except Exception:
                    b_start = None
            # If already datetime but naive, make it aware
            elif isinstance(b_start, datetime) and b_start.tzinfo is None:
                b_start = b_start.replace(tzinfo=ZoneInfo("Asia/Karachi"))

            if isinstance(b_end, str):
                try:
                    b_end = datetime.fromisoformat(b_end)
                    # Make timezone-aware if naive
                    if b_end.tzinfo is None:
                        b_end = b_end.replace(tzinfo=ZoneInfo("Asia/Karachi"))
                except Exception:
                    b_end = None
            # If already datetime but naive, make it aware
            elif isinstance(b_end, datetime) and b_end.tzinfo is None:
                b_end = b_end.replace(tzinfo=ZoneInfo("Asia/Karachi"))

            # Time-window filter
            if start_dt or end_dt:
                # If we have no datetime info, skip when a window is requested
                if (start_dt or end_dt) and (not b_start and not b_end):
                    continue

                # Basic overlap check:
                # - if block starts after window end -> skip
                if end_dt and b_start and b_start > end_dt:
                    continue
                # - if block ends before window start -> skip
                if start_dt and b_end and b_end < start_dt:
                    continue

            score = 1.0 - float(dist)  # cosine distance -> similarity-ish
            rb = RetrievedBlock(block=b, score=score)
            rb.metadata = _extract_meta(block_id, idx)
            candidates.append(rb)

        # print(f"[VECTOR_STORE] After building candidates: {len(candidates)} blocks (blocks_not_in_memory={blocks_not_in_memory})")  # Verbose

        # Sample first 3 candidates to inspect metadata - Verbose logging disabled
        # if candidates and len(candidates) > 0:
        #     print(f"[VECTOR_STORE] Sample of first 3 candidates' metadata:")
        #     for i, cand in enumerate(candidates[:3]):
        #         meta = cand.metadata or {}
        #         variant = meta.get("variant", "N/A")
        #         tags = meta.get("tags", [])
        #         if isinstance(tags, str):
        #             tags_display = tags if tags else "empty"
        #         else:
        #             tags_display = ",".join(tags) if tags else "empty"
        #         print(f"  [{i+1}] variant={variant}, tags={tags_display}")

        if not candidates:
            print(f"[VECTOR_STORE] WARNING: No candidates after building list! ChromaDB returned {result_count} but none found in _blocks_by_id")
            return []

        # 4) Partition into "filter-matching" and "non-matching" (soft filters)
        def _matches_filters(rb: RetrievedBlock) -> bool:
            if not (variant_filter or sentiment_filter or tag_filter):
                return False  # no preference if no filters given

            meta = rb.metadata or {}
            v = str(meta.get("variant", "")).lower()
            s = str(meta.get("sentiment", "")).lower()
            t_list = [str(t).lower() for t in meta.get("tags", []) or []]

            if variant_filter and v in variant_filter:
                return True
            if sentiment_filter and s in sentiment_filter:
                return True
            if tag_filter and any(t in tag_filter for t in t_list):
                return True

            return False

        candidates_sorted = sorted(candidates, key=lambda rb: rb.score, reverse=True)

        if variant_filter or sentiment_filter or tag_filter:
            primary: List[RetrievedBlock] = []
            secondary: List[RetrievedBlock] = []

            for rb in candidates_sorted:
                if _matches_filters(rb):
                    primary.append(rb)
                else:
                    secondary.append(rb)

            ordered = primary + secondary
            # print(f"[VECTOR_STORE] After soft filtering: {len(primary)} matching filters, {len(secondary)} non-matching (filters: variants={variants}, sentiments={sentiments}, tags={tags})")  # Verbose
        else:
            ordered = candidates_sorted
            # print(f"[VECTOR_STORE] No soft filters applied, using all {len(ordered)} candidates")  # Verbose

        # 5) Simple diversity selection (token-overlap based) over the ordered list
        def _token_set(text: str) -> set:
            return set(text.lower().split())

        selected: List[RetrievedBlock] = []
        selected_token_sets: List[set] = []
        rejected_for_similarity = 0

        for cand in ordered:
            if len(selected) >= top_k:
                break

            cand_tokens = _token_set(cand.block.flattened_text)
            if not cand_tokens:
                # If empty token set, just accept it
                selected.append(cand)
                selected_token_sets.append(cand_tokens)
                continue

            too_similar = False
            for stoks in selected_token_sets:
                if not stoks:
                    continue
                overlap = len(cand_tokens & stoks) / max(len(cand_tokens), 1)
                # If large token overlap, skip this candidate to promote diversity
                if overlap > 0.80:
                    too_similar = True
                    break

            if too_similar:
                rejected_for_similarity += 1
                continue

            selected.append(cand)
            selected_token_sets.append(cand_tokens)

        # print(f"[VECTOR_STORE] After diversity filtering: {len(selected)} selected (rejected {rejected_for_similarity} for similarity, requested top_k={top_k})")  # Verbose

        # Fallback: if we filtered too aggressively, just take top_k by score
        if not selected:
            print(f"[VECTOR_STORE] WARNING: Diversity filtering removed all blocks! Using fallback: top {top_k} by score")
            selected = ordered[:top_k]

        # print(f"[VECTOR_STORE] Final result: Returning {len(selected)} blocks")  # Verbose
        return selected