# ai/cross_platform/engine.py
"""
Cross-Platform Engine

Retrieves information from multiple platforms (PakWheels, Reddit, WhatsApp)
and combines the results for comprehensive answers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ai.enrichment import EnrichmentState
from ai.llm_client import BaseLLMClient
from ai.vector_store import ChromaVectorStore, RetrievedBlock


class CrossPlatformEngine:
    """
    Cross-platform query engine that retrieves from multiple sources.
    
    Features:
    - Retrieves from PakWheels, Reddit, and WhatsApp stores
    - Combines and deduplicates results
    - Preserves source attribution
    - Uses same LLM and RAG infrastructure as individual platforms
    """

    def __init__(
        self,
        pakwheels_store: Optional[ChromaVectorStore] = None,
        reddit_store: Optional[ChromaVectorStore] = None,
        whatsapp_store: Optional[ChromaVectorStore] = None,
        llm: Optional[BaseLLMClient] = None,
        k: int = 7,  # Increased from 5 to 7 for more comprehensive coverage
        state: Optional[EnrichmentState] = None,
        max_block_chars: int = 2048,
        company_id: str = "haval",
    ):
        """
        Initialize cross-platform engine.

        Args:
            pakwheels_store: Vector store for PakWheels forum data
            reddit_store: Vector store for Reddit discussions
            whatsapp_store: Vector store for WhatsApp conversations
            llm: LLM client for query processing
            k: Number of results to retrieve per platform (default: 7)
            state: Enrichment state with known variants/tags
            max_block_chars: Maximum characters per context block
            company_id: Company identifier (e.g., "haval", "kia")
        """
        self.stores = {}
        
        # Add available stores
        if pakwheels_store is not None:
            self.stores["pakwheels"] = pakwheels_store
            print(f"[CrossPlatform] PakWheels store added - Collection size: {pakwheels_store.count() if hasattr(pakwheels_store, 'count') else 'unknown'}")
        if reddit_store is not None:
            self.stores["reddit"] = reddit_store
            print(f"[CrossPlatform] Reddit store added - Collection size: {reddit_store.count() if hasattr(reddit_store, 'count') else 'unknown'}")
        if whatsapp_store is not None:
            self.stores["whatsapp"] = whatsapp_store
            print(f"[CrossPlatform] WhatsApp store added - Collection size: {whatsapp_store.count() if hasattr(whatsapp_store, 'count') else 'unknown'}")
            
        self.llm = llm
        self.k = k
        self.state = state or EnrichmentState()
        self.max_block_chars = max_block_chars
        self.company_id = company_id
        
        print(f"[CrossPlatform] Initialized with {len(self.stores)} stores: {list(self.stores.keys())}")
        if len(self.stores) == 0:
            print("[CrossPlatform] WARNING: No stores were initialized! This will result in empty responses.")

    def retrieve_from_all_platforms(
        self,
        query: str,
        k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[RetrievedBlock]]:
        """
        Retrieve results from all available platforms.

        Args:
            query: User query string
            k: Number of results per platform (uses self.k if None)
            filter_dict: Optional metadata filters

        Returns:
            Dictionary mapping platform names to lists of retrieved blocks
            Example: {
                "pakwheels": [block1, block2, ...],
                "reddit": [block3, block4, ...],
                "whatsapp": [block5, block6, ...]
            }
        """
        k = k or self.k
        results = {}
        
        print(f"[CrossPlatform] Starting retrieval from {len(self.stores)} platforms for query: '{query}'")
        
        for platform, store in self.stores.items():
            try:
                print(f"[CrossPlatform] Searching {platform}...")
                blocks = store.search(
                    query=query,
                    k=k,
                    filter_dict=filter_dict
                )
                results[platform] = blocks
                print(f"[CrossPlatform] Retrieved {len(blocks)} blocks from {platform}")
                if len(blocks) > 0:
                    print(f"[CrossPlatform]   - Top result similarity: {blocks[0].similarity:.4f}")
                else:
                    print(f"[CrossPlatform]   - WARNING: No results found for {platform}")
            except Exception as e:
                print(f"[CrossPlatform] Error retrieving from {platform}: {e}")
                import traceback
                traceback.print_exc()
                results[platform] = []
        
        total_blocks = sum(len(blocks) for blocks in results.values())
        print(f"[CrossPlatform] Total blocks retrieved: {total_blocks}")
        
        return results

    def combine_results(
        self,
        platform_results: Dict[str, List[RetrievedBlock]],
        max_total_blocks: int = 20  # Increased from 15 to 20 for more comprehensive answers
    ) -> List[Tuple[str, RetrievedBlock]]:
        """
        Combine and rank results from multiple platforms with balanced representation.

        Args:
            platform_results: Dictionary mapping platform names to retrieved blocks
            max_total_blocks: Maximum number of blocks to return (default: 20)

        Returns:
            List of tuples (platform_name, block) sorted by relevance score,
            ensuring each platform gets at least min_per_platform results if available
        """
        # Count available platforms with results
        platforms_with_results = [p for p, blocks in platform_results.items() if len(blocks) > 0]
        num_platforms = len(platforms_with_results)
        
        if num_platforms == 0:
            print(f"[CrossPlatform] No results from any platform")
            return []
        
        # Calculate minimum blocks per platform to ensure balanced representation
        min_per_platform = max(3, max_total_blocks // (num_platforms * 2))
        
        print(f"[CrossPlatform] Combining results from {num_platforms} platforms")
        print(f"[CrossPlatform] Ensuring at least {min_per_platform} blocks per platform")
        
        # Step 1: Take top min_per_platform from each platform (guaranteed representation)
        guaranteed_results = []
        for platform in platforms_with_results:
            blocks = platform_results[platform][:min_per_platform]
            for block in blocks:
                guaranteed_results.append((platform, block))
            print(f"[CrossPlatform]   - {platform}: Added {len(blocks)} guaranteed blocks")
        
        # Step 2: Collect remaining blocks from all platforms
        remaining_results = []
        for platform in platforms_with_results:
            blocks = platform_results[platform][min_per_platform:]
            for block in blocks:
                remaining_results.append((platform, block))
        
        # Step 3: Sort remaining blocks by similarity
        remaining_results.sort(key=lambda x: x[1].similarity, reverse=True)
        
        # Step 4: Combine guaranteed + best remaining up to max_total_blocks
        remaining_slots = max_total_blocks - len(guaranteed_results)
        if remaining_slots > 0:
            guaranteed_results.extend(remaining_results[:remaining_slots])
        
        # Step 5: Sort final results by similarity for coherent context
        guaranteed_results.sort(key=lambda x: x[1].similarity, reverse=True)
        
        # Print distribution summary
        platform_counts = {}
        for platform, _ in guaranteed_results:
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        print(f"[CrossPlatform] Final distribution: {platform_counts}")
        print(f"[CrossPlatform] Total blocks: {len(guaranteed_results)}")
        
        return guaranteed_results

    def build_combined_context(
        self,
        combined_results: List[Tuple[str, RetrievedBlock]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Build context string and sources list from combined results.

        Args:
            combined_results: List of (platform, block) tuples

        Returns:
            Tuple of (context_string, sources_list)
        """
        context_parts = []
        sources = []
        
        # Group results by platform for better organization
        platform_groups = {}
        for platform, block in combined_results:
            if platform not in platform_groups:
                platform_groups[platform] = []
            platform_groups[platform].append(block)
        
        # Build context with clear platform sections
        idx = 1
        for platform in ["pakwheels", "reddit", "whatsapp"]:
            if platform not in platform_groups:
                continue
                
            platform_label = platform.upper()
            if platform == "pakwheels":
                platform_label = "PAKWHEELS FORUM"
            elif platform == "reddit":
                platform_label = "REDDIT DISCUSSIONS"
            elif platform == "whatsapp":
                platform_label = "WHATSAPP CONVERSATIONS"
            
            context_parts.append(f"\n{'='*70}")
            context_parts.append(f"SOURCE: {platform_label}")
            context_parts.append(f"{'='*70}\n")
            
            for block in platform_groups[platform]:
                # Extract metadata
                author = "Unknown"
                date = "Unknown"
                additional_info = ""
                
                if hasattr(block, 'metadata') and block.metadata:
                    if platform == "whatsapp":
                        author = block.metadata.get("customer_name", "Customer")
                        date = block.metadata.get("date", "Unknown")
                        phone = block.metadata.get("phone", "")
                        if phone:
                            additional_info = f" | Phone: {phone}"
                    elif platform in ["pakwheels", "reddit"]:
                        author = block.metadata.get("username", "Anonymous")
                        date = block.metadata.get("date", "Unknown")
                        if platform == "pakwheels":
                            thread = block.metadata.get("thread_title", "")
                            if thread:
                                additional_info = f" | Thread: {thread}"
                        elif platform == "reddit":
                            subreddit = block.metadata.get("subreddit", "")
                            if subreddit:
                                additional_info = f" | r/{subreddit}"
                
                # Build source entry
                context_parts.append(f"[{idx}] Author: {author} | Date: {date}{additional_info}")
                context_parts.append(f"Relevance: {block.similarity:.3f}")
                context_parts.append("---")
                context_parts.append(block.text.strip())
                context_parts.append("")  # Empty line for spacing
                
                # Build source metadata for frontend
                source = {
                    "index": idx,
                    "platform": platform,
                    "platform_label": platform_label,
                    "similarity": round(block.similarity, 3),
                    "author": author,
                    "date": date,
                    "text": block.text[:300] + "..." if len(block.text) > 300 else block.text,
                }
                
                # Add platform-specific metadata
                if hasattr(block, 'metadata') and block.metadata:
                    if platform == "whatsapp":
                        source["customer"] = block.metadata.get("customer_name", "Unknown")
                        source["phone"] = block.metadata.get("phone", "")
                    elif platform == "pakwheels":
                        source["thread"] = block.metadata.get("thread_title", "")
                        source["post_id"] = block.metadata.get("post_id", "")
                    elif platform == "reddit":
                        source["subreddit"] = block.metadata.get("subreddit", "")
                        source["post_id"] = block.metadata.get("post_id", "")
                
                sources.append(source)
                idx += 1
        
        context = "\n".join(context_parts)
        return context, sources

    def build_cross_platform_prompt(
        self,
        query: str,
        context: str,
        sources: List[Dict[str, Any]]
    ) -> str:
        """
        Build prompt for cross-platform query answering.

        Args:
            query: User query
            context: Combined context from all platforms
            sources: List of source metadata

        Returns:
            Formatted prompt string
        """
        # Count sources per platform
        platform_counts = {}
        for source in sources:
            platform = source["platform"]
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        platform_summary = []
        if "pakwheels" in platform_counts:
            platform_summary.append(f"PakWheels Forum ({platform_counts['pakwheels']} discussions)")
        if "reddit" in platform_counts:
            platform_summary.append(f"Reddit ({platform_counts['reddit']} posts)")
        if "whatsapp" in platform_counts:
            platform_summary.append(f"WhatsApp ({platform_counts['whatsapp']} conversations)")
        
        platform_list = ", ".join(platform_summary)
        
        prompt = f"""You are an expert AI assistant analyzing customer feedback and discussions from multiple data sources.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
USER QUESTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{query}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE DATA SOURCES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{platform_list}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RETRIEVED INFORMATION (With Source Attribution)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL INSTRUCTIONS - READ CAREFULLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**YOUR ROLE:**
You are analyzing real customer feedback from three distinct sources:
1. **PakWheels Forum**: Public forum discussions with detailed technical discussions and owner experiences
2. **Reddit**: Community discussions with diverse opinions and comparisons
3. **WhatsApp**: Direct customer service conversations with dealers and support

**RESPONSE REQUIREMENTS:**

1. **COMPREHENSIVE ANALYSIS:**
   - Analyze ALL provided sources from all platforms
   - Synthesize information to provide a complete, unified answer
   - Identify patterns and common themes across platforms
   - Note any contradictions or differing perspectives

2. **EXPLICIT SOURCE ATTRIBUTION (MANDATORY):**
   - ALWAYS mention which platform(s) each piece of information comes from
   - Use clear platform labels: "According to PakWheels users...", "Reddit discussions show...", "WhatsApp customer inquiries reveal..."
   - Use citation numbers [1], [2], [3], etc. that match the source numbers above
   - For each major point, indicate: "This is reported on [Platform Name] [citation numbers]"

3. **STRUCTURE YOUR ANSWER:**
   - Start with a brief overview synthesizing all platforms
   - Break down by topic/theme (issues, features, feedback, etc.)
   - For each topic:
     * State the finding clearly
     * Cite which platform(s) it appears on: "**[PakWheels]** [1][3]" or "**[Reddit & WhatsApp]** [5][8][10]"
     * Include specific details from the sources
     * Note if multiple platforms agree or disagree
   - End with a summary of cross-platform consensus

4. **PLATFORM-SPECIFIC CONTEXT:**
   - **PakWheels**: Focus on technical details, owner experiences, community knowledge
   - **Reddit**: Note diverse opinions, comparisons, international perspectives
   - **WhatsApp**: Highlight direct customer concerns, dealer interactions, immediate issues

5. **HANDLING DIFFERENCES:**
   - If platforms show different perspectives, explicitly state: "While PakWheels users report X [1][2], Reddit discussions suggest Y [5][6]"
   - Don't hide contradictions - present them clearly
   - Offer balanced perspective when sources differ

6. **FORMATTING:**
   - Use **bold** for platform names: **[PakWheels]**, **[Reddit]**, **[WhatsApp]**
   - Use bullet points for clarity
   - Use citations: [1], [2], [3], etc.
   - Use section headers for different topics

7. **QUALITY STANDARDS:**
   - Be specific and detailed, not generic
   - Quote or paraphrase actual user comments when relevant
   - Provide context (dates, specific models, conditions when mentioned)
   - Distinguish between isolated reports and common patterns

**EXAMPLE FORMAT:**

Based on analysis of {platform_list}:

### Overview
[Brief synthesis of what all platforms say about the topic]

### [Topic 1]
**[PakWheels Forum]** [1][3]: [Detailed findings from PakWheels with specific examples]

**[Reddit Discussions]** [5][7]: [Detailed findings from Reddit with specific examples]

**[WhatsApp Conversations]** [9][10]: [Detailed findings from WhatsApp with specific examples]

**Cross-Platform Consensus**: [Summary of agreement/disagreement across platforms]

### [Topic 2]
[Continue same format...]

### Summary
[Final synthesis highlighting what's consistent across platforms and what varies]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NOW PROVIDE YOUR COMPREHENSIVE CROSS-PLATFORM ANALYSIS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        return prompt

    def query(
        self,
        query: str,
        k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        thinking_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Execute cross-platform query.

        Args:
            query: User query string
            k: Number of results per platform
            filter_dict: Optional metadata filters
            thinking_mode: Whether to use thinking mode for response

        Returns:
            Dictionary containing:
            - answer: Generated answer string
            - sources: List of source metadata with platform attribution
            - platform_results: Raw results from each platform
        """
        print(f"[CrossPlatform] Processing query: {query}")
        
        # Step 1: Retrieve from all platforms
        platform_results = self.retrieve_from_all_platforms(
            query=query,
            k=k,
            filter_dict=filter_dict
        )
        
        # Step 2: Combine and rank results
        combined_results = self.combine_results(platform_results)
        
        if not combined_results:
            return {
                "answer": "No information found across any platform.",
                "sources": [],
                "platform_results": platform_results
            }
        
        # Step 3: Build context and sources
        context, sources = self.build_combined_context(combined_results)
        
        # Step 4: Generate answer with LLM
        if self.llm:
            prompt = self.build_cross_platform_prompt(query, context, sources)
            
            try:
                # Use higher token limit for comprehensive cross-platform answers
                response = self.llm.generate(
                    prompt=prompt,
                    max_tokens=4000,  # Increased from 2000 for more detailed responses
                    temperature=0.7
                )
                
                # Extract text from response
                if hasattr(response, 'content'):
                    answer = response.content
                elif hasattr(response, 'text'):
                    answer = response.text
                else:
                    answer = str(response)
                
                # Add source summary at the end if not already included
                if "###" not in answer and len(sources) > 0:
                    # LLM might not have followed format, add sources manually
                    answer += "\n\n---\n\n### 📋 Sources\n\n"
                    for source in sources:
                        platform_emoji = "🚗" if source["platform"] == "pakwheels" else ("🔴" if source["platform"] == "reddit" else "💬")
                        answer += f"**[{source['index']}]** {platform_emoji} **{source['platform_label']}** | "
                        answer += f"Author: {source['author']} | Date: {source['date']}\n"
                        answer += f"_{source['text']}_\n\n"
                    
            except Exception as e:
                print(f"[CrossPlatform] LLM generation error: {e}")
                answer = "Error generating answer. Please try again."
        else:
            answer = "LLM not configured for cross-platform queries."
        
        print(f"[CrossPlatform] Generated answer with {len(sources)} sources from {len(platform_results)} platforms")
        
        return {
            "answer": answer,
            "sources": sources,
            "platform_results": platform_results,
            "combined_count": len(combined_results)
        }
