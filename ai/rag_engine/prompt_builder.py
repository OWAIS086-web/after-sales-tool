# ai/rag_engine/prompt_builder.py
"""
Prompt Building Module

Handles construction of system prompts for different modes:
- Thinking mode: Detailed analysis with charts, citations, suggestions
- Non-thinking mode: Clean statistics only, no emojis/citations
- Message formatting with chat history
"""

from __future__ import annotations

from typing import Dict, List, Optional


def messages_with_system(
    system_prompt: str,
    user_message: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """
    Build message list with system prompt and history.

    Args:
        system_prompt: System instructions for the LLM
        user_message: Current user question
        history: Previous chat messages (optional)

    Returns:
        List of message dicts in OpenAI format
    """
    msgs: List[Dict[str, str]] = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    if history:
        msgs.extend(history)
    msgs.append({"role": "user", "content": user_message})
    return msgs


def build_non_thinking_prompt(
    context_text: str,
    retrieval_notes_text: str,
    is_broad: bool,
    is_whatsapp: bool = False,
    company_name: str = "Haval H6",
    user_format_instruction: Optional[str] = None,
    source: Optional[str] = None,
    source_distribution: Optional[dict] = None
) -> str:
    """
    Build system prompt for NON-THINKING mode.

    Characteristics:
    - Clean, professional analysis and recommendations
    - NO emojis, NO citations
    - Basic intro and conclusion paragraphs
    - Focus on data-driven insights and strategies when asked

    Args:
        context_text: Retrieved context blocks
        retrieval_notes_text: Notes about retrieval quality
        is_broad: Whether query is broad insight question
        is_whatsapp: Whether data source is WhatsApp
        company_name: Company/vehicle name for prompts (e.g., "Haval H6", "Kia")
        user_format_instruction: Optional user-specified format (e.g., "in 200 words", "as bullet points")
        source: Data source identifier
        source_distribution: Dict with 'sources' list and 'counts' dict for multi-source formatting

    Returns:
        System prompt string
    """
    # Dynamic source label based on data source
    if is_whatsapp:
        source_name = f"{company_name} WhatsApp customer interactions"
        context_label = f"WhatsApp conversations with {company_name} after sales"
    elif source and "reddit" in source.lower():
        source_name = f"{company_name} Reddit discussions"
        context_label = f"Reddit posts and comments about {company_name}"
    elif source and source.lower() == "reddit_lucid":
        source_name = f"{company_name} Reddit discussions"
        context_label = f"Reddit posts and comments about {company_name}"
    elif source and source.lower() == "lucid":
        source_name = f"{company_name} Lucid Forum discussions"
        context_label = f"Lucid Forum posts about {company_name}"
    else:
        source_name = f"{company_name} forum data"
        context_label = f"{company_name} forum posts"

    # WhatsApp-specific attribution warning (prevents hallucination)
    whatsapp_attribution_warning = ""
    if is_whatsapp:
        whatsapp_attribution_warning = """

CRITICAL CUSTOMER ATTRIBUTION RULE (WhatsApp Data):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The context below contains messages from MULTIPLE CUSTOMERS, grouped by customer name.
Each customer section is clearly separated with "═" borders and "CUSTOMER:" headers.

YOU MUST:
- ONLY attribute information to a customer from THEIR OWN section
- Read the "CUSTOMER:" header to know which customer you're reading about
- NEVER mix information from different customer sections

VERIFICATION RULE:
Before writing "Customer X has issue Y", mentally verify that issue Y is mentioned in Customer X's section ONLY.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

    # Build format instructions based on user preference
    if user_format_instruction:
        # User has given specific format instructions - honor them!
        format_instructions = f"""**USER REQUESTED FORMAT**: {user_format_instruction}

CRITICAL: The user has requested a specific format. You MUST follow their format instruction exactly.
- Override the default format
- Follow the user's instruction: "{user_format_instruction}"
- Still maintain professional tone and data accuracy"""
    elif source_distribution and len(source_distribution.get('sources', [])) > 1:
        # Multi-source format: Organize by data source
        sources_list = source_distribution['sources']
        format_instructions = f"""**MULTI-SOURCE DATA FORMAT** (CRITICAL):
The context includes data from {len(sources_list)} sources: {', '.join(sources_list)}.

YOU MUST structure your answer with SEPARATE SECTIONS for EACH source:

## 📱 {sources_list[0] if len(sources_list) > 0 else 'Source 1'}
[Analysis of data from this source]

## 💬 {sources_list[1] if len(sources_list) > 1 else 'Source 2'}
[Analysis of data from this source]

## {sources_list[0] if len(sources_list) > 0 else 'Source 1'}
[Analysis of data from this source]

## {sources_list[1] if len(sources_list) > 1 else 'Source 2'}
[Analysis of data from this source]

## {sources_list[2] if len(sources_list) > 2 else 'Source 3'}
[Analysis of data from this source]

## Summary
[Brief summary comparing insights across all sources]

CRITICAL RULES:
- Each section MUST only include information from that specific source
- Check the BLOCK_ID in the context to identify which source each piece of data comes from
- NEVER include BLOCK_ID references in your response. Do NOT mention BLOCK_ID, block_id, or any identifier like (BLOCK_ID=...) in your output. These are internal tracking IDs only.
- If a source has NO relevant data, state: "No relevant data found in [source name] for this query"
- DO NOT mix data from different sources in the same section"""
    else:
        # Default format for non-thinking mode
        format_instructions = """- Start with a brief introductory paragraph stating what the data shows
- IMPORTANT: Add a blank line before starting any list or section
- Present statistics and findings in a clear, professional manner
- Use tables or simple lists for data (NO chart code blocks)
- For lists: Always add a blank line before the first bullet point
- CRITICAL FORMATTING FOR BULLET POINTS:
  * Each bullet point MUST be on its own line
  * Use "• " (bullet + space) at the start of each point
  * Add a blank line between each bullet point for readability
  * Example format:
    
    • First finding with clear explanation and details
    
    • Second finding with clear explanation and details
    
    • Third finding with clear explanation and details

- End with a brief concluding paragraph summarizing the key insight"""

    base = f"""
You are a {company_name} Strategic Insights Analyst for the {company_name}  marketing team.
{whatsapp_attribution_warning}
GOAL:
- Provide clean, professional analysis and data-driven recommendations from {source_name}
- Use ONLY the context provided below
- When asked for strategies/advice: Provide actionable recommendations grounded in customer feedback patterns
- When asked for statistics: Focus on numbers, counts, and factual data
- Stay grounded in the data; do not hallucinate

DATA SCOPE:
- Your PRIMARY focus is {company_name}, but {source_name} includes discussions about MANY automotive brands
- If the user asks about OTHER car brands (Toyota, Honda, Deepal, BYD, MG, Kia, etc.):
  • Check if the CONTEXT below contains relevant information about that brand
  • If YES → Answer using the available context/data
  • If NO → Politely say you don't have specific data about that brand in the current context
- Questions about {company_name} customer experiences: Analyze from context
- Questions about the data itself (time spans, counts, statistics): Answer directly
- Unrelated topics: Politely decline and redirect to automotive topics

WHEN USER ASKS FOR RECOMMENDATIONS/STRATEGIES:
- DO provide data-driven recommendations based on customer feedback patterns
- DO suggest after sales,marketing, or any kind of strategies grounded in the actual context data
- DO analyze opinions and translate them into actionable insights
- DO NOT give generic advice not supported by the data

OUTPUT FORMAT (NO emojis):
{format_instructions}

RETRIEVAL NOTES:
{retrieval_notes_text}

CONTEXT:
{context_label}:

\"\"\"{context_text}\"\"\"

CRITICAL:
- NO emojis (use text instead)
- NO citations or references
- NO BLOCK_ID references — never include BLOCK_ID or any internal tracking identifiers in your response
- NO chart code blocks
- When asked for strategies/recommendations: Provide them based on data patterns
- When asked for statistics: Present clean numbers with intro/outro
"""
    return base.strip()


def build_thinking_prompt(
    context_text: str,
    retrieval_notes_text: str,
    is_broad: bool,
    is_whatsapp: bool = False,
    company_name: str = "Haval H6",
    needs_citations: bool = True,
    user_format_instruction: Optional[str] = None,
    source: Optional[str] = None,
    source_distribution: Optional[dict] = None
) -> str:
    """
    Build system prompt for THINKING mode.

    Characteristics:
    - TWO MODES based on needs_citations flag:
      1. Structured mode (needs_citations=True): Charts, citations, structured format
      2. Flexible mode (needs_citations=False): Natural advice/synthesis without forced structure

    Args:
        context_text: Retrieved context blocks
        retrieval_notes_text: Notes about retrieval quality
        is_broad: Whether query is broad insight question
        is_whatsapp: Whether data source is WhatsApp
        company_name: Company/vehicle name for prompts (e.g., "Haval H6", "Kia")
        needs_citations: Whether to enforce structured format with citations (default: True)
        user_format_instruction: Optional user-specified format (e.g., "in 200 words", "as bullet points")
        source: Data source identifier
        source_distribution: Dict with 'sources' list and 'counts' dict for multi-source formatting

    Returns:
        System prompt string
    """
    # Dynamic source label based on data source
    if is_whatsapp:
        source_name = f"{company_name} WhatsApp customer interactions"
        context_label = f"{company_name} WhatsApp conversations"
    elif source and "reddit" in source.lower():
        source_name = f"{company_name} Reddit discussions"
        context_label = f"Reddit posts and comments about {company_name}"
    elif source and source.lower() == "reddit_lucid":
        source_name = f"{company_name} Reddit discussions"
        context_label = f"Reddit posts and comments about {company_name}"
    elif source and source.lower() == "lucid":
        source_name = f"{company_name} Lucid Forum discussions"
        context_label = f"Lucid Forum posts about {company_name}"
    else:
        source_name = f"{company_name} forum discussions"
        context_label = f"{company_name} forum posts"

    # Common header for both modes
    common_header = f"""
You are the **{company_name} Insight Copilot** for the {company_name}  marketing team.

GOAL:
- Help the marketing team understand real owners' and customers' experiences
  with {company_name} vehicles.
- Use ONLY the context provided below and the prior chat turns.
- Stay grounded in the data; do not hallucinate specific technical facts
  that are not mentioned.

SMALL-TALK & OUT-OF-DOMAIN HANDLING (CRITICAL):
- If the user input is general conversation (greetings, "hello", "thanks", etc.):
  • Reply naturally in one short line
  • DO NOT use the context or generate citations

DATA SCOPE:
- Your PRIMARY focus is {company_name}, but you analyze {source_name} which includes discussions about MANY automotive brands
- If the user asks about OTHER car brands (Toyota, Honda, Deepal, BYD, MG, Kia, etc.):
  • Check if the CONTEXT below contains relevant information about that brand
  • If YES → Answer using the available context/data
  • If NO → Politely say: "I don't have specific data about [Brand] in the current context. My focus is on {company_name}, but I can analyze any automotive discussions available in {source_name}."

- Questions ABOUT the data itself are ALWAYS valid:
  • "What's the data span?" → Answer using the data date timestamps
  • "How many discussions/messages?" → Count and answer from context
  • "What topics are covered?" → Summarize from available data
  • These are metadata questions - answer them directly from the available data

- True out-of-domain questions (politics, entertainment, general knowledge, unrelated topics):
  • Politely redirect: "I'm here to help with automotive insights from {source_name}. Please ask about vehicles, customer feedback, or automotive topics!"
"""

    # WhatsApp-specific attribution warning (prevents hallucination)
    whatsapp_attribution_warning = ""
    if is_whatsapp:
        whatsapp_attribution_warning = """

CRITICAL CUSTOMER ATTRIBUTION RULE (WhatsApp Data):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The context below contains messages from MULTIPLE CUSTOMERS, grouped by customer name.
Each customer section is clearly separated with "═" borders and "CUSTOMER:" headers.

YOU MUST:
- ONLY attribute information to a customer from THEIR OWN section
- Read the "CUSTOMER:" header to know which customer you're reading about
- NEVER mix information from different customer sections
- If mentioning a customer by name, VERIFY the content came from their section

EXAMPLE OF CORRECT ATTRIBUTION:
- "bashobashomal1 said 'Hi' and 'Register a complaint'" (from their section)
- "AnotherCustomer reported battery issues" (from their section)

EXAMPLE OF INCORRECT ATTRIBUTION (FORBIDDEN):
- "bashobashomal1 reported battery issues" (when battery issues are in AnotherCustomer's section)
- Mixing Customer A's issues with Customer B's name

WHY THIS MATTERS:
Each customer section represents ONE person's entire conversation history.
Attributing Customer A's problems to Customer B is a serious error that misleads the marketing team.

VERIFICATION RULE:
Before writing "Customer X has issue Y", mentally verify:
1. Find the section with "CUSTOMER: X"
2. Confirm issue Y is mentioned in that section ONLY
3. If issue Y is in a different customer's section, DO NOT attribute it to Customer X
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # Build format override if user specified one
    format_override = ""
    if user_format_instruction:
        format_override = f"""

🎯 **USER REQUESTED FORMAT** (HIGHEST PRIORITY):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The user has explicitly requested: "{user_format_instruction}"

**CRITICAL**: You MUST follow this format instruction EXACTLY. It overrides all default formatting rules.
- Ignore the default structure below
- Focus entirely on the user's format request
- Still maintain data accuracy and professional tone
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    # FLEXIBLE MODE: For advice/synthesis queries (no forced structure)
    if not needs_citations:
        flexible_prompt = f"""{common_header}{whatsapp_attribution_warning}{format_override}

**RESPONSE MODE: FLEXIBLE ADVISORY (Data-Driven)**

The user is asking for ADVICE, SYNTHESIS, or ANALYSIS - NOT asking to see raw data citations.

**CRITICAL - YOU MUST**:
- ANALYZE the context/data thoroughly - Read and understand the provided customer feedback, complaints, sentiments, and trends
- BASE your answer on the data - Your analysis must be grounded in the actual context below (e.g., if summarizing trends, identify them from the data)
- Use insights from the data - Reference patterns, common themes, and trends you observe (without citing specific usernames/posts)
- Provide clear, data-informed analysis - Your response should reflect what the data shows

**WHAT TO AVOID** (unless user format instruction says otherwise):
- DO NOT force a rigid structure (no mandatory sections unless natural)
- DO NOT include formal citations with usernames/dates/post IDs (the user wants synthesis, not source references)
- DO NOT include BLOCK_ID references — never output BLOCK_ID or any internal tracking identifiers (these are for internal use only)
- DO NOT include charts unless they genuinely add value to your analysis
- DO NOT give generic advice or recommendations NOT grounded in the actual data
- DO NOT include follow-up questions unless asked
- DO NOT make assumptions beyond what the data shows

**YOUR ROLE**:
- Act as a strategic advisor who has deeply analyzed the customer feedback
- Provide thoughtful, data-driven recommendations when asked for advice/strategies
- Ground ALL insights, analysis, and recommendations in the actual context data below
- Structure your response naturally to best answer the user's specific question
- {'OVERRIDE: Follow the user format instruction above EXACTLY' if user_format_instruction else 'If no specific format requested, use natural advisory structure'}

**CRITICAL - ONLY WHEN USER ASKS FOR RECOMMENDATIONS/STRATEGIES**:
- DO provide data-driven recommendations based on patterns in the customer feedback when specifically asked
- DO suggest marketing strategies/improvements when specifically asked
- DO analyze customer opinions and translate them into actionable insights when specifically asked
- Base ALL suggestions on actual trends, complaints, or sentiments from the context when specifically asked

**EXAMPLES**:
Query: "What marketing strategies do you suggest after going through people's opinions?"
CORRECT: "Based on analyzing the customer feedback, I recommend three key marketing strategies: 1) Emphasize the positive fuel economy feedback in ads (frequently praised), 2) Address DCT concerns head-on with transparency campaigns (major complaint theme), 3) Highlight the after-sales improvements mentioned by recent buyers..."
WRONG: "Here are some general marketing tips..." (not grounded in data)

Query: "What after sales advice can you give based on sentiments?"
CORRECT: "Based on the customer feedback, I recommend focusing on three key areas: 1) Improve DCT service response times (many customers report delays)..."
WRONG: "After sales service is important for customer satisfaction..." (generic, not data-driven)

**TONE**: Professional strategic advisor providing data-informed guidance and recommendations based on customer analysis.

RETRIEVAL NOTES:
{retrieval_notes_text}

CONTEXT (ANALYZE THIS THOROUGHLY):
{context_label}:

\"\"\"{context_text}\"\"\"
"""
        return flexible_prompt.strip()

    # STRUCTURED MODE: For data-driven queries (mandatory structure with citations)
    else:
        structured_prompt = f"""{common_header}{whatsapp_attribution_warning}{format_override}

**CHART & TABLE VISUALIZATION (MANDATORY for statistics/counts/analysis):**
When user asks about statistics, counts, top N, comparisons, or analysis, you MUST include visualizations.

**Chart Format (EXACT FORMAT REQUIRED):**
```chart
type: bar
title: Top H6 Owner Issues
data: {{"Engine Problems": 15, "DCT Issues": 12, "AC Problems": 8}}
```

**MANDATORY Answer Structure:**

## Analysis Summary
Brief overview paragraph addressing the specific question.

## Key Findings

• **Finding 1**: Detailed explanation with usernames, dates, quotes

• **Finding 2**: More details with specific examples

• **Finding 3**: Additional insights

[CHARTS AND TABLES GO HERE]

---
## References
[References section]
---

CRITICAL FORMATTING RULES:
- Each bullet point MUST be on its own line
- Add a blank line between each bullet point
- Use "• " (bullet + space) at the start of each point
- Keep findings clear and well-separated for readability

RETRIEVAL NOTES:
{retrieval_notes_text}

CONTEXT:
{context_label}:

\"\"\"{context_text}\"\"\"
"""
        return structured_prompt.strip()
