# haval_insights/enrichment.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set

from collections import Counter
from tqdm import tqdm

from ai.models import ConversationBlock, CleanPost
from ai.llm_client import BaseLLMClient


# -------------------------------------------------------------------------
# Seed values (used as starting point; can be expanded at runtime)
# -------------------------------------------------------------------------

SEED_VARIANTS = ["PHEV", "HEV", "Jolion", "Unknown"]
ALLOWED_SENTIMENTS = ["positive", "negative", "mixed", "neutral"]

# These are *seed* tags, not a hard-closed list.
# Tags are organized into categories for robust metadata filtering:
# 1. Issue Type tags: Specific technical/service issues
# 2. Severity tags: critical, minor, resolved
# 3. Status tags: pending, resolved, escalated
# 4. Category tags: pre_sales, post_sales, complaint, inquiry

SEED_TAGS = [
    # ===== ISSUE TYPE TAGS (Technical/Service) =====
    "fuel_economy",
    "charging_cost",
    "range_anxiety",
    "brake_vibration",
    "brake_squeaking",
    "brake_fade",
    "steering_issue",
    "steering_vibration",
    "steering_loose",
    "build_quality",
    "rattles",
    "infotainment",
    "ac_performance",
    "service_experience",
    "pricing",
    "availability",
    "general_praise",
    "feature_set",
    "noise_and_vibration",
    "concern",
    "problem_report",
    "engine_issue",
    "transmission_issue",
    "suspension_issue",
    "electrical_issue",
    "paint_quality",
    "interior_quality",

    # ===== WHATSAPP-SPECIFIC TAGS (Customer Support) =====
    "booking_inquiry",
    "delivery_delay",
    "delivery_status",
    "payment_issue",
    "payment_confirmation",
    "test_drive_request",
    "dealership_location",
    "dealership_experience",
    "warranty_question",
    "warranty_claim",
    "service_appointment",
    "service_delay",
    "complaint_escalation",
    "urgent_request",
    "price_negotiation",
    "trade_in_inquiry",
    "financing_question",
    "financing_approval",
    "color_availability",
    "variant_inquiry",
    "feature_inquiry",
    "comparison_request",
    "cancellation_request",
    "refund_request",

    # ===== SEVERITY TAGS =====
    "severity_critical",     # Safety issues, urgent problems
    "severity_major",        # Significant issues affecting usability
    "severity_minor",        # Small annoyances, cosmetic issues
    "severity_resolved",     # Issue has been fixed

    # ===== STATUS TAGS =====
    "status_pending",        # Issue/request awaiting response
    "status_resolved",       # Issue/request completed successfully
    "status_escalated",      # Escalated to manager/technical team
    "status_follow_up",      # Requires follow-up action
    "status_closed",         # Conversation closed

    # ===== CATEGORY TAGS =====
    "category_pre_sales",    # Inquiry before purchase (booking, pricing, features)
    "category_post_sales",   # After purchase (delivery, service, issues)
    "category_complaint",    # Customer complaint or dissatisfaction
    "category_inquiry",      # General information request
    "category_praise",       # Positive feedback
    "category_technical",    # Technical problem or question

    "unknown",
]

# -------------------------------------------------------------------------
# Few-Shot Examples for Robust Prompting
# -------------------------------------------------------------------------

