"""
Dealership SQL Generator

LLM-powered SQL generation with validation and security.
Converts natural language queries to safe SQL.
"""

from typing import Dict, Any, Tuple, List
from ai.llm_client import BaseLLMClient
import re

# Try to import sqlparse for validation (optional)
try:
    import sqlparse
    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False
    print("[SQL Generator] Warning: sqlparse not installed. Install with: pip install sqlparse")


# Database schema definition
DATABASE_SCHEMA = """
**DEALERSHIP DATABASE SCHEMA**:

1. **warranty_claims** (Technical Reports / Warranty Claims):
   - id (INTEGER PRIMARY KEY)
   - vin_number (TEXT) - 17-char vehicle ID
   - dealership_name (TEXT) - e.g. 'Lahore', 'Karachi', 'Islamabad'
   - car_model (TEXT) - e.g. 'Sportage', 'Picanto', 'Sorento'
   - variant (TEXT) - e.g. 'Premium', 'Comfort'
   - claim_date (DATE) - Format: YYYY-MM-DD
   - problem_description (TEXT) - Description of problem
   - problem_cause_analysis (TEXT) - Root cause analysis
   - claim_type (TEXT) - e.g. 'tyre', 'engine', 'transmission', 'electrical'
   - status (TEXT) - 'pending', 'approved', 'rejected'
   - cost (DECIMAL)

2. **pdi_inspections** (Pre-Delivery Inspection):
   - id (INTEGER PRIMARY KEY)
   - vin_number (TEXT UNIQUE) - One PDI per vehicle
   - dealership_name (TEXT)
   - car_model (TEXT)
   - variant (TEXT)
   - inspection_date (DATE)
   - factory_delivery_date (DATE)
   - pdi_status (TEXT) - 'passed', 'failed', 'objection'
   - objections (TEXT) - JSON array of objections
   - objection_count (INTEGER)
   - delivery_status (TEXT) - 'delivered', 'pending', 'rejected'
   - inspector_name (TEXT)

3. **ffs_inspections** (First Free Service at 1000km):
   - id (INTEGER PRIMARY KEY)
   - vin_number (TEXT)
   - dealership_name (TEXT)
   - car_model (TEXT)
   - inspection_date (DATE)
   - odometer_reading (INTEGER)
   - findings (TEXT)
   - recommendations (TEXT)
   - cost (DECIMAL)
   - status (TEXT) - 'completed'

4. **sfs_inspections** (Second Free Service at 5000km):
   - id (INTEGER PRIMARY KEY)
   - vin_number (TEXT)
   - dealership_name (TEXT)
   - car_model (TEXT)
   - inspection_date (DATE)
   - odometer_reading (INTEGER)
   - findings (TEXT)
   - cost (DECIMAL)
   - status (TEXT)

5. **campaigns** (Service Campaigns):
   - id (INTEGER PRIMARY KEY)
   - campaign_id (TEXT UNIQUE)
   - campaign_name (TEXT)
   - campaign_type (TEXT) - 'free_service', 'recall', 'inspection'
   - start_date (DATE)
   - end_date (DATE)

6. **campaign_services** (Campaign Service Records):
   - id (INTEGER PRIMARY KEY)
   - campaign_id (TEXT FOREIGN KEY)
   - vin_number (TEXT)
   - dealership_name (TEXT)
   - car_model (TEXT)
   - service_date (DATE)
   - service_type (TEXT)
   - status (TEXT) - 'completed'

7. **repair_orders** (RO List - Repair Orders):
   - id (INTEGER PRIMARY KEY)
   - ro_number (TEXT UNIQUE)
   - vin_number (TEXT)
   - chassis_number (TEXT)
   - dealership_name (TEXT)
   - car_model (TEXT)
   - customer_name (TEXT)
   - customer_phone (TEXT)
   - issue_description (TEXT)
   - repair_description (TEXT)
   - parts_used (TEXT) - JSON array
   - labor_hours (DECIMAL)
   - parts_cost (DECIMAL)
   - labor_cost (DECIMAL)
   - total_cost (DECIMAL)
   - ro_date (DATE)
   - completion_date (DATE)
   - status (TEXT) - 'open', 'in_progress', 'completed', 'cancelled'
   - warranty_applicable (BOOLEAN)

8. **vehicles** (Master Vehicle Data):
   - id (INTEGER PRIMARY KEY)
   - vin_number (TEXT UNIQUE)
   - chassis_number (TEXT)
   - engine_number (TEXT)
   - car_model (TEXT)
   - variant (TEXT)
   - model_year (INTEGER)
   - color (TEXT)
   - manufacturing_date (DATE)
   - delivery_date (DATE)
   - dealership_name (TEXT)
   - customer_name (TEXT)
   - status (TEXT) - 'active', 'warranty_terminated'

9. **dealerships** (Dealership Master):
   - id (INTEGER PRIMARY KEY)
   - dealership_code (TEXT UNIQUE)
   - dealership_name (TEXT)
   - city (TEXT)
   - region (TEXT)
   - contact_person (TEXT)
   - phone (TEXT)
   - email (TEXT)
"""


