# ai/rag_engine/format_detector.py
"""
Format Instruction Detection Module

Uses LLM to detect if user has given specific format instructions
in their query (e.g., "summarize in 200 words", "give bullet points").
"""

from __future__ import annotations
from typing import Optional
from ai.llm_client import BaseLLMClient


def detect_user_format_instruction(query: str, llm: BaseLLMClient) -> Optional[str]:
    """
    Use LLM to detect if user has given specific format instructions.

    This is a PRODUCTION approach that handles ANY format the user might request,
    without hardcoding keywords.

    Args:
        query: User's query
        llm: LLM client for detection (should be fast, like Grok-3-fast)

    Returns:
        Format instruction string if detected (e.g., "in 200 words"), None otherwise

    Examples:
        Input: "Summarize this in 200 words please"
        Output: "in 200 words"

        Input: "Give me bullet points about Haval issues"
        Output: "as bullet points"

        Input: "What are the top problems?"
        Output: None (no format instruction)

    Cost: ~$0.0001 (Grok-3-fast, ~50 tokens)
    Latency: ~0.1s
    """
    detection_prompt = f"""Analyze this user query to detect if they have given a SPECIFIC FORMAT INSTRUCTION for how they want the response.

**USER QUERY**: "{query}"

**YOUR TASK**:
Determine if the user has explicitly requested a specific format, structure, length, or style for the answer.

**FORMAT TYPES TO DETECT**:

1. **Word/Character Count**:
   - "in 200 words", "in 150 words", "500 word summary"
   - "in 2 paragraphs", "in 3 sentences"
   - "keep it under 100 words", "maximum 250 words"

2. **List Structures**:
   - "as bullet points", "give me bullets", "bullet form"
   - "numbered list", "as a list", "list format"
   - "in point form", "key points only"

3. **Table/Visual Formats**:
   - "in table format", "as a table", "create a table"
   - "in a spreadsheet format", "tabular form"
   - "comparison table", "side by side"

4. **Document Types**:
   - "as a report", "write a report", "formal report"
   - "as an essay", "essay format"
   - "as a memo", "memo format"
   - "executive summary", "brief summary"

5. **Paragraph Styles**:
   - "in paragraph form", "as paragraphs"
   - "detailed explanation", "elaborate", "in detail"
   - "brief overview", "quick summary", "concise"
   - "step by step", "sequential format"

6. **Tone/Style Modifiers**:
   - "in simple language", "explain like I'm 5"
   - "technical terms", "professional language"
   - "conversational tone", "casual style"

7. **Specific Structures**:
   - "pros and cons", "advantages and disadvantages"
   - "Q&A format", "question and answer"
   - "timeline format", "chronological order"
   - "grouped by category", "categorize"

8. **Comparison Formats**:
   - "compare and contrast", "side by side comparison"
   - "before and after", "old vs new"

9. **Length Indicators**:
   - "briefly", "in brief", "short answer"
   - "comprehensively", "exhaustively", "in depth"
   - "one line", "one sentence"

**EXAMPLES** (Learn the pattern):

✅ Query: "Summarize this in 200 words please"
   Response: "in 200 words"

✅ Query: "Give me bullet points about Haval issues"
   Response: "as bullet points"

✅ Query: "Create a detailed report about complaints"
   Response: "as a detailed report"

✅ Query: "List the top 10 problems in table format"
   Response: "in table format with top 10 problems"

✅ Query: "Explain H6 features briefly in 3 paragraphs"
   Response: "briefly in 3 paragraphs"

✅ Query: "Compare Haval and Kia side by side"
   Response: "side by side comparison"

✅ Query: "Give me a quick summary under 100 words"
   Response: "quick summary under 100 words"

✅ Query: "Write this as a professional memo to management"
   Response: "as a professional memo"

✅ Query: "Break this down step by step for my team"
   Response: "step by step breakdown"

✅ Query: "Categorize the complaints by severity in a numbered list"
   Response: "categorized by severity in numbered list"

❌ Query: "What are the top 10 problems?"
   Response: None (asking for top 10 is CONTENT, not FORMAT)

❌ Query: "Explain H6 features"
   Response: None (no format instruction)

❌ Query: "Tell me about brake issues"
   Response: None (no format specified)

❌ Query: "Summarize"
   Response: None (too vague, no specific format)

**CRITICAL RULES**:
1. Only detect EXPLICIT format instructions (user directly states HOW they want it formatted)
2. Do NOT detect CONTENT requests (what they want to know about)
   - "top 10 problems" = content (WHAT), not format (HOW)
   - "in bullet points" = format (HOW)
3. Combine multiple format hints if present:
   - "Give me 5 bullet points about X" → "5 bullet points"
   - "Write a brief 200-word report" → "brief 200-word report"
4. Keep response SHORT (2-8 words max)
5. If NO format instruction detected, respond with ONLY: None
6. Do NOT include quotation marks or extra explanation

**YOUR RESPONSE** (ONLY the format instruction or "None"):"""

    try:
        messages = [{"role": "user", "content": detection_prompt}]
        response = llm.generate(messages, max_tokens=30, temperature=0.0)

        detected = response.content.strip().strip('"\'').strip('.')

        # Clean up the response
        if detected.lower() == "none" or detected.lower() == "null" or not detected:
            return None

        # Validate it's a reasonable format instruction (not a full sentence)
        if len(detected.split()) > 15:  # Too long, probably not a format instruction
            print(f"[FormatDetector] Detected format too long, ignoring: '{detected}'")
            return None

        print(f"[FormatDetector] ✅ Detected user format: '{detected}'")
        return detected

    except Exception as e:
        print(f"[FormatDetector] Error during detection: {e}")
        return None