EXAMPLES_WHATSAPP = """
### 🔹 EXAMPLE 1: Technical Issue (Mix-Language, High Urgency)
**Input:**
"Asalam o Alaikum, my H6 HEV is showing a 'Battery Management System' error on the screen. Kya yeh serious issue hai? Also, when can I come for the 5000km service? Very urgent please!"

**Output:**
```json
{
  "variant": "HEV",
  "sentiment": "negative",
  "tags": ["electrical_issue", "service_appointment", "severity_critical", "status_pending", "category_post_sales", "category_technical", "urgent_request"],
  "urgency": "critical",
  "summary": "Customer reports Battery Management System error on H6 HEV and requests urgent service appointment for 5000km maintenance. Issue flagged as critical due to safety concerns. Status: Pending service booking."
}
```

### 🔹 EXAMPLE 2: Pre-Sales Inquiry (Positive, Medium Urgency)
**Input:**
"Jolion ki current price kya hai? And if I book today, delivery kab tak milegi? I'm interested in the HEV variant."

**Output:**
```json
{
  "variant": "Jolion",
  "sentiment": "positive",
  "tags": ["booking_inquiry", "variant_inquiry", "delivery_status", "severity_minor", "status_pending", "category_pre_sales"],
  "urgency": "medium",
  "summary": "Potential customer inquiring about Jolion HEV pricing and delivery timeline. Customer expressed interest in booking. Status: Awaiting sales agent response with current pricing."
}
```

### 🔹 EXAMPLE 3: Complaint Escalation (Angry Customer, Critical Urgency)
**Input:**
"I have been waiting for my PHEV for 3 MONTHS! This is totally unacceptable. I want to speak to your manager immediately or I will cancel my booking and ask for a full refund!"

**Output:**
```json
{
  "variant": "PHEV",
  "sentiment": "negative",
  "tags": ["delivery_delay", "complaint_escalation", "cancellation_request", "refund_request", "severity_critical", "status_escalated", "category_post_sales", "category_complaint"],
  "urgency": "critical",
  "summary": "Customer extremely dissatisfied with 3-month delay in PHEV delivery. Threatening to cancel booking and demanding full refund. Requesting escalation to management. Status: Escalated to senior team."
}
```

### 🔹 EXAMPLE 4: Resolved Service Request (Positive, Low Urgency)
**Input:**
"Thank you so much for fixing the AC issue! The service was excellent and the technician was very professional. My H6 is running perfectly now."

**Output:**
```json
{
  "variant": "H6",
  "sentiment": "positive",
  "tags": ["ac_performance", "service_experience", "severity_resolved", "status_closed", "category_post_sales", "category_praise"],
  "urgency": "low",
  "summary": "Customer expressing gratitude for excellent AC repair service. Praised technician professionalism. Issue fully resolved. Status: Closed with positive feedback."
}
```
""".strip()

EXAMPLES_PAKWHEELS = """
### 🔹 EXAMPLE 1: Technical Complaint (Owner, Negative Sentiment)
**Input:**
"I'm a proud H6 PHEV owner but honestly the brake vibration issue is getting worse. At highway speeds (100+ km/h), the steering wheel shakes badly when braking. Took it to the service center twice but they keep saying 'it's normal'. This is NOT normal and I'm worried about safety. Anyone else facing this?"

**Output:**
```json
{
  "variant": "PHEV",
  "sentiment": "negative",
  "tags": ["brake_vibration", "steering_vibration", "service_experience", "severity_critical", "status_pending", "category_post_sales", "category_complaint", "category_technical"],
  "is_owner": true,
  "summary": "Owner reports severe brake vibration and steering shake at highway speeds (100+ km/h) on PHEV. Visited service center twice but issue unresolved. Service center claims it's normal behavior. Owner concerned about safety and seeking validation from other owners."
}
```

### 🔹 EXAMPLE 2: Positive Review (Owner, Mixed Sentiment)
**Input:**
"Just completed my first 5000km in my Jolion HEV. Overall very impressed! Fuel economy is fantastic (22 km/l in city, 28 on motorway). Build quality is solid. Only complaint is the infotainment system is a bit laggy sometimes. But for the price, this is an amazing package."

**Output:**
```json
{
  "variant": "Jolion",
  "sentiment": "mixed",
  "tags": ["fuel_economy", "build_quality", "infotainment", "general_praise", "severity_minor", "status_closed", "category_post_sales", "category_praise"],
  "is_owner": true,
  "summary": "Owner review after 5000km in Jolion HEV. Praised excellent fuel economy (22 city / 28 highway km/l) and solid build quality. Minor criticism of laggy infotainment system. Overall highly satisfied with value for money."
}
```

### 🔹 EXAMPLE 3: Pre-Purchase Question (Non-Owner, Neutral)
**Input:**
"Thinking of buying the H6 HEV vs PHEV. Can someone explain the difference? Which one is better for mostly city driving in Karachi? Also, what's the warranty coverage on the battery?"

**Output:**
```json
{
  "variant": "Unknown",
  "sentiment": "neutral",
  "tags": ["variant_inquiry", "comparison_request", "warranty_question", "feature_inquiry", "severity_minor", "status_pending", "category_pre_sales", "category_inquiry"],
  "is_owner": false,
  "summary": "Potential buyer seeking clarification on HEV vs PHEV variants for city driving in Karachi. Questions about battery warranty coverage. Status: Awaiting community response."
}
```

### 🔹 EXAMPLE 4: Resolved Issue (Owner, Positive)
**Input:**
"UPDATE: My H9 transmission issue is finally fixed! Turns out it was a software glitch. Service center updated the firmware and now the gear shifts are smooth as butter. Big thanks to the Sazgar team for sorting this out!"

**Output:**
```json
{
  "variant": "H9",
  "sentiment": "positive",
  "tags": ["transmission_issue", "service_experience", "severity_resolved", "status_resolved", "category_post_sales", "category_praise"],
  "is_owner": true,
  "summary": "Owner provides positive update on resolved H9 transmission issue. Problem was software-related and fixed via firmware update. Gear shifts now operating smoothly. Customer satisfied with service center support."
}
```
""".strip()


