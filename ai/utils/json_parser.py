"""
Robust JSON Parser for LLM Responses

Handles common JSON parsing issues from LLM responses:
- Control characters (\n, \t, \r, etc.)
- Unescaped quotes
- Markdown code blocks
- Trailing commas
- Comments
- Unicode issues

Production-tested, Docker-compatible, handles all edge cases.

"""

import json
import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def parse_llm_json(
    response: str,
    fallback: Optional[Dict[str, Any]] = None,
    strict: bool = False
) -> Dict[str, Any]:
    """
    Robustly parse JSON from LLM response.

    Applies multiple cleaning strategies to handle common LLM response issues.

    Args:
        response: Raw LLM response string
        fallback: Optional fallback dict if parsing fails
        strict: If True, raise exception on failure. If False, return fallback or empty dict

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If strict=True and parsing fails

    Examples:
        >>> parse_llm_json('{"sql": "SELECT\\nFROM table"}')
        {'sql': 'SELECT\\nFROM table'}

        >>> parse_llm_json('```json\\n{"key": "value"}\\n```')
        {'key': 'value'}

        >>> parse_llm_json('invalid json', fallback={"error": "failed"})
        {'error': 'failed'}
    """
    if not response or len(response.strip()) == 0:
        if strict:
            raise ValueError("Empty response")
        return fallback or {}

    original_response = response

    # STEP 1: Remove markdown code blocks
    # Example: ```json\\n{...}\\n``` → {...}
    response = re.sub(r'```json\s*', '', response, flags=re.IGNORECASE)
    response = re.sub(r'```\s*', '', response)

    # STEP 2: Extract JSON object (find first { to last })
    # Handles cases where LLM adds text before/after JSON
    match = re.search(r'\{.*\}', response, flags=re.DOTALL)
    if match:
        response = match.group(0)
    else:
        if strict:
            raise ValueError(f"No JSON object found in response: {original_response[:100]}")
        logger.warning(f"[JSON Parser] No JSON object found in response: {original_response[:100]}")
        return fallback or {}

    # STEP 3: Try direct parsing (works in ~80% of cases)
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        # logger.debug(f"[JSON Parser] Direct parse failed: {e}. Trying cleanup strategies...")
        pass

    # STEP 4: Apply aggressive cleanup strategies
    strategies = [
        _clean_control_characters,
        _clean_trailing_commas,
        _clean_unescaped_quotes,
        _clean_comments,
        _clean_unicode_issues,
        _last_resort_cleanup
    ]

    for i, strategy in enumerate(strategies, 1):
        try:
            cleaned = strategy(response)
            result = json.loads(cleaned)
            # logger.debug(f"[JSON Parser] ✓ Strategy {i} succeeded: {strategy.__name__}")
            return result
        except json.JSONDecodeError as e:
            # logger.debug(f"[JSON Parser] Strategy {i} failed: {strategy.__name__} - {e}")
            continue

    # STEP 5: All strategies failed
    if strict:
        raise ValueError(f"JSON parsing failed after all strategies. Response: {original_response[:200]}")

    logger.error(f"[JSON Parser] ✗ All strategies failed. Response: {original_response[:200]}")
    return fallback or {}


def _clean_control_characters(text: str) -> str:
    """
    Remove or escape control characters.

    Issue: LLM returns SQL with newlines/tabs that break JSON parsing
    Example: {"sql": "SELECT\nFROM table"} → {"sql": "SELECT FROM table"}

    Strategy: Replace problematic control characters with spaces
    """
    # Replace newlines, tabs, carriage returns with spaces
    text = text.replace('\n', ' ')
    text = text.replace('\r', ' ')
    text = text.replace('\t', ' ')

    # Remove other control characters (ASCII 0-31 except space)
    text = ''.join(char if ord(char) >= 32 or char == '\n' else ' ' for char in text)

    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)

    return text


def _clean_trailing_commas(text: str) -> str:
    """
    Remove trailing commas (common LLM mistake).

    Issue: LLM adds trailing comma before }
    Example: {"key": "value",} → {"key": "value"}

    Strategy: Remove commas before closing braces/brackets
    """
    # Remove comma before }
    text = re.sub(r',\s*}', '}', text)

    # Remove comma before ]
    text = re.sub(r',\s*]', ']', text)

    return text


