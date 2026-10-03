from typing import Optional, List, Dict, Any
import json, os
from datetime import datetime, timezone


# Simple version for database messages
def build_whatsapp_llm_prompt_simple(
    query: str,
    whatsapp_data: List[Dict],
    history: Optional[List[Dict[str, str]]] = None
) -> tuple[List[Dict[str, str]], List[Dict]]:
    """
    Build LLM prompt for WhatsApp mode with database messages
    
    Args:
        query: User's question
        whatsapp_data: List of WhatsApp messages from database
        history: Chat history
        
    Returns:
        List of messages for LLM
    """
    # Analyze query intent
    ql = (query or "").lower()
    
    # Detect query type
    is_top_n = any(word in ql for word in ["top", "most", "common", "frequent", "popular", "main"])
    is_complaint_focus = any(word in ql for word in ["complaint", "complain", "issue", "problem", "concern"])
    is_query_focus = any(word in ql for word in ["query", "question", "ask", "inquiry"])
    is_summary = any(word in ql for word in ["summary", "summarize", "overview", "insights", "patterns", "trend"])
    is_count = any(word in ql for word in ["how many", "count", "number of", "total"])
    is_comparison = any(word in ql for word in [" vs ", " versus ", "compare", "comparison", "both"])
    
    # Extract number if asking for top N
    import re
    top_n_match = re.search(r'\b(top|first|last)\s+(\d+)\b', ql)
    requested_count = int(top_n_match.group(2)) if top_n_match else None
    
    # Build context from WhatsApp messages with citation keys
    context_parts = []
    complaints = [msg for msg in whatsapp_data if msg.get('message_type') == 'complaint']
    queries = [msg for msg in whatsapp_data if msg.get('message_type') == 'query']

    # FILTER messages based on user's explicit intent
    # Check if user is asking EXCLUSIVELY for queries or complaints
    is_listing_queries = any(word in ql for word in ["list query", "list down query", "show queries", "show me queries", "all queries", "only queries"])
    is_listing_complaints = any(word in ql for word in ["list complaint", "list down complaint", "show complaints", "show me complaints", "all complaints", "only complaints"])

    if is_listing_queries and not is_complaint_focus:
        # User explicitly wants ONLY queries - filter to show only queries
        messages_to_show = queries[:50]
        if len(queries) == 0:
            # If no queries exist, don't show anything (will be handled by LLM prompt)
            messages_to_show = []
    elif is_listing_complaints and not is_query_focus:
        # User explicitly wants ONLY complaints - filter to show only complaints
        messages_to_show = complaints[:50]
        if len(complaints) == 0:
            messages_to_show = []
    elif is_query_focus and not is_complaint_focus and not is_comparison:
        # User is focusing on queries (but not explicitly listing) - show queries first
        messages_to_show = (queries[:40] + complaints[:10])[:50]
    elif is_complaint_focus and not is_query_focus and not is_comparison:
        # User is focusing on complaints - show complaints first
        messages_to_show = (complaints[:40] + queries[:10])[:50]
    else:
        # Default: show a balanced mix - interleave complaints and queries for better reference mapping
        messages_to_show = []
        max_complaints = min(30, len(complaints))
        max_queries = min(20, len(queries))
        
        # Interleave complaints and queries (2 complaints, 1 query pattern)
        c_idx = q_idx = 0
        while len(messages_to_show) < 50 and (c_idx < max_complaints or q_idx < max_queries):
            # Add 2 complaints
            for _ in range(2):
                if c_idx < max_complaints and len(messages_to_show) < 50:
                    messages_to_show.append(complaints[c_idx])
                    c_idx += 1
            # Add 1 query
            if q_idx < max_queries and len(messages_to_show) < 50:
                messages_to_show.append(queries[q_idx])
                q_idx += 1
        
        # If we still have space and remaining messages, add them
        while len(messages_to_show) < 50:
            if c_idx < len(complaints):
                messages_to_show.append(complaints[c_idx])
                c_idx += 1
            elif q_idx < len(queries):
                messages_to_show.append(queries[q_idx])
                q_idx += 1
            else:
                break
    
    for idx, msg in enumerate(messages_to_show, 1):
        msg_type = msg.get('message_type', 'unknown')
        emoji = "❗" if msg_type == "complaint" else "❓"
        customer_name = msg.get('customer_name', 'Unknown')
        contact = f"+{msg.get('country_code', '')}{msg.get('contact_number', '')}"
        
        context_parts.append(
            f"[WA-{idx}] {emoji} **{customer_name}** ({msg_type})\n"
            f"   Message: {msg.get('message', 'N/A')}\n"
            f"   Contact: {contact}\n"
            f"   Time: {msg.get('timestamp', 'N/A')}\n"
        )
    
    context = "\n".join(context_parts)
    
    # Build intelligent instructions based on query type
    query_specific_instructions = ""
    if is_top_n and requested_count:
        query_specific_instructions = f"\n- The user is asking for TOP {requested_count} items. Identify and rank the most relevant {requested_count} messages from ALL available data."
        query_specific_instructions += f"\n- ⚠️ MANDATORY: Create MULTIPLE visualizations using the exact format below:"
        query_specific_instructions += f"\n  1. A BAR chart showing the top {requested_count} items with their counts"
        query_specific_instructions += f"\n  2. A PIE chart showing the distribution/percentage of top items"
        query_specific_instructions += f"\n  3. A TABLE with detailed breakdown (Issue, Count, Percentage, Severity)"
    elif is_top_n:
        query_specific_instructions = "\n- The user is asking for TOP items. Identify and rank the most relevant messages (typically 5-10) from ALL available data."
        query_specific_instructions += "\n- ⚠️ MANDATORY: Create MULTIPLE visualizations using the exact format below:"
        query_specific_instructions += "\n  1. A BAR chart showing the top items with their counts"
        query_specific_instructions += "\n  2. A PIE chart showing the distribution/percentage"
        query_specific_instructions += "\n  3. A TABLE with detailed breakdown"
    
    if is_count:
        query_specific_instructions += "\n- The user wants COUNT/NUMBER. Provide specific numbers and statistics from ALL available data."
        query_specific_instructions += "\n- ⚠️ MANDATORY: You MUST include MULTIPLE visualizations using the exact format below:"
        query_specific_instructions += "\n  1. A chart (bar/pie) showing the counts"
        query_specific_instructions += "\n  2. A TABLE with detailed numbers and percentages"
    
    if is_summary:
        query_specific_instructions += "\n- The user wants a SUMMARY/OVERVIEW. Analyze ALL messages (both complaints and queries) and identify patterns."
        query_specific_instructions += "\n- ⚠️ MANDATORY: Include MULTIPLE visualizations using the exact format below:"
        query_specific_instructions += "\n  1. A PIE chart showing the distribution of issues/categories"
        query_specific_instructions += "\n  2. A BAR chart showing top issues by count"
        query_specific_instructions += "\n  3. A TABLE with comprehensive breakdown"
    
    if is_listing_queries:
        query_specific_instructions += f"\n- ⚠️ CRITICAL: User wants to LIST/SHOW ONLY QUERIES (❓). You have been given {len(queries)} queries in the context."
        query_specific_instructions += f"\n- If the context shows queries (❓), list them ALL. DO NOT say 'no queries found' if queries exist in the context."
        query_specific_instructions += f"\n- If the context is empty, then say 'No queries found in the database'."
    elif is_listing_complaints:
        query_specific_instructions += f"\n- ⚠️ CRITICAL: User wants to LIST/SHOW ONLY COMPLAINTS (❗). You have been given {len(complaints)} complaints in the context."
        query_specific_instructions += f"\n- If the context shows complaints (❗), list them ALL. DO NOT say 'no complaints found' if complaints exist in the context."
        query_specific_instructions += f"\n- If the context is empty, then say 'No complaints found in the database'."
    elif is_complaint_focus and not is_query_focus:
        query_specific_instructions += "\n- User is specifically asking about COMPLAINTS (❗). Focus on complaints but you can mention queries if relevant."
    elif is_query_focus and not is_complaint_focus:
        query_specific_instructions += "\n- User is specifically asking about QUERIES (❓). Focus on queries but you can mention complaints if relevant."
    else:
        query_specific_instructions += "\n- Answer based on ALL available data (both complaints ❗ and queries ❓). Don't limit yourself to just one type unless explicitly asked."
    
    # Check if data is empty or very limited
    data_guidance = ""
    if len(whatsapp_data) == 0:
        data_guidance = """

**⚠️ NO DATA AVAILABLE:**
If you have no data to analyze, inform the user:
"I don't have any WhatsApp messages to analyze yet. To get insights, please:
1. Go to the Search page
2. Use the WATI API integration to fetch WhatsApp data
3. Come back and ask your question again!"
"""
    elif len(whatsapp_data) < 5:
        data_guidance = f"""

**⚠️ LIMITED DATA ({len(whatsapp_data)} messages):**
Mention that insights are limited due to small dataset. Suggest importing more data for better analysis.
"""

    # Add specific guidance for queries/complaints
    if is_listing_queries and len(queries) == 0:
        data_guidance += f"""

**⚠️ NO QUERIES FOUND:**
The database has {len(complaints)} complaints but 0 queries. Inform the user:
"Currently, there are no queries (❓) in the database. All {len(complaints)} messages are classified as complaints (❗).
If you believe there should be queries, please check:
1. The classification logic in the data import process
2. The message_type field in your WhatsApp data
3. Re-import the data if needed"
"""
    elif is_listing_complaints and len(complaints) == 0:
        data_guidance += f"""

**⚠️ NO COMPLAINTS FOUND:**
The database has {len(queries)} queries but 0 complaints. Inform the user:
"Currently, there are no complaints (❗) in the database. All {len(queries)} messages are classified as queries (❓).
If you believe there should be complaints, please check the classification logic."
"""

    # System prompt with intelligent detection
    system_prompt = f"""You are an AI assistant analyzing Haval H6 customer messages from WhatsApp.

**Available Data:**
- Total Messages: {len(whatsapp_data)}
- Complaints (❗): {len(complaints)}
- Queries (❓): {len(queries)}{data_guidance}

**IMPORTANT:** You have access to BOTH complaints and queries. Use ALL relevant data to answer questions unless the user specifically asks for only one type.

**Messages Context:**
{context}

**Core Instructions:**
- Answer questions using ALL available data (complaints AND queries) unless specifically asked to filter
- When referencing a message, cite it inline like: [WA-1] or [WA-5]
- If the data contains relevant information, USE IT - don't say "no data found" if data exists
- If NO relevant data exists for the specific question, suggest the user add more data or check other platforms
- Provide clear, factual analysis based on the actual messages
- Be empathetic and professional

**ANSWER FORMATTING (IMPORTANT):**
- Structure your answer with clear sections using markdown headers (##, ###)
- Use bullet points (•) or numbered lists for better readability
- Highlight important information with **bold** text
- Use emojis strategically to make the answer more engaging
- Group related information together
- Make the answer visually appealing and easy to scan

**Example Answer Structure:**
## 📊 Analysis Summary
Brief overview paragraph here...

## 🔍 Key Findings
• Finding 1 with citation [WA-1]
• Finding 2 with citation [WA-2]
• Finding 3 with citation [WA-3]

[Charts and Tables here]

## 📋 References
[References section]

{query_specific_instructions}

**CHART & TABLE VISUALIZATION (MANDATORY for statistics/counts/analysis):**
When user asks about statistics, counts, top N, or analysis, you MUST include visualizations.

**Use MULTIPLE chart types based on data:**
1. **Bar Chart** - For rankings, comparisons, top N items
2. **Pie Chart** - For distributions, percentages, categories
3. **Line Chart** - For trends over time, sequential data
4. **Tables** - For detailed data, comparisons, structured information

**Chart Format (EXACT FORMAT REQUIRED):**
\`\`\`chart
type: bar
title: Top Customer Issues
data: {{"Engine Problems": 15, "Delivery Delays": 12, "AC Issues": 8, "Fuel Economy": 6, "Service Quality": 4}}
\`\`\`

**WRONG - DO NOT USE:**
❌ CHART_PLACEHOLDER_0
❌ [Chart will be displayed here]
❌ <chart data here>

**CORRECT - ALWAYS USE:**
✅ Complete ```chart blocks as shown above

**CRITICAL CHART RULES:**
- Use EXACT format above with ```chart opening and ``` closing
- type: must be "bar", "pie", or "line" (lowercase)
- title: descriptive chart title
- data: valid JSON with string keys and number values
- Use double quotes in JSON, not single quotes
- Place charts BEFORE the References section
- NEVER use placeholders like CHART_PLACEHOLDER_0 or similar
- ALWAYS use the complete ```chart format shown above

**Table Format (for detailed data):**
| Issue | Count | Percentage | Severity |
|-------|-------|------------|----------|
| Issue 1 | 10 | 20% | High |
| Issue 2 | 8 | 16% | Medium |

**IMPORTANT:**
- Use BAR charts for rankings (top 10, most common, etc.)
- Use PIE charts for distributions (complaints vs queries, severity breakdown, etc.)
- Use LINE charts for trends (issues over time, monthly patterns, etc.)
- Use TABLES for detailed breakdowns, comparisons, or structured data
- Include MULTIPLE visualizations when appropriate (e.g., bar chart + pie chart + table)
- Place visualizations BEFORE the References section
- Data must be valid JSON with string keys and number values
- Use double quotes in JSON

**MANDATORY: References Section**
At the end of your answer, ALWAYS add a styled References section like this:

---
### 📋 References

**[WA-1]** 👤 [ACTUAL CUSTOMER NAME FROM DATA] | 📞 +CountryCode PhoneNumber | 🏷️ Message Type | 🕐 Timestamp  
💬 *"The actual customer message text here"*

**[WA-2]** 👤 [ACTUAL CUSTOMER NAME FROM DATA] | 📞 +CountryCode PhoneNumber | 🏷️ Message Type | 🕐 Timestamp  
💬 *"The actual customer message text here"*

---

CRITICAL: Use the EXACT customer names from the WhatsApp data above (e.g., if the data shows "Sohaib Zahid", use "Sohaib Zahid", NOT "Customer Name").
Include ONLY the messages you actually referenced in your answer (do not list all messages).
Use emojis and formatting to make references clear and professional.
Always include the timestamp (🕐) for each reference.

**MANDATORY: Recommendations Section**
After your answer and before References, add a Recommendations section when appropriate:

---
### 💡 Recommendations

- **Action Item 1**: Specific actionable recommendation based on the data
- **Action Item 2**: Another specific recommendation
- **Action Item 3**: Additional suggestion or insight

---

CRITICAL: Always include this Recommendations section with 3-6 actionable recommendations based on the patterns you identified in the messages.

Provide 4-6 actionable recommendations based on the patterns you identified in the messages.

Answer the user's question based on ALL available WhatsApp messages."""

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": query})
    
    return messages, messages_to_show


