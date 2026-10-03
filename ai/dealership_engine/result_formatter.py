"""
Dealership Result Formatter

Converts SQL results into natural language responses.
Formats data with tables, summaries, and insights.
"""

from typing import List, Dict, Any
from ai.llm_client import BaseLLMClient


def format_results(
    sql_results: List[Dict[str, Any]],
    original_question: str,
    query_classification: Dict[str, Any],
    llm: BaseLLMClient
) -> str:
    """
    Format SQL results into natural language response.

    Args:
        sql_results: Results from SQL query
        original_question: User's original question
        query_classification: Query classification details
        llm: LLM client for formatting

    Returns:
        Formatted natural language response
    """

    # Handle empty results
    if not sql_results or len(sql_results) == 0:
        return _generate_no_results_message(original_question, llm)

    query_type = query_classification.get('query_type', 'UNKNOWN')

    # Format based on query type
    if query_type == 'AGGREGATION':
        return _format_aggregation_results(sql_results, original_question, llm)

    elif query_type == 'HISTORY':
        return _format_history_results(sql_results, original_question, llm)

    elif query_type == 'COMPARISON':
        return _format_comparison_results(sql_results, original_question, llm)

    elif query_type in ['FILTERING', 'SEMANTIC']:
        return _format_filtering_results(sql_results, original_question, llm)

    else:
        # Default formatting
        return _format_default_results(sql_results, original_question, llm)


def _format_aggregation_results(
    results: List[Dict],
    question: str,
    llm: BaseLLMClient
) -> str:
    """Format aggregation/counting results"""

    # Single number result (simple COUNT)
    if len(results) == 1 and len(results[0]) == 1:
        count = list(results[0].values())[0]

        # Generate natural response
        summary_prompt = f"""Based on the dealership database, answer this question concisely:

Question: "{question}"
Result: {count}

Generate a 1-2 sentence natural language answer.

Examples:
Q: "How many tyre complaints in December?"
Result: 23
Answer: "There were **23 tyre-related warranty claims** in December."

Q: "Total PDI inspections?"
Result: 80
Answer: "The database shows **80 PDI inspections** have been completed."

Now answer:"""

        try:
            response = llm.generate(
                [{"role": "user", "content": summary_prompt}],
                max_tokens=100,
                temperature=0.3
            )
            return response.content.strip()
        except:
            return f"Based on the dealership data: **{count}**"

    # Multiple rows (GROUP BY results)
    else:
        # Create markdown table
        table = _create_markdown_table(results)

        # Generate summary
        summary_prompt = f"""Analyze these dealership statistics and provide insights:

**Question**: "{question}"

**Data**:
{table}

Provide:
1. A 1-sentence answer to the question
2. Key insights (top performer, trends, anomalies)
3. Keep it concise (2-3 sentences total)

Example:
Q: "Which dealership has most warranty claims?"
Data: Lahore: 45, Karachi: 38, Islamabad: 22

Answer:
"**Lahore dealership** has the most warranty claims with 45 cases, followed by Karachi (38) and Islamabad (22). Lahore accounts for 43% of all claims, suggesting either higher volume or quality issues that may need investigation."

Now provide your analysis:"""

        try:
            response = llm.generate(
                [{"role": "user", "content": summary_prompt}],
                max_tokens=200,
                temperature=0.3
            )
            summary = response.content.strip()
        except:
            summary = "Here are the results from the dealership database:"

        return f"{summary}\n\n**Detailed Breakdown:**\n{table}"


def _format_history_results(
    results: List[Dict],
    question: str,
    llm: BaseLLMClient
) -> str:
    """Format VIN history timeline"""

    if len(results) == 0:
        return f"No history found for the requested VIN number."

    # Create timeline
    timeline = "**Vehicle Service History:**\n\n"

    for idx, record in enumerate(results, 1):
        date = record.get('date') or record.get('claim_date') or record.get('inspection_date') or record.get('service_date') or record.get('ro_date') or 'Unknown date'
        service_type = _identify_service_type(record)
        details = _extract_key_details(record)

        timeline += f"{idx}. **{service_type}** - {date}\n"
        if details:
            timeline += f"   {details}\n"
        timeline += "\n"

    return timeline


def _format_comparison_results(
    results: List[Dict],
    question: str,
    llm: BaseLLMClient
) -> str:
    """Format comparison results"""

    table = _create_markdown_table(results)

    summary_prompt = f"""Compare these dealership statistics:

**Question**: "{question}"

**Comparison Data**:
{table}

Provide:
1. Direct comparison answer (which is higher/lower)
2. Percentage difference if relevant
3. Brief insight

Example:
Q: "Model A vs Model B warranty claims"
Data: Model A: 45, Model B: 32

Answer:
"**Model A has 41% more warranty claims** than Model B (45 vs 32 claims). This could indicate either higher sales volume for Model A or model-specific quality issues worth investigating."

Now provide comparison:"""

    try:
        response = llm.generate(
            [{"role": "user", "content": summary_prompt}],
            max_tokens=200,
            temperature=0.3
        )
        summary = response.content.strip()
    except:
        summary = "Comparison results:"

    return f"{summary}\n\n{table}"


