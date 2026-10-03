"""
LLM Configuration Module

Centralized configuration for all LLM usage across the RAG pipeline.
Change LLM models for different components without touching code.

Usage:
    from config.llm_config import get_llm_for_component

    # Get LLM for answer generation
    llm = get_llm_for_component("answer_generation")

    # Get LLM for enrichment
    llm = get_llm_for_component("enrichment")
"""

from dataclasses import dataclass
from os import getenv
from typing import Dict, Optional

# Track which components have already printed config to avoid duplicates
_printed_configs = set()


@dataclass
class LLMConfig:
    """Configuration for a specific LLM"""

    provider: str  # "grok", "gemini", "openai"
    model_name: str  # e.g., "grok-3-fast", "gemini-2.5-flash", "gpt-4o"
    temperature: float = 0.2
    max_tokens: int = 2048
    api_key_env: str = None  # Environment variable name for API key

    def __post_init__(self):
        """Auto-set API key environment variable based on provider"""
        if self.api_key_env is None:
            if self.provider == "grok":
                self.api_key_env = "XAI_API_KEY"
            elif self.provider == "gemini":
                self.api_key_env = "GEMINI_API_KEY"
            elif self.provider == "openai":
                self.api_key_env = "OPENAI_API_KEY"


# =============================================================================
# LLM CONFIGURATION - CUSTOMIZE HERE
# =============================================================================