# Original complex version (kept for compatibility)
from typing import Optional, List, Dict, Any
import json, os
from datetime import datetime, timezone



# -----------------------------
# Helpers
# -----------------------------
_SKIP_MESSAGE_TYPES = {"image", "document", "audio", "video", "sticker", "location", "contact", "contacts"}
_SKIP_EVENT_TYPES = {"ticket"}  # ticket events are bot/ops workflow, not real chat content

_BOT_NAME_HINTS = {"bot", "automation"}  # operatorName often "Bot "


def _safe_str(x) -> str:
    return "" if x is None else str(x)


def _parse_iso_dt(s: str) -> Optional[datetime]:
    s = _safe_str(s).strip()
    if not s:
        return None
    # handles "2025-11-27T11:40:20.624Z"
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _parse_unix_ts(s: str) -> Optional[datetime]:
    s = _safe_str(s).strip()
    if not s:
        return None
    try:
        return datetime.fromtimestamp(int(float(s)), tz=timezone.utc)
    except Exception:
        return None


def _is_bot_message(item: Dict[str, Any]) -> bool:
    """
    owner:true often means SAZ side, could be bot or human agent.
    We treat as bot if operatorName looks like bot OR avatarUrl is bot.png OR botType present.
    """
    op = _safe_str(item.get("operatorName")).strip().lower()
    avatar = _safe_str(item.get("avatarUrl")).strip().lower()
    bot_type = item.get("botType", None)

    if any(h in op for h in _BOT_NAME_HINTS):
        return True
    if "bot.png" in avatar:
        return True
    if bot_type is not None:
        # In your snippet bot messages have botType=0; humans usually null
        return True
    return False