# Table-specific schema definitions for optimization
TABLE_SCHEMAS = {
    "warranty_claims": """
1. **warranty_claims** (Technical Reports / Warranty Claims):
   - id, vin_number (TEXT), dealership_name (TEXT), car_model (TEXT), variant (TEXT)
   - claim_date (DATE format: YYYY-MM-DD), problem_description (TEXT), problem_cause_analysis (TEXT)
   - claim_type (TEXT: 'tyre', 'engine', 'transmission', 'electrical'), status (TEXT), cost (DECIMAL)
""",
    "pdi_inspections": """
2. **pdi_inspections** (Pre-Delivery Inspection):
   - id, vin_number (TEXT UNIQUE), dealership_name (TEXT), car_model (TEXT), variant (TEXT)
   - inspection_date (DATE), factory_delivery_date (DATE), pdi_status (TEXT: 'passed', 'failed', 'objection')
   - objections (TEXT JSON array), objection_count (INTEGER), delivery_status (TEXT), inspector_name (TEXT)
""",
    "ffs_inspections": """
3. **ffs_inspections** (First Free Service at 1000km):
   - id, vin_number (TEXT), dealership_name (TEXT), car_model (TEXT), inspection_date (DATE)
   - odometer_reading (INTEGER), findings (TEXT), recommendations (TEXT), cost (DECIMAL), status (TEXT)
""",
    "sfs_inspections": """
4. **sfs_inspections** (Second Free Service at 5000km):
   - id, vin_number (TEXT), dealership_name (TEXT), car_model (TEXT), inspection_date (DATE)
   - odometer_reading (INTEGER), findings (TEXT), cost (DECIMAL), status (TEXT)
""",
    "campaigns": """
5. **campaigns** (Service Campaigns):
   - id, campaign_id (TEXT UNIQUE), campaign_name (TEXT)
   - campaign_type (TEXT: 'free_service', 'recall', 'inspection'), start_date (DATE), end_date (DATE)
""",
    "campaign_services": """
6. **campaign_services** (Campaign Service Records):
   - id, campaign_id (TEXT FK), vin_number (TEXT), dealership_name (TEXT), car_model (TEXT)
   - service_date (DATE), service_type (TEXT), status (TEXT)
""",
    "repair_orders": """
7. **repair_orders** (RO List - Repair Orders):
   - id, ro_number (TEXT UNIQUE), vin_number (TEXT), chassis_number (TEXT), dealership_name (TEXT)
   - car_model (TEXT), customer_name (TEXT), customer_phone (TEXT), issue_description (TEXT)
   - repair_description (TEXT), parts_used (TEXT JSON), labor_hours (DECIMAL), parts_cost (DECIMAL)
   - labor_cost (DECIMAL), total_cost (DECIMAL), ro_date (DATE), completion_date (DATE)
   - status (TEXT: 'open', 'in_progress', 'completed', 'cancelled'), warranty_applicable (BOOLEAN)
""",
    "vehicles": """
8. **vehicles** (Master Vehicle Data):
   - id, vin_number (TEXT UNIQUE), chassis_number (TEXT), engine_number (TEXT), car_model (TEXT)
   - variant (TEXT), model_year (INTEGER), color (TEXT), manufacturing_date (DATE), delivery_date (DATE)
   - dealership_name (TEXT), customer_name (TEXT), status (TEXT: 'active', 'warranty_terminated')
""",
    "dealerships": """
9. **dealerships** (Dealership Master):
   - id, dealership_code (TEXT UNIQUE), dealership_name (TEXT), city (TEXT), region (TEXT)
   - contact_person (TEXT), phone (TEXT), email (TEXT)
"""
}