LLM_COMPONENTS: Dict[str, LLMConfig] = {
    # Query Classification: Lightweight classification of query domain
    # (in_domain, out_of_domain, small_talk)
    # Recommended: Fast, cheap model
    "query_classification": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=10,  # Only needs 1 word response
    ),

    # Merged Classifier: PRODUCTION OPTIMIZER - Combines 3 tasks in 1 LLM call
    # - Domain classification (in_domain, out_of_domain, small_talk)
    # - Format detection (bullet points, 200 words, table format, etc.)
    # - Query optimization (search queries + time window extraction)
    # Recommended: Fast model for quick turnaround (~25% faster than 3 separate calls)
    # Cost: ~$0.0003 per query (~400 tokens)
    "merged_classifier": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=400,  # Needs more tokens for JSON response with all 3 results
    ),

    # Query Optimizer: Decomposes complex queries into sub-queries
    # Extracts time windows and generates semantic filters
    # Recommended: Fast model with good reasoning
    "query_optimizer": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic optimization
        max_tokens=1024,
    ),

    # Answer Generation: Main RAG response generations
    # Generates detailed answers with context from vector store
    # Recommended: High-quality model for best responses
    # NOTE: This is kept for backward compatibility. Use mode-specific configs below.
    "answer_generation": LLMConfig(
        provider="grok", #openai
        model_name="grok-3-fast", #gpt-4o
        temperature=0.2,
        max_tokens=2048,
    ),

    # Answer Generation - THINKING MODE (Comprehensive Analysis)
    # Used when thinking_mode=True for detailed, structured responses
    # Higher temperature for creativity, more tokens for completeness
    # Adjust these values to control response detail and creativity
    "answer_generation_thinking": LLMConfig(
        provider="grok",  # Change to "openai" for GPT-4o
        model_name="grok-3-fast",  # Change to "gpt-4o" for GPT-4o
        temperature=1,   # Higher = more creative/verbose (0.5-1.0 recommended)
        max_tokens=4096,   # More tokens = more detailed answers
    ),

    # Answer Generation - NON-THINKING MODE (Clean Statistics)
    # Used when thinking_mode=False for focused, concise responses
    # Lower temperature for precision, fewer tokens for brevity
    # Adjust these values to control response length and focus
    "answer_generation_non_thinking": LLMConfig(
        provider="grok",  # Change to "openai" for GPT-4o
        model_name="grok-3-fast",  # Change to "gpt-4o" for GPT-4o
        temperature=0.4,   # Moderate = clear but not overly verbose (0.3-0.6 recommended)
        max_tokens=1024,   # Sufficient for detailed statistics
    ),

    # Insights Generation: Dedicated insights mode
    # Uses OpenAI for high-quality analysis
    # Recommended: Premium model for detailed insights
    "insights": LLMConfig(
        provider="openai",
        model_name="gpt-4o",
        temperature=0.3,
        max_tokens=4096,
    ),

    # Enrichment: Data enrichment pipeline
    # Classifies conversation blocks (variants, sentiment, tags)
    # Recommended: Balance between speed and quality
    "enrichment": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=512,
    ),

    # Context Compression: LLM-based semantic extraction for conversational memory
    # Extracts relevant portions of long assistant responses when user asks follow-up questions
    # Examples: "summarize point 3 above", "tell me more about the transmission issues"
    # Recommended: Cheap, fast model optimized for extraction (GPT-4o-mini is ideal)
    # Cost: ~$0.001 per compression (~500 input + 150 output tokens)
    "context_compression": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",  # $0.15/1M input, $0.60/1M output (10x cheaper than GPT-4o)
        temperature=0.0,  # Deterministic extraction
        max_tokens=150,  # Increased for structured compression with names/keywords
    ),

    # Query Reformulation: Rewrites context-dependent queries into standalone search queries
    # Used for follow-up questions that reference previous conversation
    # Examples: "provide references", "what about white ones?", "tell me more about that"
    # Recommended: Smart model for context understanding (GPT-4o-mini ideal)
    # Cost: ~$0.0003 per reformulation (~300 input + 200 output tokens)
    "query_reformulation": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",  # Better context understanding than Grok-3-fast
        temperature=0.2,  # Slight creativity for natural reformulations
        max_tokens=200,  # Enough for complex reformulations with customer names
    ),

    # =========================================================================
    # DEALERSHIP DATABASE COMPONENTS
    # =========================================================================

    # Dealership Domain Classifier: Check if query is about dealership data
    # Filters out irrelevant queries before processing (e.g., "Who is the best salesperson?")
    # Returns: IN_DOMAIN or OUT_OF_DOMAIN
    # Recommended: Fast model for quick filtering
    # Cost: ~$0.00002 per check (~20 tokens total)
    "dealership_domain_classifier": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=10,  # Only needs 1 word: "IN_DOMAIN" or "OUT_OF_DOMAIN"
    ),

    # Dealership Query Classification: Classify dealership query types
    # (AGGREGATION, FILTERING, COMPARISON, HISTORY, SEMANTIC)
    # Recommended: Fast model for quick classification
    # Cost: ~$0.0001 per classification (~100 tokens)
    "dealership_query_classifier": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=150,
    ),

    # Dealership Entity Extraction: Extract VINs, dealerships, dates, models
    # Handles typos, variations, abbreviations
    # Recommended: Smart model for flexible extraction
    # Cost: ~$0.0002 per extraction (~150 tokens)
    "dealership_entity_extractor": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic extraction
        max_tokens=200,
    ),

    # Dealership SQL Generator: Convert natural language to SQL
    # Critical component - needs to be accurate and safe
    # Recommended: Smart model for complex SQL generation
    # Cost: ~$0.0008 per SQL query (~400 tokens)
    "dealership_sql_generator": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",  # Use best available model for accuracy
        temperature=0.0,  # Deterministic SQL generation
        max_tokens=400,
    ),

    # DMS Metadata Generator: Generate business-friendly metadata for database tables
    # Creates descriptions, use cases, sample queries for all DMS tables
    # Recommended: Fast model for cost-effective batch generation
    # Cost: ~$0.002 per table (~1000 tokens) × 150 tables = ~$0.30 total
    "dms_metadata_generator": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Moderate creativity for natural descriptions
        max_tokens=1500,  # Enough for detailed metadata
    ),

    # Dealership Result Formatter: Format SQL results into natural language
    # Creates summaries, insights, and formatted responses
    # Recommended: Quality model for clear communication
    # Cost: ~$0.0005 per response (~250 tokens)
    "dealership_result_formatter": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Some creativity for natural responses
        max_tokens=500,
    ),

    # DMS Format Detector: Detect user's preferred output format (table, json, list, etc.)
    # Uses LLM to intelligently detect format instead of regex
    # Recommended: Fast model for quick detection
    # Cost: ~$0.00001 per detection (~10 tokens)
    "dms_format_detector": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic format detection
        max_tokens=10,  # Only needs 1 word response
    ),

    # DMS Answer Generation: Generate natural language answers from SQL results
    # Adaptive detail levels: brief (1024), moderate (1024), detailed (2048)
    # Recommended: Quality model for clear, professional responses
    # Cost: ~$0.001 per answer (~500 tokens average)
    "dms_answer_generation": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Some creativity for natural answers
        max_tokens=2048,  # Max for detailed responses (adaptive based on query)
    ),

    # DMS Decomposition Agent: Break complex queries into sub-queries
    # Determines if decomposition needed and creates execution plan
    # Recommended: Fast model for quick classification
    # Cost: ~$0.0001 per query (~300 tokens)
    "dms_decomposition": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.2,  # Low temperature for consistent decomposition
        max_tokens=800,
    ),

    # DMS Generation Agent: Generate SQL from natural language
    # Uses few-shot learning with schema context
    # Recommended: Fast model with good reasoning
    # Cost: ~$0.0002 per query (~500 tokens)
    "dms_generation": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Low temperature for consistent SQL
        max_tokens=600,
    ),

    # DMS Table Hints: Extract table names from queries using domain keywords
    # Used by schema_agent for semantic validation guard rail
    # Recommended: Fast model for quick keyword → table mapping
    # Cost: ~$0.00005 per query (~100 tokens)
    "dms_table_hints": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic extraction
        max_tokens=100,  # Only needs JSON array of 2-3 table names
    ),

    # =========================================================================
    # DMS FOLLOW-UP QUERY COMPONENTS (CONVERSATIONAL MEMORY)
    # =========================================================================

    # DMS Intent Classifier: Classify if query needs conversational context
    # Returns: standalone | context_dependent | meta_op | topic_switch
    # Uses regex-first optimization (70% queries use 0 tokens)
    # LLM fallback only for ambiguous cases
    # Recommended: Fast model for quick classification
    # Cost: ~$0.0001 per query (only 30% need LLM, rest use regex)
    "dms_intent_classifier": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=10,  # Only needs 1 word response
    ),

    # DMS Query Reformulator: Convert context-dependent queries to standalone
    # Resolves pronouns, carries forward context (VINs, names, dates)
    # Examples: "What about Ahmed?" → "Ahmed customer FFS records December 2024"
    # Recommended: Smart model for context understanding
    # Cost: ~$0.0003 per reformulation (~300 input + 200 output tokens)
    "dms_query_reformulator": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.2,  # Slight creativity for natural reformulations
        max_tokens=200,  # Enough for complex reformulations
    ),

    # DMS Meta-Operation Handler: Transform previous answers (summarize, elaborate, etc.)
    # Operates on PREVIOUS ANSWER without re-querying database
    # Examples: "Summarize above in 100 words", "Give me that in bullet points"
    # Recommended: Smart model for quality transformations
    # Cost: ~$0.0005 per operation (~250 input + 250 output tokens)
    "dms_meta_operation": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Creative for rephrasing
        max_tokens=2000,  # Enough for elaboration and reports
    ),

    # =========================================================================
    # FINANCE MODE COMPONENTS
    # =========================================================================

    # Finance Domain Classifier: Check if query is finance/DMS related
    # Filters out irrelevant queries (e.g., "What's the weather?")
    # Returns: IN_DOMAIN or OUT_OF_DOMAIN
    # Recommended: Fast model for quick filtering
    "finance_domain_classifier": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=10,  # Only needs 1 word response
    ),

    # Finance Query Reformulator: Expand abbreviations and improve query quality
    # Examples: "EMI" → "monthly installment", "DP" → "down payment"
    # Recommended: Fast model for quick reformulation
    "finance_query_reformulator": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.1,  # Reduced for faster responses
        max_tokens=150,  # Reduced for faster responses
    ),

    # Finance Format Detector: Detect query type and expected response format
    # Classifies: count, list, aggregate, search, comparison, analytical
    # Determines format: single_value, table, list, chart, summary
    # Recommended: Fast model for quick detection
    "finance_format_detector": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic detection
        max_tokens=80,  # Reduced for faster responses
    ),

    # Finance Answer Generation: Generate comprehensive finance responses
    # Uses company-specific context for personalized answers
    # Recommended: Smart model for quality responses
    "finance_answer_generation": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Balanced for informative responses
        max_tokens=800,  # Reduced from 1500 for faster responses
    ),

    # =========================================================================
    # FINANCE SQL AGENT (LANGCHAIN)
    # =========================================================================

    # Finance SQL Agent: LangChain SQL agent for direct database queries
    # Converts natural language to SQL and executes queries
    # Uses same provider as other components (grok) for consistency
    # Optimized for fast, accurate SQL generation with typo tolerance
    # Model: grok-3-fast (same as DMS for consistency)
    "finance_sql_agent": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",  # Same as DMS engine
        temperature=0.0,  # Deterministic SQL for consistency
        max_tokens=800,  # Sufficient for complex queries
    ),

    # =========================================================================
    # SUPPLY CHAIN COMPONENTS (CEO-LEVEL SUPPLY CHAIN QUERIES)
    # =========================================================================

    # Supply Chain Domain Classifier: Fast in-domain/out-domain classification
    # Filters out irrelevant queries (e.g., "What's the weather?")
    # Returns: IN_DOMAIN or OUT_OF_DOMAIN
    # Recommended: Fast model for quick filtering
    "supplychain_domain_classifier": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic classification
        max_tokens=10,  # Only needs 1 word response
    ),

    # Supply Chain Query Reformulator: Expand abbreviations and improve query quality
    # Examples: "OTD" → "on-time delivery", "LT" → "lead time"
    # Recommended: Fast model for quick reformulation
    "supplychain_query_reformulator": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.1,  # Reduced for faster responses
        max_tokens=150,  # Reduced for faster responses
    ),

    # Supply Chain Format Detector: Detect query type and expected response format
    # Classifies: count, list, aggregate, search, comparison, analytical
    # Determines format: single_value, table, list, chart, summary
    # Recommended: Fast model for quick detection
    "supplychain_format_detector": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.0,  # Deterministic detection
        max_tokens=80,  # Reduced for faster responses
    ),

    # Supply Chain Answer Generation: Generate comprehensive supply chain responses
    # Uses company-specific context for personalized answers
    # Recommended: Smart model for quality responses
    "supplychain_answer_generation": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",
        temperature=0.3,  # Balanced for informative responses
        max_tokens=800,  # Reduced from 1500 for faster responses
    ),

    # =========================================================================
    # SUPPLY CHAIN SQL AGENT (LANGCHAIN)
    # =========================================================================

    # Supply Chain SQL Agent: LangChain SQL agent for direct database queries
    # Converts natural language to SQL and executes queries
    # Uses same provider as other components (grok) for consistency
    # Optimized for fast, accurate SQL generation with typo tolerance
    # Model: grok-3-fast (consistent with finance and DMS)
    "supplychain_sql_agent": LLMConfig(
        provider="grok",
        model_name="grok-3-fast",  # Same as DMS and Finance for consistency
        temperature=0.0,  # Deterministic SQL for consistency
        max_tokens=800,  # Sufficient for complex queries
    ),
}


