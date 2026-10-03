# Supply Chain Module

## Overview
This module provides natural language querying capabilities for the Haval Supply Chain Database. It follows the same architecture as the finance module but is specifically designed for supply chain operations.

## Database Structure
The supply chain database contains 5 interconnected tables:

1. **Suppliers** - Global supplier master data (20 suppliers from 8 countries)
2. **Parts** - Automotive component catalog (109 parts across 5 categories)
3. **Purchase_Orders** - Procurement tracking (645 orders, $561M spend)
4. **Inventory** - Stock management (355 positions, 168K units, $221M value)
5. **Shipments** - Delivery tracking (608 shipments with quality metrics)

## Module Structure

```
ai/SupplyChain/
├── __init__.py                    # Module exports
├── main.py                        # Entry point with SupplyChainManager
├── supplychain_pipeline.py        # Main pipeline orchestrator
├── domain_classifier.py           # In-domain/out-domain classification
├── query_reformulator.py          # Query preprocessing
├── format_detector.py             # Response format detection
├── sql_agent.py                   # LangChain SQL agent
├── db_manager.py                  # Database connection manager
├── supplychain_utils.py           # Helper utilities
├── logs/                          # Log files
└── metadata/                      # Table metadata (optional)
```

## Key Features

### 1. Domain Classification
- Regex-first approach for fast classification
- Detects supply chain vs. out-of-domain queries
- ~70-80% queries handled without LLM (token savings)

### 2. Query Reformulation
- Expands abbreviations (po → purchase order)
- Fixes common typos
- Clarifies ambiguous references

### 3. SQL Generation
- Natural language → SQL conversion
- Optimized prompts for supply chain context
- Support for complex multi-table queries

### 4. Response Formatting
- Context-aware answer formatting
- Currency, percentage, and quantity formatting
- Performance indicators and status categorization

## Usage

### Basic Usage

```python
from ai.SupplyChain.main import get_manager

# Initialize manager
manager = get_manager(db_path="data/haval_supply_chain.db")
manager.initialize()

# Process query
result = manager.process_query("Show me top 5 suppliers by spend")

print(result['answer'])
# Output: Top 5 suppliers by spend:
# 1. Bosch Automotive (Germany) - $45.2M
# 2. Denso Corporation (Japan) - $38.7M
# ...
```

### Advanced Usage

```python
from ai.SupplyChain.supplychain_pipeline import get_supplychain_pipeline

# Get pipeline directly
pipeline = get_supplychain_pipeline(db_path="data/haval_supply_chain.db")
pipeline.initialize()

# Execute query
result = pipeline.query(
    user_query="Which parts are low stock?",
    reformulated_query="List parts where stock status is low stock"
)

print(result['answer'])
print(result['sql'])  # See generated SQL
```

## Query Examples

### Supplier Queries
```
- "How many suppliers do we have?"
- "Show me top 5 suppliers by total spend"
- "Which suppliers have low on-time delivery rates?"
- "List all suppliers from Germany"
- "What's the average quality rating of Tier 1 suppliers?"
```

### Parts Queries
```
- "How many parts do we have in the powertrain category?"
- "Show me the most expensive parts"
- "List all parts with lead time over 30 days"
- "Which parts are critical?"
- "What's the average cost of electrical components?"
```

### Inventory Queries
```
- "Which parts are low stock?"
- "Show me inventory value by warehouse"
- "List overstock items"
- "What's the total inventory value?"
- "Which warehouses have low stock items?"
```

### Purchase Order Queries
```
- "How many pending purchase orders?"
- "Show me delayed orders"
- "What's the total procurement spend this year?"
- "List all high-priority orders"
- "Which orders are unpaid?"
```

### Shipment Queries
```
- "How many late deliveries?"
- "Show me shipments with quality issues"
- "What's the average delay time?"
- "List all failed quality inspections"
- "Which suppliers have the worst delivery performance?"
```