def _speaker_label(item: Dict[str, Any]) -> str:
    # owner=False: customer/user, owner=True: SAZ side (bot or human agent)
    if item.get("owner") is False:
        return "[User]"
    # owner True => agent/bot side
    if _is_bot_message(item):
        return "[Bot]"
    # human agent name if present
    op = _safe_str(item.get("operatorName")).strip()
    if op:
        return f"[Agent: {op}]"
    return "[Agent]"


def _should_keep_message(item: Dict[str, Any]) -> bool:
    if not isinstance(item, dict):
        return False

    # drop non-message events
    if _safe_str(item.get("eventType")).strip().lower() in _SKIP_EVENT_TYPES:
        return False

    # must look like a message
    if _safe_str(item.get("eventType")).strip().lower() != "message":
        return False

    # drop non-text message types
    mtype = _safe_str(item.get("type")).strip().lower()
    if not mtype or mtype in _SKIP_MESSAGE_TYPES:
        return False

    # keep only if it has real text content
    text = _safe_str(item.get("text")).strip()
    if not text:
        return False

    return True


def _message_time(item: Dict[str, Any]) -> Optional[datetime]:
    # Prefer `created` (ISO), fallback to `timestamp` (unix string)
    dt = _parse_iso_dt(item.get("created"))
    if dt:
        return dt
    return _parse_unix_ts(item.get("timestamp"))


