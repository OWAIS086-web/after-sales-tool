"""
Dealership Domain Classifier

Checks if a user query is about dealership data before processing.
Prevents wasting tokens on irrelevant queries.
"""

from typing import Dict
from ai.llm_client import BaseLLMClient


def classify_dealership_domain(question: str, llm: BaseLLMClient) -> str:
    """
    Classify if query is about dealership data.

    Args:
        question: User's natural language question
        llm: LLM client for classification

    Returns:
        "IN_DOMAIN" if query is about dealership data
        "OUT_OF_DOMAIN" if query is not answerable from dealership database

    Examples:
        IN_DOMAIN:
        - "How many warranty claims in December?"
        - "Show PDI inspections for Lahore"
        - "Which VIN has most complaints?"
        - "Compare warranty claims across different models"

        OUT_OF_DOMAIN:
        - "Who is the best salesperson?"
        - "What is the capital of France?"
        - "How do I cook biryani?"
        - "Tell me about PakWheels forums"
    """

    prompt = f"""You are a domain classifier for a dealership database system.

**Available Data in Dealership Database:**
- Warranty Claims (VIN, claim_type, dealership, dates, repair costs, problem descriptions)
- PDI Inspections (Pre-Delivery Inspections, objections, delivery status)
- FFS/SFS Inspections (First/Second Free Service inspections)
- Campaign Services (recall campaigns, service campaigns)
- Repair Orders (RO numbers, service history)
- Vehicle Information (VIN, model, variant, color, dealership)

**Your Task:**
Classify if this question can be answered using the dealership database.

**Question:** "{question}"

**Rules:**

1. **IN_DOMAIN - Dealership Data Questions:**
   - Warranty claims, PDI inspections, campaigns, repair orders, VIN history
   - Dealerships, car models, service records
   - Any question about data in the database above

2. **IN_DOMAIN - Visualization & Formatting Requests:**
   - Charts, graphs, plots, visualizations: "show me a bar graph", "plot this", "chart the data"
   - Formatting requests: "show as bullet points", "make a table", "format as list"
   - Even if the system can't generate the visual, the request is still about dealership data

3. **IN_DOMAIN - Follow-up Questions (referencing previous context):**
   - "show me the above", "that data", "those issues", "the previous results"
   - "can you visualize that?", "make it a chart", "what about those?"
   - "summarize that", "explain those", "give me details on that"
   - Any question referencing "above", "that", "those", "it", "them" (implies dealership context)

4. **OUT_OF_DOMAIN - Non-Dealership Questions:**
   - Salespeople, employees, customers, revenue, profits, inventory
   - WhatsApp messages, PakWheels forums, general knowledge
   - Greetings, small talk, general conversation

**Examples of IN_DOMAIN (even if seems unusual):**
- "show me a bar graph of the above" → IN_DOMAIN (visualization of dealership data)
- "format that as bullet points" → IN_DOMAIN (formatting dealership data)
- "can you make that a table?" → IN_DOMAIN (table of dealership results)
- "what about those issues?" → IN_DOMAIN (follow-up on dealership issues)
- "plot the frequencies" → IN_DOMAIN (visualization request)

**Answer with ONLY one word: "IN_DOMAIN" or "OUT_OF_DOMAIN"**
"""

    try:
        response = llm.generate(
            [{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.0
        )

        classification = response.content.strip().upper()

        # Normalize response
        if "IN_DOMAIN" in classification or "IN-DOMAIN" in classification:
            return "IN_DOMAIN"
        elif "OUT_OF_DOMAIN" in classification or "OUT-OF-DOMAIN" in classification:
            return "OUT_OF_DOMAIN"
        else:
            # Default to IN_DOMAIN to avoid blocking valid queries
            print(f"[Domain Classifier] Unclear classification: '{classification}', defaulting to IN_DOMAIN")
            return "IN_DOMAIN"

    except Exception as e:
        print(f"[Domain Classifier] Error: {e}")
        # Default to IN_DOMAIN on error to avoid blocking valid queries
        return "IN_DOMAIN"


def get_out_of_domain_message(question: str) -> str:
    """
    Generate helpful message for out-of-domain queries.

    Args:
        question: User's question

    Returns:
        Helpful message explaining what dealership mode can answer
    """

    return f"""I'm sorry, but the question **"{question}"** is not about dealership database information.

**Dealership Data Mode** can answer questions about:

✅ **Warranty Claims** - "How many tyre complaints in December?"
✅ **PDI Inspections** - "Show PDI inspections for Lahore dealership"
✅ **Campaign Services** - "How many campaigns did Karachi complete?"
✅ **VIN History** - "Show complete history for VIN [VIN]"
✅ **Repair Orders** - "How many ROs against this VIN?"
✅ **Service Records** - "Which dealership has most FFS inspections?"
✅ **Comparisons** - "Compare warranty claims across different models"

**For other questions:**
- General questions → Use **Insights Mode**
- PakWheels forums → Use **PakWheels Mode**
- WhatsApp data → Use **WhatsApp Mode**

Please ask a question about dealership data, or switch modes using the dropdown menu."""
