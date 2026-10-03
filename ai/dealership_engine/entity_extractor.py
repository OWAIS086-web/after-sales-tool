"""
Dealership Entity Extraction

LLM-based extraction of entities from queries:
- VIN numbers (with typo tolerance)
- Dealership names (with variations)
- Dates and date ranges
- Car models and variants
- Claim types
- Service types
"""

from typing import Dict, Any, Optional
from ai.llm_client import BaseLLMClient
import json
import re
from datetime import datetime, timedelta


def extract_entities(question: str, llm: BaseLLMClient, chat_history: list = None) -> Dict[str, Any]:
    """
    Extract all entities from question using LLM.
    Handles typos, abbreviations, variations.

    Args:
        question: User's question
        llm: LLM client for extraction
        chat_history: Previous conversation for context

    Returns:
        Dict with extracted entities
    """

    # Build context from history if followup
    history_context = ""
    if chat_history and len(chat_history) > 0:
        last_msg = chat_history[-1]
        if last_msg.get('role') == 'user':
            history_context = f"\n\n**PREVIOUS QUESTION**: {last_msg.get('content', '')[:200]}"

    extraction_prompt = f"""You are extracting entities from a dealership database query.

**ENTITY TYPES TO EXTRACT**:

1. **VIN Numbers**: 17-character alphanumeric (handle typos, missing chars, spaces)
   Examples: "ABC123XYZ45678901", "abc 123 xyz", "vin ending in 901"

2. **Dealership Names**:
   - Full names: "Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad", or specific dealership names
   - Abbreviations: "lhr" → "Lahore", "khi" → "Karachi", "isb" → "Islamabad"
   - Typos: "lahre" → "Lahore"

3. **Car Models**:
   - Extract any car model mentioned (e.g., "Sportage", "Picanto", "Model X")
   - Typos: Handle common misspellings
   - Variants: Handle model variants (e.g., "Model X EV", "Model Y Hybrid")

4. **Date Filters**:
   - Months: "December" → month=12, "Dec" → month=12
   - Ranges: "last month", "last 6 months", "this year", "2024"
   - Specific dates: "December 2024", "15th Dec", "between Jan and Mar"

5. **Claim Types** (for warranty_claims):
   - Types: "tyre", "engine", "transmission", "electrical", "brake", "suspension", "battery"
   - Typos: "tire" → "tyre", "breaks" → "brake"

6. **Service Types**:
   - "PDI", "FFS", "SFS", "campaign", "repair order", "RO", "warranty", "inspection"

7. **Status/Filters**:
   - Status: "pending", "approved", "rejected", "completed", "failed", "objection"
   - Conditions: "with objections", "no objections", "rejected deliveries"

8. **Metrics** (for aggregation queries):
   - "count", "total", "sum", "average", "most", "least", "top", "bottom"

---

**USER QUERY**: "{question}"{history_context}

Extract ALL entities in JSON format:
{{
  "vin_number": "ABC123..." or null,
  "dealership_name": "Lahore" or null,
  "car_model": "Sportage" or ["Sportage", "Picanto"] (if multiple),
  "date_filter": {{
    "type": "month|range|year|specific",
    "month": 12 or null,
    "year": 2024 or null,
    "start_date": "2024-01-01" or null,
    "end_date": "2024-12-31" or null
  }} or null,
  "claim_type": "tyre" or null,
  "service_type": "PDI|FFS|SFS|campaign|warranty|repair_order" or null,
  "status_filter": "pending|approved|rejected|completed" or null,
  "metric": "count|sum|average|max|min" or null,
  "aggregation_field": "dealership_name|car_model|claim_type" or null,
  "limit": 10 or null,
  "has_objections": true/false/null,
  "comparison_entities": ["Sportage", "Picanto"] or null (for comparison queries)
}}

**IMPORTANT RULES**:
- Handle typos: "lahre" → "Lahore", "kracki" → "Karachi"
- Expand abbreviations: "lhr" → "Lahore", "khi" → "Karachi"
- Preserve user intent even with mistakes
- Extract ALL mentioned entities (for comparison queries, list multiple models/dealerships)
- If uncertain, set to null (don't hallucinate)

**EXAMPLES**:

Q: "How many tyre complaints in December?"
{{
  "vin_number": null,
  "dealership_name": null,
  "car_model": null,
  "date_filter": {{"type": "month", "month": 12, "year": null}},
  "claim_type": "tyre",
  "service_type": "warranty",
  "status_filter": null,
  "metric": "count",
  "aggregation_field": null,
  "limit": null,
  "has_objections": null,
  "comparison_entities": null
}}

Q: "Which dealership has most PDIs - lhr or khi?"
{{
  "vin_number": null,
  "dealership_name": null,
  "car_model": null,
  "date_filter": null,
  "claim_type": null,
  "service_type": "PDI",
  "status_filter": null,
  "metric": "count",
  "aggregation_field": "dealership_name",
  "limit": null,
  "has_objections": null,
  "comparison_entities": ["Lahore", "Karachi"]
}}

Q: "Show history of VIN abc123xyz"
{{
  "vin_number": "ABC123XYZ",
  "dealership_name": null,
  "car_model": null,
  "date_filter": null,
  "claim_type": null,
  "service_type": null,
  "status_filter": null,
  "metric": null,
  "aggregation_field": null,
  "limit": null,
  "has_objections": null,
  "comparison_entities": null
}}

Q: "Compare complaints for Model A vs Model B in last 6 months"
{{
  "vin_number": null,
  "dealership_name": null,
  "car_model": null,
  "date_filter": {{"type": "range", "start_date": "2024-07-01", "end_date": "2024-12-31"}},
  "claim_type": null,
  "service_type": "warranty",
  "status_filter": null,
  "metric": "count",
  "aggregation_field": "car_model",
  "limit": null,
  "has_objections": null,
  "comparison_entities": ["Model A", "Model B"]
}}

Now extract entities:"""

    try:
        response = llm.generate(
            [{"role": "user", "content": extraction_prompt}],
            max_tokens=300,
            temperature=0.0
        )

        # Parse JSON response
        entities = json.loads(response.content.strip())

        # Normalize dates if needed
        if entities.get('date_filter'):
            entities['date_filter'] = _normalize_date_filter(entities['date_filter'])

        print(f"[Entity Extractor] Extracted entities: {json.dumps(entities, indent=2)}")

        return entities

    except json.JSONDecodeError as e:
        print(f"[Entity Extractor] JSON parse error: {e}")
        print(f"[Entity Extractor] Raw response: {response.content}")

        # Fallback: Extract basic entities with regex
        return _fallback_entity_extraction(question)

    except Exception as e:
        print(f"[Entity Extractor] Error: {e}")
        return _fallback_entity_extraction(question)