# -----------------------------
# REQUIRED: Formatter
# -----------------------------
def _format_whatsapp_data(data) -> str:
    """
    Merge messages by conversationId into blocks.
    Only includes actual text messages (no tickets, no images/docs).
    Citation key: [WA-<conversationId>:<messageId>]
    """
    items = data if isinstance(data, list) else []
    # Filter to valid chat messages
    msgs = [it for it in items if _should_keep_message(it)]

    # Group by conversationId
    by_conv: Dict[str, List[Dict[str, Any]]] = {}
    for m in msgs:
        cid = _safe_str(m.get("conversationId")).strip() or "UNKNOWN_CONVERSATION"
        by_conv.setdefault(cid, []).append(m)

    # Sort conversations by earliest message time
    def conv_sort_key(cid: str):
        times = [_message_time(m) for m in by_conv.get(cid, [])]
        times = [t for t in times if t is not None]
        if not times:
            return datetime.max.replace(tzinfo=timezone.utc)
        return min(times)

    conv_ids = sorted(by_conv.keys(), key=conv_sort_key)

    lines: List[str] = []
    lines.append(f"Total WhatsApp conversations: {len(conv_ids)}")
    lines.append("Ground-truth rules: use ONLY this WhatsApp context. Cite messages inline as [WA-<conversationId>:<messageId>].")
    lines.append("")

    for cid in conv_ids:
        conv_msgs = by_conv[cid]

        # sort messages chronologically
        conv_msgs.sort(key=lambda m: (_message_time(m) or datetime.max.replace(tzinfo=timezone.utc)))

        # derive simple metadata
        start_dt = _message_time(conv_msgs[0])
        end_dt = _message_time(conv_msgs[-1])
        topic = ""  # topicName exists only on ticket events, so we won't rely on it

        # Attempt to derive a contact name from bot greeting if present
        contact_hint = ""
        for m in conv_msgs:
            txt = _safe_str(m.get("text"))
            if "welcome" in txt.lower() and "saz" in txt.lower():
                # very light heuristic; avoid overfitting
                contact_hint = "Customer chat (SAZ support)"
                break

        lines.append("=" * 72)
        lines.append(f"[CONVERSATION] id={cid}")
        if contact_hint:
            lines.append(f"Context: {contact_hint}")
        if start_dt or end_dt:
            s = start_dt.isoformat() if start_dt else "Unknown"
            e = end_dt.isoformat() if end_dt else "Unknown"
            lines.append(f"Time range (UTC): {s} → {e}")
        if topic:
            lines.append(f"Topic: {topic}")
        lines.append("Messages:")

        for m in conv_msgs:
            mid = _safe_str(m.get("id")).strip() or "UNKNOWN_MSG"
            speaker = _speaker_label(m)
            txt = _safe_str(m.get("text")).strip()

            dt = _message_time(m)
            dt_str = dt.isoformat() if dt else _safe_str(m.get("created")).strip() or _safe_str(m.get("timestamp")).strip() or "Unknown time"

            # Keep it compact but still citable
            lines.append(f"- {dt_str} {speaker}: {txt}  [WA-{cid}:{mid}]")

        lines.append("")  # spacer

    return "\n".join(lines).strip()


