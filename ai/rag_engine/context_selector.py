"""
Dynamic Contextual Anchoring - LLM-Based Context Selection

Intelligently selects which chat messages are relevant for the current query.
Replaces the fixed 4-message window with intent-aware selection.

Advantages:
- Saves tokens by only using relevant messages
- Handles "summarize above" (last message only)
- Handles "compare to earlier" (search full history)
- Detects topic switches (ignore previous context)
"""

from typing import List, Dict, Optional
from ai.llm_client import BaseLLMClient
import json


def select_relevant_context(
    query: str,
    chat_history: List[Dict[str, str]],
    llm: BaseLLMClient,
    max_history_to_analyze: int = 10
) -> Dict:
    """
    Use LLM to intelligently select which messages from chat history are relevant.

    Args:
        query: User's current query
        chat_history: Full chat history (list of {"role": "user"/"assistant", "content": "..."})
        llm: LLM client for context selection
        max_history_to_analyze: Maximum number of recent messages to analyze (default: 10)

    Returns:
        Dictionary with:
        {
            "selected_messages": [List of selected message dicts],
            "context_type": "META_OP" | "DATA_REQUEST" | "CLARIFICATION" | "TOPIC_SWITCH" | "NEW_TOPIC",
            "reasoning": "Explanation of why these messages were selected",
            "window_size": int (number of messages selected)
        }

    Examples:
        >>> select_relevant_context("summarize above", history, llm)
        {
            "selected_messages": [last_message],
            "context_type": "META_OP",
            "reasoning": "User wants to summarize the previous answer",
            "window_size": 1
        }

        >>> select_relevant_context("what about Ahmed?", history, llm)
        {
            "selected_messages": [last_2_messages],
            "context_type": "DATA_REQUEST",
            "reasoning": "User asking about Ahmed, need recent context to understand topic",
            "window_size": 2
        }
    """
    # Handle empty history
    if not chat_history or len(chat_history) == 0:
        return {
            "selected_messages": [],
            "context_type": "NEW_TOPIC",
            "reasoning": "No chat history available",
            "window_size": 0
        }

    # Limit analysis to recent messages (for performance)
    recent_history = chat_history[-max_history_to_analyze:] if len(chat_history) > max_history_to_analyze else chat_history

    # Build history with indices for reference
    history_with_indices = []
    for idx, msg in enumerate(recent_history):
        role_label = "USER" if msg["role"] == "user" else "ASSISTANT"
        preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
        history_with_indices.append(f"[Message {idx}] {role_label}: {preview}")

    history_text = "\n".join(history_with_indices)

    # Context selection prompt
    selection_prompt = f"""You are a context selection specialist for a conversational RAG system.

**YOUR TASK**: Analyze the user's current query and determine which messages from the chat history are needed to understand it.

**CHAT HISTORY** (most recent {len(recent_history)} messages):
{history_text}

**CURRENT USER QUERY**: "{query}"

**CONTEXT TYPES**:

1. **META_OP** (Meta-operation on previous answer):
   - User wants to TRANSFORM/OPERATE ON the previous assistant response
   - Trigger words: "summarize above", "elaborate", "explain more", "clarify that", "expand on this"
   - Selection: **ONLY the last assistant message** (the answer they want to transform)
   - Example: "summarize above in 100 words" → Use only last assistant message

2. **DATA_REQUEST** (Request for new data with context):
   - User is asking for NEW information but references previous context
   - Trigger words: "what about X?", "show me Y", "compare X and Y"
   - Selection: **Last 1-3 messages** to understand topic/entities being discussed
   - Example: "what about Ahmed?" → Use last 2 messages to understand what topic Ahmed is related to

3. **CLARIFICATION** (Asking to clarify or compare with earlier discussion):
   - User references something discussed EARLIER in the conversation (not just previous message)
   - Trigger words: "like you said earlier", "compared to before", "you mentioned previously"
   - Selection: **Specific messages** mentioned + last message for current context
   - Example: "compare to what you said about pricing" → Find pricing message + last message

4. **TOPIC_SWITCH** (Completely new topic):
   - User is switching to a completely different topic, no relation to previous discussion
   - Trigger words: "now show me...", "switching topics...", completely unrelated query
   - Selection: **NONE** (no context needed, this is a fresh query)
   - Example: After discussing pricing, user asks "show me delivery complaints" → No context needed

5. **NEW_TOPIC** (First query or standalone):
   - First message in conversation OR query is fully standalone
   - Selection: **NONE**
   - Example: "What are the top complaints?" (first query in session)

**CRITICAL RULES**:

1. **Minimize Context**: ONLY select messages that are DIRECTLY relevant. More context = wasted tokens.

2. **Meta-Operations**: If user says "summarize above", "elaborate", "explain more" → They want to operate on the LAST ANSWER ONLY. Do NOT include more messages.

3. **Topic Switches**: If user switches topic (e.g., from pricing to delivery), do NOT include previous messages. Mark as TOPIC_SWITCH.

4. **Pronouns**: If user says "what about it?", "show me that", "and him?" → Need last 1-2 messages to resolve pronouns.

5. **Relative References**: "above", "previously", "earlier", "that", "this" → Determine if referring to last message or earlier messages.

**OUTPUT FORMAT** (JSON only, no explanation):
{{
    "message_indices": [list of message indices to use, e.g., [4, 5] for messages 4 and 5],
    "context_type": "META_OP" | "DATA_REQUEST" | "CLARIFICATION" | "TOPIC_SWITCH" | "NEW_TOPIC",
    "reasoning": "Brief explanation of why these messages were selected (1 sentence)",
    "window_size": <number of messages selected>
}}

**EXAMPLES**:

Query: "summarize above in 100 words"
Output: {{"message_indices": [{len(recent_history)-1}], "context_type": "META_OP", "reasoning": "User wants to summarize the previous assistant answer", "window_size": 1}}

Query: "what about you said earlier about Ahmed/ engine issues ?"
Output: {{"message_indices": [{len(recent_history)-2}, {len(recent_history)-1}], "context_type": "DATA_REQUEST", "reasoning": "Need last 2 messages to understand topic context for Ahmed", "window_size": 2}}

Query: "show me delivery complaints"
Output: {{"message_indices": [], "context_type": "TOPIC_SWITCH", "reasoning": "Completely new topic, no previous context needed", "window_size": 0}}

**YOUR JSON OUTPUT**:
"""

    messages = [{"role": "user", "content": selection_prompt}]

    try:
        response = llm.generate(messages, max_tokens=150, temperature=0.1)
        result_text = response.content.strip()

        # Parse JSON response
        # Handle potential markdown code blocks
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)

        # Extract selected messages based on indices
        selected_indices = result.get("message_indices", [])
        selected_messages = []

        for idx in selected_indices:
            if 0 <= idx < len(recent_history):
                selected_messages.append(recent_history[idx])

        # print(f"[ContextSelector] 🎯 Selected {len(selected_messages)} message(s) for context")  # Verbose
        # print(f"[ContextSelector]   Type: {result.get('context_type', 'UNKNOWN')}")  # Verbose
        # print(f"[ContextSelector]   Reasoning: {result.get('reasoning', 'N/A')}")  # Verbose

        return {
            "selected_messages": selected_messages,
            "context_type": result.get("context_type", "DATA_REQUEST"),
            "reasoning": result.get("reasoning", "LLM-based selection"),
            "window_size": len(selected_messages)
        }

    except Exception as e:
        print(f"[ContextSelector] ⚠️ LLM selection failed: {e}, falling back to last 2 messages")
        # Fallback: Use last 2 messages (safer than 4)
        fallback_messages = recent_history[-2:] if len(recent_history) >= 2 else recent_history
        return {
            "selected_messages": fallback_messages,
            "context_type": "DATA_REQUEST",
            "reasoning": f"Fallback due to error: {e}",
            "window_size": len(fallback_messages)
        }
