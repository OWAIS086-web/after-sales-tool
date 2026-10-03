# ai/cross_platform/__init__.py
"""
Cross-Platform Query Engine

Handles queries that span multiple data sources (PakWheels, Reddit, WhatsApp)
by retrieving and combining results from all available platforms.

Quick Start:
    from ai.cross_platform import CrossPlatformEngine
    
    engine = CrossPlatformEngine(
        pakwheels_store=pakwheels_store,
        reddit_store=reddit_store,
        whatsapp_store=whatsapp_store,
        llm=llm_client,
        k=5
    )
    
    result = engine.query("What are common issues?")
    print(result["answer"])
    print(result["sources"])

Documentation:
    - README.md: Full technical documentation
    - QUICK_START.md: User guide
    - IMPLEMENTATION.md: Implementation details
    - DIAGRAMS.md: Visual architecture diagrams
"""

from .engine import CrossPlatformEngine

__all__ = ["CrossPlatformEngine"]
__version__ = "1.0.0"