def get_optimized_schema(query_classification: Dict[str, Any], entities: Dict[str, Any]) -> str:
    """
    Get optimized schema with only relevant tables.

    Reduces token usage from ~130 lines to ~20-40 lines.

    Args:
        query_classification: Query classification result
        entities: Extracted entities

    Returns:
        Optimized schema string with only relevant tables
    """
    query_type = query_classification.get('query_type', '')
    suggested_table = query_classification.get('suggested_table', '')

    # Determine relevant tables based on query and entities
    relevant_tables = set()

    # Add suggested table
    if suggested_table and suggested_table in TABLE_SCHEMAS:
        relevant_tables.add(suggested_table)

    # Add tables based on query type
    if query_type == 'HISTORY':
        # VIN history needs all tables
        relevant_tables.update(['warranty_claims', 'pdi_inspections', 'ffs_inspections',
                              'sfs_inspections', 'campaigns', 'campaign_services',
                              'repair_orders', 'vehicles'])

    # Add tables based on entities
    if entities.get('vin_number'):
        relevant_tables.add('vehicles')

    if entities.get('campaign'):
        relevant_tables.update(['campaigns', 'campaign_services'])

    # If no tables identified, use suggested or default to warranty_claims
    if not relevant_tables:
        if suggested_table:
            relevant_tables.add(suggested_table)
        else:
            relevant_tables.add('warranty_claims')

    # Build optimized schema
    schema_parts = ["**RELEVANT DATABASE TABLES**:\n"]
    for table in sorted(relevant_tables):
        if table in TABLE_SCHEMAS:
            schema_parts.append(TABLE_SCHEMAS[table])

    optimized_schema = "\n".join(schema_parts)

    # Log token savings
    full_tokens = len(DATABASE_SCHEMA.split())
    optimized_tokens = len(optimized_schema.split())
    savings = ((full_tokens - optimized_tokens) / full_tokens) * 100
    print(f"[Schema Optimizer] Token reduction: {full_tokens} → {optimized_tokens} tokens ({savings:.1f}% saved)")

    return optimized_schema


