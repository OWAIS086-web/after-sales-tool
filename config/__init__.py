"""
Configuration Package

Centralized configuration for the Haval Marketing Tool.
"""

from .companies import (
    CompanyConfig,
    get_company_config,
    get_all_companies,
    get_enabled_companies,
    is_company_enabled,
    get_company_display_name,
    DEFAULT_COMPANY,
    COMPANIES,
)

from .llm_config import (
    LLMConfig,
    LLM_COMPONENTS,
    get_llm_config,
    get_llm_for_component,
    list_components,
    print_llm_config,
)

__all__ = [
    # Company configuration
    "CompanyConfig",
    "get_company_config",
    "get_all_companies",
    "get_enabled_companies",
    "is_company_enabled",
    "get_company_display_name",
    "DEFAULT_COMPANY",
    "COMPANIES",
    # LLM configuration
    "LLMConfig",
    "LLM_COMPONENTS",
    "get_llm_config",
    "get_llm_for_component",
    "list_components",
    "print_llm_config",
]