@dataclass
class EnrichmentState:
    """
    Shared enrichment state that can be held globally in haval_pipeline.

    - `variants` and `tags` are dynamic registries:
      * seeded from SEED_VARIANTS / SEED_TAGS
      * extended when the LLM introduces new ones.
    """
    variants: Set[str] = field(default_factory=lambda: set(SEED_VARIANTS))
    tags: Set[str] = field(default_factory=lambda: set(SEED_TAGS))

    def set_prev_state(self, other: EnrichmentState) -> None:
        """
        Copy over variants/tags from another state.
        """
        self.variants = set(other.variants)
        self.tags = set(other.tags)


@dataclass
class BlockClassificationResult:
    """
    Result of classifying one ConversationBlock.
    """
    block: ConversationBlock
    status: str                     # "success", "empty_response", "invalid_json", "error"
    raw_response: str = ""
    error_message: Optional[str] = None
    new_variants: List[str] = field(default_factory=list)
    new_tags: List[str] = field(default_factory=list)


@dataclass
class EnrichmentMetrics:
    """
    Aggregated view over all classification results.
    """
    total_blocks: int
    status_counts: Dict[str, int] = field(default_factory=dict)
    variant_counts: Dict[str, int] = field(default_factory=dict)
    sentiment_counts: Dict[str, int] = field(default_factory=dict)
    tag_counts: Dict[str, int] = field(default_factory=dict)


# -------------------------------------------------------------------------
# Prompt construction
# -------------------------------------------------------------------------