# =============================================================================
# DMS ANSWER GENERATION CONFIGURATION
# =============================================================================

# Token limits for different detail levels in DMS answer generation
# Can be adjusted to control response length and detail
DMS_ANSWER_TOKEN_LIMITS = {
    "brief": 1024,      # Short, direct answers (1-2 sentences)
    "moderate": 1024,   # Moderate answers with key details (3-5 sentences)
    "detailed": 2048,   # Detailed answers with insights and trends (5-8 sentences)
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_llm_config(component: str) -> LLMConfig:
    """
    Get LLM configuration for a specific component.

    Args:
        component: Component name (e.g., "query_classification", "answer_generation")

    Returns:
        LLMConfig object

    Raises:
        ValueError: If component is not configured
    """
    if component not in LLM_COMPONENTS:
        raise ValueError(
            f"Unknown LLM component: {component}. "
            f"Available: {list(LLM_COMPONENTS.keys())}"
        )
    return LLM_COMPONENTS[component]


def get_llm_for_component(component: str, fallback_api_key: Optional[str] = None):
    """
    Create and return an LLM client for a specific component.

    Args:
        component: Component name (e.g., "query_classification", "answer_generation")
        fallback_api_key: Fallback API key if environment variable not set

    Returns:
        BaseLLMClient instance (GrokClient, GeminiClient, or OpenAIClient)

    Raises:
        RuntimeError: If API key is not available
        ValueError: If provider is unknown
    """
    from ai.llm_client import FallbackLLMClient, GeminiClient, GrokClient

    config = get_llm_config(component)

    # Get API key from environment
    api_key = getenv(config.api_key_env)
    if not api_key and fallback_api_key:
        api_key = fallback_api_key

    if not api_key:
        raise RuntimeError(
            f"No API key found for {component}. "
            f"Set {config.api_key_env} environment variable."
        )

    # Create client based on provider
    if config.provider == "grok":
        # Create Grok client
        grok_client = GrokClient(
            api_key=api_key,
            model_name=config.model_name,
            temperature=config.temperature,
        )

        # AUTO-FALLBACK: Wrap with FallbackLLMClient that falls back to GPT-4o on 429 errors
        # Get OpenAI API key for fallback
        openai_key = getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                # Create GPT-4o fallback client
                gpt4o_client = GrokClient(  # Uses OpenAI-compatible format
                    api_key=openai_key,
                    model_name="gpt-4o",
                    temperature=config.temperature,
                    base_url="https://api.openai.com/v1",
                )

                # Wrap with fallback logic
                if component not in _printed_configs:
                    # print(f"[Config] {component}: Grok-3-Fast with GPT-4o fallback enabled")
                    _printed_configs.add(component)
                return FallbackLLMClient(
                    primary_client=grok_client,
                    fallback_client=gpt4o_client,
                    primary_name="Grok-3-Fast",
                    fallback_name="GPT-4o",
                )
            except Exception as e:
                if component not in _printed_configs:
                    print(f"[Config] Warning: Could not enable GPT-4o fallback: {e}")
                    print(f"[Config] Using Grok-3-Fast without fallback")
                    _printed_configs.add(component)
                return grok_client
        else:
            if component not in _printed_configs:
                print(f"[Config] Warning: OPENAI_API_KEY not set, Grok fallback disabled")
                _printed_configs.add(component)
            return grok_client

    elif config.provider == "gemini":
        return GeminiClient(
            api_key=api_key,
            model_name=config.model_name,
            temperature=config.temperature,
        )
    elif config.provider == "openai":
        # Import OpenAI client when needed
        try:
            from openai import OpenAI

            # Create a wrapper similar to GrokClient (OpenAI-compatible)
            return GrokClient(  # GrokClient works with any OpenAI-compatible API
                api_key=api_key,
                model_name=config.model_name,
                temperature=config.temperature,
                base_url="https://api.openai.com/v1",  # Official OpenAI endpoint
            )
        except ImportError:
            raise RuntimeError("OpenAI library not installed. Run: pip install openai")
    else:
        raise ValueError(f"Unknown LLM provider: {config.provider}")


def list_components() -> Dict[str, str]:
    """
    List all configured LLM components.

    Returns:
        Dict mapping component names to their model names
    """
    return {
        component: f"{config.provider}:{config.model_name}"
        for component, config in LLM_COMPONENTS.items()
    }


def print_llm_config():
    """Print current LLM configuration for debugging"""
    print("\n" + "="*70)
    print("LLM CONFIGURATION")
    print("="*70)
    for component, config in LLM_COMPONENTS.items():
        print(f"\n{component}:")
        print(f"  Provider: {config.provider}")
        print(f"  Model: {config.model_name}")
        print(f"  Temperature: {config.temperature}")
        print(f"  Max Tokens: {config.max_tokens}")
        print(f"  API Key: ${config.api_key_env}")
    print("="*70 + "\n")


# Convenience exports
__all__ = [
    "LLMConfig",
    "LLM_COMPONENTS",
    "DMS_ANSWER_TOKEN_LIMITS",
    "get_llm_config",
    "get_llm_for_component",
    "list_components",
    "print_llm_config",
]