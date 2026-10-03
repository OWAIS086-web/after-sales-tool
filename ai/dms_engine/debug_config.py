"""
DMS Debug Configuration

Controls verbosity of DMS pipeline logging.

Set DMS_MINIMAL_LOGGING=1 in environment to only show:
- Cache hits/misses
- LLM calls

This suppresses:
- Agent initialization
- Schema selection details
- Validation details
- Decomposition details
- Result formatter details
"""

import os

# Check environment variable
_minimal_logging = os.getenv("DMS_MINIMAL_LOGGING", "0") == "1"


def should_print_verbose() -> bool:
    """Check if verbose logging is enabled"""
    return not _minimal_logging


def should_print_llm_call() -> bool:
    """LLM calls are always shown"""
    return True


def should_print_cache() -> bool:
    """Cache operations are always shown"""
    return True


def dms_print(message: str, force: bool = False, category: str = "verbose"):
    """
    Conditional print for DMS components.

    Args:
        message: The message to print
        force: If True, always print regardless of settings
        category: "verbose", "llm", "cache"
    """
    if force:
        print(message)
        return

    if category == "llm" and should_print_llm_call():
        print(message)
    elif category == "cache" and should_print_cache():
        print(message)
    elif category == "verbose" and should_print_verbose():
        print(message)