def _classification_prompt(
    block: ConversationBlock,
    state: Optional[EnrichmentState] = None,
    retry: int = 0,
    company_id: str = "haval",
    data_source: str = "pakwheels",
) -> str:
    """
    Build a strict JSON-only classification + summarisation prompt.

    - Uses company-specific configuration (name, variants)
    - Uses different prompts for PakWheels (forum) vs WhatsApp (customer service)
    - Uses current variants/tags from the EnrichmentState as "known" values.
    - LLM is allowed to introduce new variants/tags when clearly justified.

    Args:
        block: Conversation block to classify
        state: Enrichment state with known variants/tags
        retry: Retry attempt number (for error messages)
        company_id: Company identifier (e.g., "haval", "kia", "toyota")
        data_source: Data source type ("pakwheels" or "whatsapp")
    """
    from config import get_company_config

    snippet = block.flattened_text
    # Keep context manageable for classification
    if len(snippet) > 4000:
        snippet = snippet[:4000]

    # Get company configuration
    try:
        company_config = get_company_config(company_id)
        company_name = company_config.full_name
        # Use company-specific variants if available, otherwise fall back to state/seed variants
        if hasattr(company_config, 'variants') and company_config.variants:
            variants_list = company_config.variants
            print(f"  🏷️  Using company variants: {variants_list}")
        else:
            variants_list = sorted(list(state.variants)) if state else SEED_VARIANTS
            print(f"  ⚠️  No company variants, using state/seed: {variants_list}")
    except Exception as e:
        print(f"  ❌ Error getting company config: {e}")
        company_name = company_id.title()
        variants_list = sorted(list(state.variants)) if state else SEED_VARIANTS

    tags_list = sorted(list(state.tags)) if state else SEED_TAGS

    # Different prompts for different data sources
    if data_source.lower() == "whatsapp":
        # WhatsApp: Customer service conversations
        system_prompt = f"""
You are a **Senior Lead for Customer Experience** at {company_name} Pakistan.
Your task is to analyze WhatsApp chat logs between support agents and customers.

**CRITICAL**: Customers often use **mix-language** (Urdu + English). You MUST handle both fluently.

You must return ONLY valid JSON with this exact structure:

{{
  "variant": "STRING",
  "sentiment": "positive|negative|mixed|neutral",
  "tags": ["tag1", "tag2", ...],
  "urgency": "critical|high|medium|low",
  "summary": "detailed summary of customer interaction"
}}

---
## 📋 FIELD GUIDELINES

### "variant":
- Use one of: {variants_list}
- If customer mentions a specific model/variant
- Use "Unknown" if unclear or not mentioned, dont force it

### "sentiment":
- Overall tone toward the **CUSTOMER SERVICE EXPERIENCE** (NOT the vehicle)
- How satisfied is the customer with the support they received?
- Must be one of: {ALLOWED_SENTIMENTS}

### "urgency":
- **critical**: Safety issue, very angry customer, urgent escalation, serious vehicle problem
- **high**: Time-sensitive request, strong complaint, escalated issue
- **medium**: Standard inquiry, normal complaint
- **low**: General question, positive feedback, casual inquiry

### "tags":
- Focus on **CUSTOMER SERVICE** categories:
  * **Booking/Pre-Sales**: booking_inquiry, variant_inquiry, price_negotiation, test_drive_request
  * **Delivery**: delivery_delay, delivery_status, color_availability
  * **Payment**: payment_issue, payment_confirmation, financing_question
  * **Service**: service_appointment, warranty_claim, warranty_question, technical_issue
  * **Complaints**: complaint_escalation, urgent_request, refund_request, cancellation_request

- **REQUIRED**: Include tags from MULTIPLE categories:
  1. **ISSUE TYPE**: booking_inquiry, delivery_delay, service_appointment, etc.
  2. **SEVERITY**: severity_critical, severity_major, severity_minor, severity_resolved
  3. **STATUS**: status_pending, status_resolved, status_escalated, status_closed
  4. **CATEGORY**: category_pre_sales, category_post_sales, category_complaint, category_inquiry

- Prefer reusing existing tags: {tags_list}
- **You MAY introduce new tags** if needed, but keep them **snake_case** and concise
- Return 3-7 tags per block

### "summary":
- 3-5 sentences with important keywords that are also common in queries
- Customer name (if available)
- Their request/complaint
- Current status (resolved/pending/escalated)
- Any commitments made by support team

---
## 🎯 FEW-SHOT EXAMPLES (LEARN FROM THESE)

{EXAMPLES_WHATSAPP}

---
**NOW ANALYZE THE CONVERSATION BELOW AND RETURN ONLY VALID JSON:**

""".strip()
    else:
        # PakWheels: Forum discussions
        system_prompt = f"""
You are a **Senior Automotive Industry Analyst** specializing in Pakistani car markets.
Your task is to analyze PakWheels forum discussions about {company_name} vehicles.

**CRITICAL**: Users often use **mix-language** (Urdu + English). You MUST handle both fluently.

You must return ONLY valid JSON with this exact structure:

{{
  "variant": "STRING",
  "sentiment": "positive|negative|mixed|neutral",
  "tags": ["tag1", "tag2", ...],
  "is_owner": true or false,
  "summary": "detailed natural language summary of this conversation block"
}}

---
## 📋 FIELD GUIDELINES

### "variant":
- Use one of the currently-known variants when possible: {variants_list}
- Variants refer to specific models (e.g., "Sportage", "PHEV", "Jolion", "Yaris")
- If the conversation clearly focuses on a specific variant not in the list,
  **you MAY introduce a new short variant name** (max ~30 characters)
- If unclear, use "Unknown"

### "sentiment":
- Overall tone toward the **{company_name} vehicle** being discussed
- Must be one of: {ALLOWED_SENTIMENTS}

### "tags":
- Tags capture key themes/topics AND metadata for filtering
- **REQUIRED**: Include tags from MULTIPLE categories when applicable:

  1. **ISSUE TYPE** (technical/service): brake_vibration, steering_issue, fuel_economy, etc.
  2. **SEVERITY**: severity_critical, severity_major, severity_minor, severity_resolved
  3. **STATUS**: status_pending, status_resolved, status_escalated, status_closed
  4. **CATEGORY**: category_pre_sales, category_post_sales, category_complaint, category_inquiry, category_praise, category_technical

- Example good tag set: ["brake_vibration", "severity_major", "status_pending", "category_post_sales", "category_complaint"]
- Example for resolved issue: ["delivery_delay", "severity_minor", "status_resolved", "category_pre_sales"]

- Prefer reusing existing tags: {tags_list}
- **You MAY introduce new tags** if needed, but keep them **snake_case** and concise
- Return 3-7 tags per block (include at least one from each applicable category)

### "is_owner":
- **true** if the ROOT author appears to own/drive this vehicle
- **false** otherwise or if unclear

### "summary":
- 3-7 sentences
- Capture the main topic, concerns, and direction of the conversation
- Include any clear signals about satisfaction/dissatisfaction, usage patterns,
  or frequently mentioned conditions (e.g., Karachi heat, city traffic, highways)

---
## 🎯 FEW-SHOT EXAMPLES (LEARN FROM THESE)

{EXAMPLES_PAKWHEELS}

---
**NOW ANALYZE THE CONVERSATION BELOW AND RETURN ONLY VALID JSON:**

""".strip()

    user_prompt = f"""Conversation block:
\"\"\"{snippet}\"\"\"
""".strip()

    if retry > 0:
        user_prompt = f"This is attempt #{retry + 1}. Please ensure your response is valid JSON as specified.\n\n{user_prompt}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Log prompt type (only once per batch, not per block)
    if retry == 0:
        print(f"  📝 Prompt Type: {data_source.upper()} | Company: {company_name} | Variants: {len(variants_list)}")

    return messages