## Configuration

Add to `config/config.yml`:

```yaml
supplychain:
  database:
    type: sqlite
    path: data/haval_supply_chain.db
    included_tables:
      - Suppliers
      - Parts
      - Purchase_Orders
      - Inventory
      - Shipments
    
  llm:
    provider: xai
    
  agent:
    type: openai-tools
    verbose: true
    max_iterations: 10
    return_intermediate_steps: true
    max_execution_time: 120
    
  toolkit:
    sample_rows_in_table_info: 3
```

Add to `config/llm_config.py`:

```python
"supplychain_sql_agent": ModelConfig(
    model_name="grok-2-1212",
    temperature=0.1,
    max_tokens=2048,
    api_key_env="XAI_API_KEY"
),
```

## API Integration

For web integration, add to your controllers:

```python
from ai.SupplyChain.main import get_manager

@app.route('/api/supplychain/query', methods=['POST'])
def supplychain_query():
    data = request.json
    query = data.get('query', '')
    
    manager = get_manager()
    result = manager.process_query(query)
    
    return jsonify({
        'success': result['success'],
        'answer': result['answer'],
        'sql': result.get('sql'),
        'metadata': {
            'domain': result.get('domain_classification', {}).get('domain'),
            'confidence': result.get('domain_classification', {}).get('confidence')
        }
    })
```

## Testing

Run the test suite:

```bash
python ai/SupplyChain/main.py
```

Sample output:
```
Testing Supply Chain Manager:
======================================================================

🔍 Query: How many suppliers do we have?
✅ Answer: There are 20 active suppliers in the database.

🔍 Query: Show me top 5 suppliers by spend
✅ Answer: Top 5 suppliers by total spend:
1. Bosch Automotive (Germany) - $45.2M
2. Denso Corporation (Japan) - $38.7M
...

======================================================================
Stats: {
  'total_queries': 5,
  'regex_hits': 4,
  'llm_fallbacks': 1,
  'regex_hit_rate': '80.0%',
  'estimated_tokens_saved': 440
}
```

## Performance Optimization

1. **Regex-First Classification**: 70-80% of queries classified without LLM
2. **Token Savings**: ~110 tokens saved per regex hit
3. **Caching**: Implement query result caching for repeated queries
4. **Connection Pooling**: SQLAlchemy manages connection pooling automatically

## Error Handling

The module handles:
- Out-of-domain queries
- Database connection errors
- SQL generation errors
- Invalid query syntax
- Empty results

## Logging

Logs are written to:
- Console (INFO level)
- `ai/SupplyChain/logs/supplychain.log` (DEBUG level)

## Next Steps

1. **Add Metadata**: Create table metadata files in `metadata/` folder
2. **Fine-tune Prompts**: Adjust system prompts in `sql_agent.py`
3. **Add Caching**: Implement semantic caching for frequent queries
4. **Metrics Dashboard**: Build analytics dashboard for supply chain KPIs

## Differences from Finance Module

| Aspect | Finance Module | Supply Chain Module |
|--------|----------------|---------------------|
| Database | DMS (Dealer Management) | Supply Chain Operations |
| Tables | 4 (Sales, Dealers, Inventory, Revenue) | 5 (Suppliers, Parts, Orders, Inventory, Shipments) |
| Focus | CEO financial queries | Supply chain performance |
| Metrics | Revenue, Profit, Margins | OTD, Quality, Lead Time, Cost |
| Regex Patterns | Finance/automotive terms | Supply chain terms |
| LLM Config | finance_sql_agent | supplychain_sql_agent |

## Support

For issues or questions:
- Check logs in `ai/SupplyChain/logs/`
- Review query examples above
- Verify database connection
- Check LLM API key in environment variables

---

**Created**: January 2026  
**Database**: Haval Supply Chain (data/haval_supply_chain.db)  
**Architecture**: Based on finance module pattern
