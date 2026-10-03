"""
Supply Chain Utilities
Helper functions for supply chain operations.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format currency amount for display.
    
    Args:
        amount: Amount to format
        currency: Currency code (USD, PKR, etc.)
        
    Returns:
        Formatted currency string
    """
    if currency == "USD":
        if amount >= 1_000_000:
            return f"${amount/1_000_000:.1f}M"
        elif amount >= 1_000:
            return f"${amount/1_000:.1f}K"
        else:
            return f"${amount:.2f}"
    elif currency == "PKR":
        if amount >= 10_000_000:
            return f"Rs {amount/10_000_000:.1f}Cr"
        elif amount >= 100_000:
            return f"Rs {amount/100_000:.1f}L"
        else:
            return f"Rs {amount:,.0f}"
    else:
        return f"{amount:,.2f} {currency}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format percentage for display.
    
    Args:
        value: Percentage value (0-100)
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    return f"{value:.{decimals}f}%"


def format_duration(days: int) -> str:
    """
    Format duration in days to human-readable format.
    
    Args:
        days: Number of days
        
    Returns:
        Formatted duration string
    """
    if days < 7:
        return f"{days} days"
    elif days < 30:
        weeks = days / 7
        return f"{weeks:.1f} weeks"
    elif days < 365:
        months = days / 30
        return f"{months:.1f} months"
    else:
        years = days / 365
        return f"{years:.1f} years"


def format_quantity(qty: int, unit: str = "units") -> str:
    """
    Format quantity for display.
    
    Args:
        qty: Quantity
        unit: Unit name
        
    Returns:
        Formatted quantity string
    """
    if qty >= 1_000_000:
        return f"{qty/1_000_000:.1f}M {unit}"
    elif qty >= 1_000:
        return f"{qty/1_000:.1f}K {unit}"
    else:
        return f"{qty:,} {unit}"


def get_performance_indicator(value: float, target: float = None, higher_is_better: bool = True) -> str:
    """
    Get performance indicator emoji based on value vs target.
    
    Args:
        value: Current value
        target: Target value (optional)
        higher_is_better: Whether higher value is better
        
    Returns:
        Performance indicator emoji
    """
    if target is None:
        return "📊"
    
    ratio = value / target if target != 0 else 0
    
    if higher_is_better:
        if ratio >= 1.1:
            return "🟢"  # Excellent
        elif ratio >= 0.95:
            return "🟡"  # Good
        else:
            return "🔴"  # Needs improvement
    else:
        if ratio <= 0.9:
            return "🟢"  # Excellent
        elif ratio <= 1.05:
            return "🟡"  # Good
        else:
            return "🔴"  # Needs improvement


def categorize_stock_status(quantity: int, safety_stock: int) -> str:
    """
    Categorize stock status based on quantity vs safety stock.
    
    Args:
        quantity: Current quantity
        safety_stock: Safety stock level
        
    Returns:
        Stock status category
    """
    if quantity == 0:
        return "Out of Stock"
    elif quantity < safety_stock * 0.5:
        return "Critical"
    elif quantity < safety_stock:
        return "Low Stock"
    elif quantity > safety_stock * 2:
        return "Overstock"
    else:
        return "Normal"


def categorize_delivery_performance(delay_days: int) -> str:
    """
    Categorize delivery performance based on delay.
    
    Args:
        delay_days: Number of days delayed (negative = early)
        
    Returns:
        Performance category
    """
    if delay_days <= 0:
        return "On Time"
    elif delay_days <= 3:
        return "Slight Delay"
    elif delay_days <= 7:
        return "Moderate Delay"
    else:
        return "Severe Delay"


def extract_table_name(sql_query: str) -> Optional[str]:
    """
    Extract primary table name from SQL query.
    
    Args:
        sql_query: SQL query string
        
    Returns:
        Table name or None
    """
    import re

    # Look for FROM clause
    match = re.search(r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_query, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return None


def validate_query_result(result: Any) -> bool:
    """
    Validate query result is not empty or error.
    
    Args:
        result: Query result
        
    Returns:
        True if valid, False otherwise
    """
    if result is None:
        return False
    
    if isinstance(result, (list, tuple)):
        return len(result) > 0
    
    if isinstance(result, dict):
        return bool(result)
    
    return True