# -------------------------------------------------------------------------
# Classification
# -------------------------------------------------------------------------

def _normalise_tag(raw: str) -> str:
    """
    Normalise a tag string into a consistent snake_case-ish token.
    """
    t = (raw or "").strip().lower().replace(" ", "_")
    # Very small cleanup; you can extend this later if needed.
    if len(t) > 64:
        t = t[:64]
    return t


def _fallback_summary(text: str, max_chars: int = 500) -> str:
    """
    Fallback summary if the LLM fails to provide one.
    """
    snippet = (text or "").strip()
    if len(snippet) <= max_chars:
        return snippet
    return snippet[:max_chars] + "..."


def classify_block(
    block: ConversationBlock,
    llm: BaseLLMClient,
    state: Optional[EnrichmentState] = None,
    company_id: str = "haval",
    data_source: str = "pakwheels",
) -> BlockClassificationResult:
    """
    Use the LLM to classify and summarise a conversation block.

    Side effects:
    - Updates:
        block.dominant_variant
        block.dominant_sentiment
        block.aggregated_tags
        block.summary      (new field, attached dynamically)
    - Propagates variant/sentiment/tags/is_owner to CleanPost objects.
    - Optionally extends `state.variants` and `state.tags` when new
      values are encountered.

    Args:
        block: Conversation block to classify
        llm: LLM client for classification
        state: Enrichment state with known variants/tags
        company_id: Company identifier (e.g., "haval", "kia", "toyota")
        data_source: Data source type ("pakwheels" or "whatsapp")

    Returns:
    - BlockClassificationResult (status + new_variants/new_tags lists).
    """
    # Use a local state if none was provided (keeps function backwards-compatible).
    if state is None:
        local_state = EnrichmentState()
    else:
        local_state = state

    message = _classification_prompt(block, local_state, retry=0, company_id=company_id, data_source=data_source)

    try:
        # Grok / Gemini / any BaseLLMClient-compatible client.
        resp = llm.generate(message)
        text = (resp.content or "").strip()

        if not text:
            # LLM returned nothing (safety/max_tokens/etc.)
            return BlockClassificationResult(
                block=block,
                status="empty_response",
            )

        # Try to extract JSON from response (handle markdown code blocks)
        def extract_json(text):
            """Extract JSON from text, handling markdown code blocks and other formatting."""
            import re
            
            # Try direct parsing first
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            
            # Try to extract JSON from markdown code blocks
            json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
            matches = re.findall(json_pattern, text, re.DOTALL)
            if matches:
                try:
                    return json.loads(matches[0])
                except json.JSONDecodeError:
                    pass
            
            # Try to find JSON object in text
            json_obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_obj_pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
            
            return None
        
        data = extract_json(text)
        
        if data is None:
            # Model didn't follow JSON-only instruction - retry
            retry_count = 1
            MAX_RETRIES = 3
            SUCCESS_FLAG = False
            while retry_count <= MAX_RETRIES:
                # Retry with a more explicit prompt
                retry_message = _classification_prompt(block, local_state, retry=retry_count)
                resp = llm.generate(retry_message)
                text = (resp.content or "").strip()
                data = extract_json(text)
                if data is not None:
                    SUCCESS_FLAG = True
                    break
                retry_count += 1
            
            if not SUCCESS_FLAG:
                return BlockClassificationResult(
                    block=block,
                    status="invalid_json",
                    raw_response=text,
                )

        # ------------------------
        # Extract + validate fields
        # ------------------------
        raw_variant = str(data.get("variant", "Unknown") or "Unknown").strip()
        raw_sentiment = str(data.get("sentiment", "neutral") or "neutral").strip().lower()
        raw_tags = data.get("tags") or []
        is_owner = data.get("is_owner", None)
        raw_summary = data.get("summary") or ""

        # Sentiment: keep the old logic, but clamp to ALLOWED_SENTIMENTS
        if raw_sentiment not in ALLOWED_SENTIMENTS:
            sentiment = "neutral"
        else:
            sentiment = raw_sentiment

        # Variant: allow new ones but clamp length & empties
        if not raw_variant:
            variant = "Unknown"
        else:
            variant = raw_variant
            if len(variant) > 64:
                variant = variant[:64]

        # Tag normalisation
        tags: List[str] = []
        if isinstance(raw_tags, list):
            seen: Set[str] = set()
            for t in raw_tags:
                if not isinstance(t, str):
                    continue
                norm = _normalise_tag(t)
                if not norm:
                    continue
                if norm in seen:
                    continue
                seen.add(norm)
                tags.append(norm)

        if not tags:
            tags = ["unknown"]

        # Summary: ensure we always have something
        summary = (raw_summary or "").strip()
        if not summary:
            summary = _fallback_summary(block.flattened_text)

        # ------------------------
        # Update dynamic registries
        # ------------------------
        new_variants: List[str] = []
        new_tags: List[str] = []

        if variant not in local_state.variants:
            local_state.variants.add(variant)
            new_variants.append(variant)

        for t in tags:
            if t not in local_state.tags:
                local_state.tags.add(t)
                new_tags.append(t)

        # ------------------------
        # Update block-level labels
        # ------------------------
        block.dominant_variant = variant
        block.dominant_sentiment = sentiment
        block.aggregated_tags = tags
        # Attach summary (ConversationBlock likely doesn't define this field,
        # but Python allows dynamic attribute assignment).
        setattr(block, "summary", summary)

        # Propagate to posts in this block (for analytics)
        def apply_to_post(p: CleanPost) -> None:
            if getattr(p, "variant", None) is None:
                p.variant = variant
            if getattr(p, "sentiment", None) is None:
                p.sentiment = sentiment
            existing = set(getattr(p, "tags", []) or [])
            if not hasattr(p, "tags") or p.tags is None:
                p.tags = []
                existing = set()
            for t in tags:
                if t not in existing:
                    p.tags.append(t)
            if is_owner is not None and p is block.root_post:
                p.is_owner = bool(is_owner)

        apply_to_post(block.root_post)
        for r in block.replies:
            apply_to_post(r)

        return BlockClassificationResult(
            block=block,
            status="success",
            raw_response=text,
            new_variants=new_variants,
            new_tags=new_tags,
        )

    except Exception as e:
        return BlockClassificationResult(
            block=block,
            status="error",
            error_message=str(e),
        )