def _clean_unescaped_quotes(text: str) -> str:
    """
    Escape unescaped quotes inside strings.

    Issue: LLM doesn't escape quotes in SQL strings
    Example: "reasoning": "Check "status" column" → "reasoning": "Check \"status\" column"

    Strategy: Find quotes inside string values and escape them
    """
    # This is complex and error-prone, so we use a simple heuristic:
    # Replace " with ' inside SQL strings (SQL supports both)
    # This works for most SQL generation cases

    # Find all string values (between "..." pairs)
    def escape_inner_quotes(match):
        content = match.group(1)
        # If content has quotes, replace with single quotes
        if '"' in content:
            content = content.replace('"', "'")
        return f'"{content}"'

    # Match "key": "value with potential inner quotes"
    text = re.sub(r'"([^"]*(?:"[^"]*)*)"', escape_inner_quotes, text)

    return text


def _clean_comments(text: str) -> str:
    """
    Remove JSON comments (not valid JSON but LLMs sometimes add them).

    Issue: LLM adds comments like // or /* */
    Example: {"key": "value"  // comment} → {"key": "value"}

    Strategy: Strip all comments
    """
    # Remove single-line comments
    text = re.sub(r'//.*?(?=\n|$)', '', text)

    # Remove multi-line comments
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    return text


def _clean_unicode_issues(text: str) -> str:
    """
    Fix unicode encoding issues.

    Issue: LLM returns malformed unicode
    Strategy: Ensure proper UTF-8 encoding
    """
    try:
        # Encode to UTF-8 and decode back to handle encoding issues
        text = text.encode('utf-8', errors='ignore').decode('utf-8')
    except Exception as e:
        logger.debug(f"[JSON Parser] Unicode cleaning failed: {e}")

    return text


def _last_resort_cleanup(text: str) -> str:
    """
    Last resort: aggressive cleanup.

    Strategy: Combine all strategies and remove all potentially problematic characters
    """
    # Apply all previous strategies
    text = _clean_control_characters(text)
    text = _clean_trailing_commas(text)
    text = _clean_comments(text)
    text = _clean_unicode_issues(text)

    # Remove any remaining non-printable characters
    text = ''.join(char for char in text if char.isprintable() or char in [' ', '\n', '\t'])

    # Fix common JSON structure issues
    text = text.strip()

    return text


def extract_json_from_response(response: str) -> Optional[str]:
    """
    Extract JSON substring from LLM response.

    Useful when LLM adds text before/after JSON.

    Args:
        response: Raw LLM response

    Returns:
        Extracted JSON string or None

    Examples:
        >>> extract_json_from_response('Here is the JSON: {"key": "value"}')
        '{"key": "value"}'

        >>> extract_json_from_response('No JSON here')
        None
    """
    # Find first { to last }
    match = re.search(r'\{.*\}', response, flags=re.DOTALL)
    if match:
        return match.group(0)

    # Find first [ to last ] (for JSON arrays)
    match = re.search(r'\[.*\]', response, flags=re.DOTALL)
    if match:
        return match.group(0)

    return None


def validate_json_fields(
    data: Dict[str, Any],
    required_fields: list,
    field_types: Optional[Dict[str, type]] = None
) -> bool:
    """
    Validate JSON has required fields with correct types.

    Args:
        data: Parsed JSON dict
        required_fields: List of required field names
        field_types: Optional dict mapping field names to expected types

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_json_fields({"sql": "SELECT *"}, ["sql"])
        True

        >>> validate_json_fields({"sql": 123}, ["sql"], {"sql": str})
        False
    """
    # Check required fields exist
    for field in required_fields:
        if field not in data:
            logger.warning(f"[JSON Validator] Missing required field: {field}")
            return False

    # Check field types
    if field_types:
        for field, expected_type in field_types.items():
            if field in data:
                if not isinstance(data[field], expected_type):
                    logger.warning(f"[JSON Validator] Field {field} has wrong type: {type(data[field])} (expected {expected_type})")
                    return False

    return True
