# ai/rag_engine/__init__.py
"""
RAG Engine Package

Refactored modular structure for better maintainability.

Modules:
- core: Main RAGEngine class
- query_classification: Domain and query type classification
- query_optimizer: Query decomposition and optimization
- prompt_builder: System prompt construction
- citation_builder: Context and citation formatting
"""

from .core import RAGEngine

__all__ = ['RAGEngine']