def _normalize_date_filter(date_filter: Dict) -> Dict:
    """Normalize date filter to standard format"""
    if not date_filter:
        return None

    # Handle relative dates
    filter_type = date_filter.get('type')

    if filter_type == 'range':
        # Calculate relative ranges
        if 'last 6 months' in str(date_filter):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)
            date_filter['start_date'] = start_date.strftime('%Y-%m-%d')
            date_filter['end_date'] = end_date.strftime('%Y-%m-%d')

        elif 'last month' in str(date_filter):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            date_filter['start_date'] = start_date.strftime('%Y-%m-%d')
            date_filter['end_date'] = end_date.strftime('%Y-%m-%d')

        elif 'this year' in str(date_filter):
            year = datetime.now().year
            date_filter['start_date'] = f"{year}-01-01"
            date_filter['end_date'] = f"{year}-12-31"

    return date_filter


def _fallback_entity_extraction(question: str) -> Dict:
    """Fallback regex-based extraction when LLM fails"""
    entities = {
        "vin_number": None,
        "dealership_name": None,
        "car_model": None,
        "date_filter": None,
        "claim_type": None,
        "service_type": None,
        "status_filter": None,
        "metric": None,
        "aggregation_field": None,
        "limit": None,
        "has_objections": None,
        "comparison_entities": None
    }

    q_lower = question.lower()

    # Extract VIN (17 chars)
    vin_match = re.search(r'\b[A-HJ-NPR-Z0-9]{17}\b', question.upper())
    if vin_match:
        entities['vin_number'] = vin_match.group()

    # Extract dealership
    dealerships = {
        'lahore': 'Lahore', 'lhr': 'Lahore',
        'karachi': 'Karachi', 'khi': 'Karachi',
        'islamabad': 'Islamabad', 'isb': 'Islamabad',
        'rawalpindi': 'Rawalpindi', 'rwp': 'Rawalpindi',
        'faisalabad': 'Faisalabad', 'fsd': 'Faisalabad'
    }
    for key, value in dealerships.items():
        if key in q_lower:
            entities['dealership_name'] = value
            break

    # Car model extraction is handled by the LLM (no hardcoded models)

    # Extract claim type
    claim_types = ['tyre', 'tire', 'engine', 'transmission', 'brake', 'electrical']
    for claim_type in claim_types:
        if claim_type in q_lower:
            entities['claim_type'] = 'tyre' if claim_type == 'tire' else claim_type
            break

    # Extract month
    months = {
        'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
        'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
        'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
        'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12
    }
    for month_name, month_num in months.items():
        if month_name in q_lower:
            entities['date_filter'] = {
                'type': 'month',
                'month': month_num,
                'year': None
            }
            break

    # Extract service type
    if 'pdi' in q_lower:
        entities['service_type'] = 'PDI'
    elif 'ffs' in q_lower:
        entities['service_type'] = 'FFS'
    elif 'sfs' in q_lower:
        entities['service_type'] = 'SFS'
    elif 'campaign' in q_lower:
        entities['service_type'] = 'campaign'
    elif 'warranty' in q_lower or 'claim' in q_lower:
        entities['service_type'] = 'warranty'

    print(f"[Entity Extractor] Fallback extraction: {entities}")
    return entities
