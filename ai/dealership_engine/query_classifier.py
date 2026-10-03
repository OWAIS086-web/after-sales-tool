"""
Dealership Query Classification

Classifies dealership queries into types:
- AGGREGATION: Count, sum, average queries
- FILTERING: Specific VIN/dealership lookups
- COMPARISON: Compare dealerships/models
- HISTORY: Complete VIN timeline
- SEMANTIC: Text search in descriptions
"""

from typing import Dict, Any
from ai.llm_client import BaseLLMClient
import json


def classify_dealership_query(question: str, llm: BaseLLMClient) -> Dict[str, Any]:
    """
    Classify dealership query type and extract query intent.

    Args:
        question: User's natural language question
        llm: LLM client for classification

    Returns:
        Dict with:
        - query_type: AGGREGATION|FILTERING|COMPARISON|HISTORY|SEMANTIC
        - intent: High-level intent description
        - needs_aggregation: Whether SQL needs GROUP BY/COUNT/SUM
        - needs_join: Whether multiple tables needed
    """

    classification_prompt = """You are a dealership database query classifier.

Classify this query into ONE of these types:

**1. AGGREGATION** (needs COUNT/SUM/AVG/GROUP BY):
Examples:
- "How many tyre complaints in December?"
- "Which dealership has most warranty claims?"
- "Total PDI inspections by dealership?"
- "Average repair cost by car model?"
- "Show me campaign completion rates"
- "How many complaints for each model?"

**2. FILTERING** (specific record lookup):
Examples:
- "Show warranty claims for VIN ABC123"
- "Which VIN has most complaints?"
- "Show all PDI inspections for Lahore dealership"
- "Get repair orders from last month"
- "Show tyre complaints only"

**3. COMPARISON** (compare entities):
Examples:
- "Compare warranty claims between different models"
- "Lahore vs Karachi dealership performance"
- "Which car model has more complaints?"
- "Compare PDI objection rates across dealerships"

**4. HISTORY** (COMPLETE timeline for VIN - all service types):
**IMPORTANT:** Only use HISTORY if user asks for "complete", "full", "all", or "entire" history/timeline.
If they ask for specific service types (warranty claims, campaigns, PDI), use FILTERING instead.
Examples:
- "Show complete history of VIN XYZ123"
- "Show all service records for this VIN" (all types)
- "VIN history from PDI to latest service" (full timeline)
- "Give me the entire service timeline for this vehicle"

**NOT HISTORY** (these are FILTERING):
- "Has this vehicle had warranty claims?" → FILTERING (specific type)
- "Show campaigns for this VIN" → FILTERING (specific type)
- "Did this car have any warranty claims or campaigns?" → FILTERING (2 specific types)

**5. SEMANTIC** (text search with listing):
Examples:
- "Show complaints about brake noise"
- "Find warranty claims mentioning transmission issues"
- "List all engine problems"
- "Search for electrical complaints"

**6. SEMANTIC_SUMMARY** (natural language overview/summary):
**IMPORTANT:** Use when user wants overview, summary, insights, or "tell me about" (not counts/statistics).
Examples:
- "Tell me about common tyre complaints"
- "Summarize transmission issues"
- "What are the main brake problems?"
- "Give me an overview of warranty claims"
- "Describe typical PDI objections"
- "What kind of electrical issues do we see?"

**NOT SEMANTIC_SUMMARY** (these are AGGREGATION):
- "How many tyre complaints?" → AGGREGATION (wants count)
- "Which has most issues?" → AGGREGATION (wants ranking)

---

**USER QUERY**: "{question}"

Respond in JSON format:
{{
  "query_type": "AGGREGATION|FILTERING|COMPARISON|HISTORY|SEMANTIC|SEMANTIC_SUMMARY",
  "intent": "Brief description of what user wants",
  "needs_aggregation": true/false,
  "needs_join": true/false,
  "needs_summarization": true/false (true for SEMANTIC_SUMMARY only),
  "suggested_table": "warranty_claims|pdi_inspections|campaigns|ffs_inspections|sfs_inspections|repair_orders|vehicles",
  "confidence": 0.0-1.0
}}

Example responses:

Q: "How many tyre complaints in December?"
{{
  "query_type": "AGGREGATION",
  "intent": "Count tyre warranty claims in December",
  "needs_aggregation": true,
  "needs_join": false,
  "needs_summarization": false,
  "suggested_table": "warranty_claims",
  "confidence": 0.95
}}

Q: "Show history of VIN ABC123"
{{
  "query_type": "HISTORY",
  "intent": "Complete service history for specific VIN",
  "needs_aggregation": false,
  "needs_join": true,
  "needs_summarization": false,
  "suggested_table": "vehicles",
  "confidence": 0.98
}}

Q: "Tell me about common tyre complaints"
{{
  "query_type": "SEMANTIC_SUMMARY",
  "intent": "Summarize and provide insights on tyre warranty issues",
  "needs_aggregation": false,
  "needs_join": false,
  "needs_summarization": true,
  "suggested_table": "warranty_claims",
  "confidence": 0.96
}}

Now classify the user's query:"""

    prompt = classification_prompt.format(question=question)

    try:
        response = llm.generate(
            [{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.0
        )

        # Parse JSON response
        result = json.loads(response.content.strip())

        print(f"[Dealership Query Classifier] Query: '{question[:60]}...'")
        print(f"[Dealership Query Classifier] Type: {result.get('query_type')}, Confidence: {result.get('confidence')}")

        return result

    except json.JSONDecodeError as e:
        print(f"[Dealership Query Classifier] JSON parse error: {e}")
        print(f"[Dealership Query Classifier] Raw response: {response.content}")

        # Fallback classification
        return {
            "query_type": "FILTERING",
            "intent": "General query",
            "needs_aggregation": False,
            "needs_join": False,
            "suggested_table": "warranty_claims",
            "confidence": 0.5
        }

    except Exception as e:
        print(f"[Dealership Query Classifier] Error: {e}")
        return {
            "query_type": "FILTERING",
            "intent": "Error in classification",
            "needs_aggregation": False,
            "needs_join": False,
            "suggested_table": "warranty_claims",
            "confidence": 0.3
        }


def is_followup_query(question: str, chat_history: list = None) -> bool:
    """
    Detect if this is a follow-up query that needs context from history.

    Args:
        question: Current question
        chat_history: Previous conversation

    Returns:
        True if this is a follow-up question
    """
    if not chat_history or len(chat_history) == 0:
        return False

    q_lower = question.lower().strip()

    # Follow-up indicators
    followup_patterns = [
        'what about',
        'and ',
        'also ',
        'same for',
        'how about',
        'what if',
        'compare with',
        'versus',
        'vs ',
        # Context references
        'that',
        'those',
        'these',
        'same',
        'it',
        'them',
    ]

    # Check if question is very short (likely referencing context)
    if len(q_lower.split()) <= 3:
        return True

    # Check for followup patterns
    for pattern in followup_patterns:
        if q_lower.startswith(pattern) or f" {pattern}" in q_lower:
            return True

    return False