def generate_sql(
    question: str,
    query_classification: Dict[str, Any],
    entities: Dict[str, Any],
    llm: BaseLLMClient
) -> Tuple[str, bool]:
    """
    Generate SQL query from natural language using LLM.

    Args:
        question: User's original question
        query_classification: Classification result
        entities: Extracted entities
        llm: LLM client for SQL generation

    Returns:
        Tuple of (sql_query, is_valid)
    """

    query_type = query_classification.get('query_type')
    suggested_table = query_classification.get('suggested_table')

    # Use optimized schema (only relevant tables)
    optimized_schema = get_optimized_schema(query_classification, entities)

    sql_prompt = f"""{optimized_schema}

**TASK**: Generate a READ-ONLY SQL query to answer the user's question.

**USER QUESTION**: "{question}"

**QUERY CLASSIFICATION**:
- Type: {query_type}
- Needs Aggregation: {query_classification.get('needs_aggregation')}
- Needs Join: {query_classification.get('needs_join')}
- Suggested Table: {suggested_table}

**EXTRACTED ENTITIES**:
{_format_entities_for_prompt(entities)}

**SQL GENERATION RULES**:

0. **UNANSWERABLE QUERY GUARDRAIL** (CHECK FIRST):
   - If the question CANNOT be answered using the available tables above, respond with EXACTLY: "INVALID_QUERY"
   - Examples of INVALID queries:
     * "Who is the best salesperson?" (no salespeople table)
     * "What is our profit margin?" (no financial data)
     * "How many customers bought cars?" (no purchase/customer tables)
   - ONLY generate SQL if the question can be answered with the available schema

1. **SECURITY** (CRITICAL):
   - ONLY use SELECT statements
   - NEVER use: DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE, EXEC
   - Use parameterized queries (? placeholders) for user inputs
   - No SQL injection patterns

2. **DATE HANDLING**:
   - Use strftime('%m', date_column) for month extraction
   - Use strftime('%Y', date_column) for year extraction
   - Date format is YYYY-MM-DD
   - Example: WHERE strftime('%m', claim_date) = '12'

3. **TEXT SEARCH**:
   - Use LIKE '%keyword%' for partial matches
   - Case-insensitive: Use LOWER(column) LIKE LOWER('%keyword%')
   - Example: WHERE LOWER(claim_type) LIKE '%tyre%'

4. **AGGREGATIONS**:
   - Use COUNT(*), SUM(), AVG(), MAX(), MIN()
   - Always use GROUP BY when aggregating
   - Use ORDER BY for sorting results
   - **IMPORTANT:** When user asks "which has most" or "which has least", show TOP 10 (not LIMIT 1)
   - Example: SELECT dealership_name, COUNT(*) as count FROM ... GROUP BY dealership_name ORDER BY count DESC LIMIT 10

5. **PARTIAL MATCHING** (for car models, dealerships, names):
   - Use LIKE '%keyword%' for partial matches instead of exact equals
   - Example: For "Sportage", use `car_model LIKE '%Sportage%'` (matches "Sportage 2024", "Kia Sportage")
   - Example: For "Picanto", use `car_model LIKE '%Picanto%'` (matches "Picanto", "Picanto 2023")
   - For multiple models: `(car_model LIKE '%Sportage%' OR car_model LIKE '%Picanto%')`

6. **JOINS** (for multi-table queries):
   - Use INNER JOIN for related records
   - Use LEFT JOIN when one table might not have matches
   - Join on common fields (vin_number, campaign_id, dealership_name)

7. **LIMITS**:
   - For ranking queries ("most", "least", "top"): Use LIMIT 10 to show distribution
   - For listing queries: Use LIMIT 100
   - Only use LIMIT 1 if user explicitly asks for "the single" or "only one"

**QUERY TYPE SPECIFIC EXAMPLES**:

**AGGREGATION Example**:
Q: "How many tyre complaints in December?"
SQL:
```sql
SELECT COUNT(*) as complaint_count
FROM warranty_claims
WHERE LOWER(claim_type) LIKE '%tyre%'
AND strftime('%m', claim_date) = '12'
```

**FILTERING Example**:
Q: "Show warranty claims for VIN ABC123"
SQL:
```sql
SELECT vin_number, dealership_name, claim_date, claim_type, problem_description, cost
FROM warranty_claims
WHERE vin_number = 'ABC123'
ORDER BY claim_date DESC
```

**COMPARISON Example**:
Q: "Compare warranty claims between Model A and Model B"
SQL:
```sql
SELECT car_model, COUNT(*) as complaint_count
FROM warranty_claims
WHERE car_model LIKE '%Model A%' OR car_model LIKE '%Model B%'
GROUP BY car_model
ORDER BY complaint_count DESC
```

**AGGREGATION with GROUP BY Example (SHOW TOP 10)**:
Q: "Which dealership has most PDI inspections?"
SQL:
```sql
SELECT dealership_name, COUNT(*) as pdi_count
FROM pdi_inspections
GROUP BY dealership_name
ORDER BY pdi_count DESC
LIMIT 10
```

**JOIN Example**:
Q: "Show campaign services for a specific model"
SQL:
```sql
SELECT cs.dealership_name, cs.car_model, c.campaign_name, cs.service_date
FROM campaign_services cs
INNER JOIN campaigns c ON cs.campaign_id = c.campaign_id
WHERE cs.car_model LIKE '%Sportage%'
ORDER BY cs.service_date DESC
LIMIT 100
```

---

**NOW GENERATE SQL FOR THE USER'S QUESTION**:

Respond with ONLY the SQL query (no markdown, no explanations):
"""

    try:
        response = llm.generate(
            [{"role": "user", "content": sql_prompt}],
            max_tokens=400,
            temperature=0.0
        )

        # Extract SQL from response
        sql = _extract_sql_from_response(response.content)

        # Check for INVALID_QUERY response
        if sql.strip().upper() == "INVALID_QUERY":
            print(f"[SQL Generator] LLM determined query is unanswerable: INVALID_QUERY")
            return "INVALID_QUERY", False

        # Validate SQL
        is_valid = validate_sql(sql)

        if is_valid:
            print(f"[SQL Generator] Generated SQL:\n{sql}")
        else:
            print(f"[SQL Generator] INVALID SQL generated:\n{sql}")
            print(f"[SQL Generator] Security validation FAILED")

        return sql, is_valid

    except Exception as e:
        print(f"[SQL Generator] Error generating SQL: {e}")
        return "", False