def classify_blocks(
    blocks: List[ConversationBlock],
    llm: BaseLLMClient,
    state: Optional[EnrichmentState] = None,
    log_progress: bool = True,
    company_id: str = "haval",
    data_source: str = "pakwheels",
) -> List[BlockClassificationResult]:
    """
    Classify + summarise a list of blocks and return per-block results.

    - ConversationBlock objects are updated in-place.
    - If `state` is provided (recommended for real system), its
      `variants` and `tags` sets are updated in-place as new values
      are discovered.
    - Basic progress logging is printed to the console.

    Args:
        blocks: List of conversation blocks to classify
        llm: LLM client for classification
        state: Enrichment state with known variants/tags
        log_progress: Whether to show progress bar
        company_id: Company identifier (e.g., "haval", "kia", "toyota")
        data_source: Data source type ("pakwheels" or "whatsapp")
    """
    if state is None:
        state = EnrichmentState()

    total = len(blocks)
    results: List[BlockClassificationResult] = []
    sucess_count = 0
    fail_count = 0

    # Get company configuration for logging
    from config import get_company_config
    try:
        company_config = get_company_config(company_id)
        company_name = company_config.full_name
    except:
        company_name = company_id.title()

    if log_progress:
        print(f"\n{'='*80}")
        print(f"🤖 ENRICHMENT START")
        print(f"{'='*80}")
        print(f"📊 Company: {company_name} (ID: {company_id})")
        print(f"📂 Data Source: {data_source.upper()}")
        print(f"🔢 Total Blocks: {total}")
        print(f"🏷️  Variants in Config: {company_config.variants if hasattr(company_config, 'variants') and company_config.variants else 'Using SEED_VARIANTS'}")
        print(f"{'='*80}\n")

    # Use tqdm for progress bar if log_progress is True
    iterator = tqdm(blocks, desc="🤖 Enriching blocks", unit="block", ncols=100) if log_progress else blocks

    for b in iterator:
        res = classify_block(b, llm, state=state, company_id=company_id, data_source=data_source)
        if (
            res is not None and
            isinstance(res, BlockClassificationResult) and
            res.status == "success"
           ):
            sucess_count += 1
        else:
            fail_count += 1
            if log_progress:
                tqdm.write(f"⚠️  Block classification failed: {res.status if res else 'None'}")
        results.append(res)

    if log_progress:
        print(f"\n✅ Enrichment complete!")
        print(f"   Successful: {sucess_count}/{total} ({sucess_count*100//total if total > 0 else 0}%)")
        print(f"   Failed:     {fail_count}/{total}")

    return results


def compute_enrichment_metrics(
    results: List[BlockClassificationResult],
) -> EnrichmentMetrics:
    """
    Aggregate enrichment results into high-level metrics.
    """
    total = len(results)
    status_counter = Counter(r.status for r in results)
    variant_counter = Counter()
    sentiment_counter = Counter()
    tag_counter = Counter()

    for r in results:
        b = r.block
        if getattr(b, "dominant_variant", None):
            variant_counter[b.dominant_variant] += 1
        if getattr(b, "dominant_sentiment", None):
            sentiment_counter[b.dominant_sentiment] += 1
        for t in getattr(b, "aggregated_tags", []) or []:
            tag_counter[t] += 1

    return EnrichmentMetrics(
        total_blocks=total,
        status_counts=dict(status_counter),
        variant_counts=dict(variant_counter),
        sentiment_counts=dict(sentiment_counter),
        tag_counts=dict(tag_counter),
    )