def _format_filtering_results(
    results: List[Dict],
    question: str,
    llm: BaseLLMClient
) -> str:
    """Format filtered record results"""

    if len(results) <= 5:
        # Show full details for small result sets
        formatted = f"Found **{len(results)} record(s)**:\n\n"

        for idx, record in enumerate(results, 1):
            formatted += f"**Record {idx}:**\n"
            for key, value in record.items():
                if value is not None:
                    # Format key (remove underscores, title case)
                    display_key = key.replace('_', ' ').title()
                    formatted += f"- {display_key}: {value}\n"
            formatted += "\n"

        return formatted

    else:
        # Show table for large result sets
        table = _create_markdown_table(results[:20])  # Limit to first 20
        total_count = len(results)

        summary = f"Found **{total_count} records** matching your criteria.\n\n"

        if total_count > 20:
            summary += f"Showing first 20 results:\n\n"

        return summary + table


def _format_default_results(
    results: List[Dict],
    question: str,
    llm: BaseLLMClient
) -> str:
    """Default formatting fallback"""

    if len(results) == 1:
        # Single record - show details
        record = results[0]
        formatted = "**Result:**\n\n"
        for key, value in record.items():
            if value is not None:
                display_key = key.replace('_', ' ').title()
                formatted += f"- {display_key}: {value}\n"
        return formatted

    else:
        # Multiple records - show table
        table = _create_markdown_table(results[:50])  # Limit to 50
        return f"Found **{len(results)} results**:\n\n{table}"


def _generate_no_results_message(question: str, llm: BaseLLMClient) -> str:
    """Generate helpful message when no results found"""

    prompt = f"""The database query returned no results for this question:

"{question}"

Generate a helpful message (1-2 sentences) explaining:
1. No matching records were found
2. Suggest what the user could try (check spelling, try different filters, etc.)

Keep it friendly and concise.

Example:
Q: "Show warranty claims for VIN ABC123"
Answer: "No warranty claims found for VIN ABC123. Please verify the VIN number is correct (17 characters), or try searching by dealership or car model instead."

Now generate message:"""

    try:
        response = llm.generate(
            [{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3
        )
        return response.content.strip()
    except:
        return f"No results found for your query. Please try different search criteria or check for typos."


def _create_markdown_table(results: List[Dict]) -> str:
    """Create markdown table from results"""
    if not results:
        return "No data"

    # Get headers from first row
    headers = list(results[0].keys())

    # Format headers (title case, remove underscores)
    display_headers = [h.replace('_', ' ').title() for h in headers]

    # Build table
    table = "| " + " | ".join(display_headers) + " |\n"
    table += "| " + " | ".join(['---'] * len(headers)) + " |\n"

    for row in results:
        values = []
        for header in headers:
            value = row.get(header)
            # Format value
            if value is None:
                values.append('-')
            elif isinstance(value, float):
                values.append(f"{value:.2f}")
            else:
                values.append(str(value))

        table += "| " + " | ".join(values) + " |\n"

    return table


def _identify_service_type(record: Dict) -> str:
    """Identify service type from record"""
    if 'claim_type' in record or 'claim_date' in record:
        return "Warranty Claim"
    elif 'pdi_status' in record:
        return "PDI Inspection"
    elif 'campaign_name' in record:
        return "Campaign Service"
    elif 'ro_number' in record:
        return "Repair Order"
    elif 'findings' in record and 'odometer_reading' in record:
        if record.get('odometer_reading', 0) < 2000:
            return "FFS Inspection"
        else:
            return "SFS Inspection"
    else:
        return "Service Record"


def _extract_key_details(record: Dict) -> str:
    """Extract key details from record"""
    details = []

    if record.get('dealership_name'):
        details.append(f"Dealership: {record['dealership_name']}")

    if record.get('claim_type'):
        details.append(f"Type: {record['claim_type']}")

    if record.get('problem_description'):
        desc = record['problem_description']
        if len(desc) > 100:
            desc = desc[:97] + "..."
        details.append(f"Issue: {desc}")

    if record.get('cost'):
        details.append(f"Cost: PKR {record['cost']}")

    if record.get('status'):
        details.append(f"Status: {record['status']}")

    return " | ".join(details) if details else None