def validate_sql(sql: str) -> bool:
    """
    Validate SQL is safe and read-only.

    Uses both sqlparse (if available) and regex-based validation.

    Args:
        sql: SQL query to validate

    Returns:
        True if SQL is safe
    """
    if not sql or len(sql.strip()) == 0:
        return False

    sql_upper = sql.upper()

    # Must start with SELECT
    if not sql_upper.strip().startswith('SELECT'):
        print("[SQL Validator] FAIL: Query must start with SELECT")
        return False

    # Optional: Use sqlparse for syntax validation and deep analysis
    if HAS_SQLPARSE:
        try:
            # Parse the SQL
            parsed = sqlparse.parse(sql)

            if not parsed or len(parsed) == 0:
                print("[SQL Validator] FAIL: sqlparse could not parse SQL")
                return False

            # Check for multiple statements
            if len(parsed) > 1:
                print(f"[SQL Validator] FAIL: Multiple SQL statements detected ({len(parsed)} statements)")
                return False

            # Get the statement
            statement = parsed[0]

            # Check statement type (should be SELECT)
            if statement.get_type() != 'SELECT':
                print(f"[SQL Validator] FAIL: Statement type is '{statement.get_type()}', expected 'SELECT'")
                return False

            # Check for forbidden keywords in parsed tokens
            forbidden_in_tokens = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
                                  'TRUNCATE', 'REPLACE', 'EXEC', 'EXECUTE', 'PRAGMA']

            tokens_upper = [str(token).upper() for token in statement.flatten()]
            for forbidden in forbidden_in_tokens:
                if forbidden in tokens_upper:
                    print(f"[SQL Validator] FAIL: Forbidden keyword '{forbidden}' found in tokens")
                    return False

            print("[SQL Validator] ✓ sqlparse validation passed")

        except Exception as e:
            print(f"[SQL Validator] WARNING: sqlparse validation error: {e}")
            # Continue with regex validation if sqlparse fails
            pass

    # Forbidden keywords (write operations)
    forbidden = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
        'TRUNCATE', 'REPLACE', 'EXEC', 'EXECUTE', 'PRAGMA'
    ]

    for keyword in forbidden:
        # Check for standalone keyword (not part of column name)
        pattern = r'\b' + keyword + r'\b'
        if re.search(pattern, sql_upper):
            print(f"[SQL Validator] FAIL: Forbidden keyword '{keyword}' detected")
            return False

    # Check for SQL injection patterns
    injection_patterns = [
        r'--',  # SQL comment
        r'/\*',  # Block comment start
        r';.*SELECT',  # Multiple statements
        r';\s*DROP',  # Dangerous chained command
        r'UNION.*SELECT',  # UNION injection (too restrictive, commented out)
    ]

    for pattern in injection_patterns:
        if re.search(pattern, sql, re.IGNORECASE):
            print(f"[SQL Validator] FAIL: Injection pattern detected: {pattern}")
            return False

    # Check for excessive semicolons (multiple statements)
    semicolon_count = sql.count(';')
    if semicolon_count > 1:
        print(f"[SQL Validator] FAIL: Multiple statements detected (semicolons: {semicolon_count})")
        return False

    print("[SQL Validator] PASS: SQL is safe")
    return True


def _extract_sql_from_response(response: str) -> str:
    """Extract SQL from LLM response (remove markdown, comments)"""
    sql = response.strip()

    # Remove markdown code blocks
    sql = re.sub(r'```sql\s*', '', sql)
    sql = re.sub(r'```\s*', '', sql)

    # Remove leading/trailing whitespace
    sql = sql.strip()

    # Remove trailing semicolon if present (we'll add it back if needed)
    sql = sql.rstrip(';')

    return sql


def _format_entities_for_prompt(entities: Dict[str, Any]) -> str:
    """Format extracted entities for SQL generation prompt"""
    formatted = []

    if entities.get('vin_number'):
        formatted.append(f"- VIN: {entities['vin_number']}")

    if entities.get('dealership_name'):
        formatted.append(f"- Dealership: {entities['dealership_name']}")

    if entities.get('car_model'):
        model = entities['car_model']
        if isinstance(model, list):
            formatted.append(f"- Car Models: {', '.join(model)}")
        else:
            formatted.append(f"- Car Model: {model}")

    if entities.get('date_filter'):
        date_filter = entities['date_filter']
        if date_filter.get('month'):
            formatted.append(f"- Month: {date_filter['month']}")
        if date_filter.get('year'):
            formatted.append(f"- Year: {date_filter['year']}")
        if date_filter.get('start_date') and date_filter.get('end_date'):
            formatted.append(f"- Date Range: {date_filter['start_date']} to {date_filter['end_date']}")

    if entities.get('claim_type'):
        formatted.append(f"- Claim Type: {entities['claim_type']}")

    if entities.get('service_type'):
        formatted.append(f"- Service Type: {entities['service_type']}")

    if entities.get('status_filter'):
        formatted.append(f"- Status: {entities['status_filter']}")

    if entities.get('metric'):
        formatted.append(f"- Metric: {entities['metric']}")

    if entities.get('aggregation_field'):
        formatted.append(f"- Group By: {entities['aggregation_field']}")

    if entities.get('limit'):
        formatted.append(f"- Limit: {entities['limit']}")

    if entities.get('has_objections') is not None:
        formatted.append(f"- Has Objections: {entities['has_objections']}")

    if entities.get('comparison_entities'):
        formatted.append(f"- Comparison: {', '.join(entities['comparison_entities'])}")

    return '\n'.join(formatted) if formatted else "No specific entities extracted"