# -----------------------------
# REQUIRED: Prompt builder (same rules as Facebook)
# -----------------------------
def build_whatsapp_llm_prompt(query: str, whatsapp_data, history: Optional[list] = None):
    messages = []

    with open(whatsapp_data, "r", encoding="utf-8") as f:
        wa_content = json.load(f)

    if not wa_content:
        return [{"role": "user", "content": query}]

    formatted_wa = _format_whatsapp_data(wa_content)

    ql = (query or "").lower()
    broad_markers = ("overview", "summary", "summarize", "insights", "patterns", "common", "overall", "trend", "what are people saying")
    is_broad = any(m in ql for m in broad_markers) or len(ql.split()) >= 18

    base_header = f"""
You are the **Haval WhatsApp Insights Copilot** for the Haval Pakistan marketing team.

GOAL
- Answer questions using ONLY the WhatsApp chat context provided below as the ground truth.
- Do NOT use outside knowledge, assumptions, or any other sources.
- If the context does not contain enough evidence, clearly say so.

FILTERING NOTE (already applied)
- Ticket/bot-workflow events are excluded (eventType="ticket").
- Non-text media messages are excluded (type in: image/document/etc.).
- Only actual text messages are included.

SMALL-TALK OVERRIDE (IMPORTANT)
- If the user input is general conversation (e.g., greetings, "hello", "hi", "how are you", "thanks", "ok", etc.),
  then DO NOT:
  • use the WhatsApp context,
  • generate citations,
  • generate references,
  • mention missing context.

- For such small-talk queries, simply reply naturally in one line (I am good thanks, how can I help you etc...).

OUT-OF-DOMAIN GUARD (CRITICAL)
- You are ONLY for analyzing Haval H6 customer messages from WhatsApp.
- DOMAIN: Haval vehicles (H6, Jolion, variants), customer issues, complaints, queries, service, delivery, features, comparisons with other vehicles
- OUT-OF-DOMAIN: Essays, general AI/tech topics, movies, food, sports, coding, jokes, general knowledge, homework help, creative writing

- If the user asks for something OUT-OF-DOMAIN:
  • DO NOT generate the requested content
  • DO NOT use the WhatsApp context
  • DO NOT generate citations or references
  • Reply: "I'm here to help with Haval H6 customer insights from WhatsApp messages. I can analyze complaints, queries, issues, and customer feedback about Haval vehicles. Please ask about Haval-related topics!"

Examples:
User: "write me an essay about AI"
Assistant: "I'm here to help with Haval H6 customer insights from WhatsApp messages. I can analyze complaints, queries, issues, and customer feedback about Haval vehicles. Please ask about Haval-related topics!"

User: "tell me a joke"
Assistant: "I'm here to help with Haval H6 customer insights from WhatsApp messages. Please ask about customer complaints, queries, or vehicle issues!"

CITATION + REFERENCES (MANDATORY)
- When you use a specific message, cite it inline like: [WA-<conversationId>:<messageId>]
- At the end of your answer, ALWAYS add, but not for small-talk queries, a styled References section like this:
  References:
  - [WA-...:...] <short label> — conversationId=<...> messageId=<...>
  Include ONLY the citations you actually relied on (do not dump everything).

CONTEXT (WhatsApp conversations merged into blocks)
\"\"\"
{formatted_wa}
\"\"\"
""".strip()

    if is_broad:
        instructions = """
ANSWERING STYLE (BROAD INSIGHT QUESTION)
1) Treat this as an insight report across conversations.
2) Structure:
   - 2–3 sentence overview
   - 2–4 short headings (only if relevant) like:
     "Recurring requests", "Service experience themes", "Delivery/booking concerns"
3) Stay strict: only claim what the WhatsApp context supports.
4) End with the mandatory References section, but for small-talk queries, output no references section.
""".strip()
    else:
        instructions = """
ANSWERING STYLE (TARGETED QUESTION)
1) Answer directly in 1–3 short paragraphs or tight bullets.
2) Use only the most relevant messages; cite them inline.
3) If evidence is limited, clearly say so.
4) End with the mandatory References section, but for small-talk queries, output no references section.
""".strip()

    system_prompt = base_header + "\n\n" + instructions

    messages.append({"role": "system", "content": system_prompt})

    for h in history or []:
        messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": query})

    return messages


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    from ..llm_client import GrokClient

    grok_api_key = os.getenv("XAI_API_KEY")
    if grok_api_key:
        print("[HavalPipeline] Using Grok LLM for RAG engine.")
        llm_client = GrokClient(api_key=grok_api_key)
    else:
        raise ValueError("XAI_API_KEY not set in environment variables.")

    test_prompt = "Provide a summary of the WhatsApp chat data provided."

    whatsapp_data = r"E:\VisionRD\haval-marketing\haval_marketing_tool\data\all_messages.json"

    message = build_whatsapp_llm_prompt(test_prompt, whatsapp_data)

    print("=== LLM Prompt ===")
    for msg in message:
        print(f"{msg['role'].upper()}: {msg['content']}\n")

    print("=== LLM Generating Answer ===")

    answer = llm_client.generate(message)
    print("=== LLM Answer ===")
    print(answer.content)
    print("==================")
