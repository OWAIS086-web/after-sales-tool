"""
Tier 2: Pre-built SQL Views

Common report queries from Haval Aftersales requirements.

WHY TIER 2 EXISTS:
==================
Problem: 40-50% of queries are common reports/dashboards
         - "Which dealership performed most PDIs?"
         - "Monthly campaign summary"
         - "Warranty claims by model"

These queries are asked frequently but LLM generation is slow and expensive.

Solution: Pre-built SQL views/functions
  - Identify top 20-30 common queries from user requirements
  - Create optimized SQL views
  - Router maps query → view name
  - Execute instantly (0.1-0.5s vs 2-3s)

VIEWS BASED ON HAVAL MEETING NOTES:
====================================
From meeting transcription, identified these common query patterns:

1. TECHNICAL REPORTS (Warranty Claims)
   - VINs with most complaints
   - Dealership with most PDIs
   - Tyre-related complaints by month
   - Warranty claims by type

2. CAMPAIGN REPORTS
   - Vehicles serviced under campaigns
   - Campaigns by model (H6, Jolion)
   - Dealership campaign performance
   - 6-month/yearly campaign analysis

3. FFS/SFS INSPECTION
   - Dealership with most FFS services
   - Breakdown by vehicle type

4. PDI INSPECTION
   - PDI reports by date range
   - PDIs with objections
   - Rejected vehicles
   - Yearly PDI totals

5. RO LIST (Repair Orders)
   - ROs against VIN
   - Warranty termination dates

Production Features:
- Optimized SQL with indexes
- Parameterized queries
- RLS injection
- Result caching (optional)
- Fast execution (0.1-0.5s)
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class ViewMatch:
    """
    Matched pre-built view with parameters.

    Contains:
    - view_name: Which view matched
    - sql: Pre-built SQL
    - parameters: Query parameters (month, year, model, etc.)
    - description: What this view returns
    - confidence: Match confidence
    """
    view_name: str
    sql: str
    parameters: Dict[str, Any]
    description: str
    confidence: float


class Tier2Views:
    """
    Tier 2 Pre-built SQL Views for common reports.

    MENTAL MAP:
    ===========
    1. Input: User query
    2. Intent matching: Match to view category
    3. Parameter extraction: Extract filters (month, model, etc.)
    4. View selection: Choose matching view
    5. Parameter injection: Fill view with parameters
    6. RLS injection: Add DealerId filtering
    7. Output: Ready-to-execute SQL

    Based on Haval Aftersales meeting notes (translated from Urdu).
    """

    def __init__(self, dealer_id: Optional[str] = None, schema_agent=None):
        """
        Initialize Tier 2 Views.

        Args:
            dealer_id: Dealer ID for RLS injection
            schema_agent: Schema agent for semantic table validation
        """
        self.dealer_id = dealer_id
        self.schema_agent = schema_agent  # For semantic validation

        # Define view patterns based on meeting notes
        self.views = {
            # TECHNICAL REPORTS / WARRANTY CLAIMS
            'vins_most_complaints': {
                'keywords': ['vin', 'most', 'complaint', 'highest', 'number'],
                'required_tables': ['RoMaster'],  # Must use repair orders for complaints
                'excluded_keywords': [
                    'pdi', 'inspection', 'delivery',  # Not PDI queries
                    'count', 'total', 'how many', 'total number', 'unique',  # ⭐ Exclude count/aggregate queries
                    'distinct', 'all', 'entire', 'database'  # ⭐ Exclude queries asking for counts of ALL VINs
                ],
                'description': 'VINs with highest number of complaints (TOP N ranking, not counts)',
                'sql_builder': self._get_vins_most_complaints_sql
            },

            'dealership_most_pdis': {
                'keywords': ['dealership', 'dealer', 'most', 'pdi', 'performed', 'inspection', 'delivery'],
                'required_keywords': ['pdi'],  # MUST have PDI in query
                'required_tables': ['PDIMaster'],  # Must use PDI table
                'excluded_keywords': ['warranty', 'repair', 'order', 'complaint', 'campaign'],  # Not other types
                'description': 'Dealership that performed most PDIs',
                'sql_builder': self._get_dealership_most_pdis_sql
            },

            'tyre_complaints_monthly': {
                'keywords': ['tyre', 'tire', 'complaint', 'december', 'month'],
                'required_tables': ['RoMaster'],  # Complaints are in repair orders
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign'],
                'description': 'Tyre-related complaints by month',
                'sql_builder': self._get_tyre_complaints_sql
            },

            'warranty_claims_by_type': {
                'keywords': ['warranty', 'claim', 'total', 'number', 'type'],
                'required_keywords': ['warranty'],
                'required_tables': ['RoMaster'],  # Warranty claims are in repair orders
                'excluded_keywords': ['pdi', 'inspection', 'delivery'],
                'description': 'Total warranty claims by type',
                'sql_builder': self._get_warranty_claims_by_type_sql
            },

            # CAMPAIGN REPORTS
            'campaign_by_model': {
                'keywords': ['campaign', 'h6', 'jolion', 'model', 'how many'],
                'required_keywords': ['campaign'],
                'required_tables': ['CampaignRpt'],  # Campaigns are in CampaignRpt
                'excluded_keywords': ['warranty', 'repair', 'order', 'pdi', 'inspection'],
                'description': 'Campaigns by vehicle model (H6, Jolion)',
                'sql_builder': self._get_campaign_by_model_sql
            },

            'dealership_campaigns': {
                'keywords': ['dealership', 'campaign', 'most', 'conducted', 'performed'],
                'required_keywords': ['campaign'],
                'required_tables': ['CampaignRpt'],  # Campaigns are in CampaignRpt
                'excluded_keywords': ['warranty', 'repair', 'order', 'pdi', 'inspection'],
                'description': 'Dealership with most campaigns',
                'sql_builder': self._get_dealership_campaigns_sql
            },

            'campaign_analysis_period': {
                'keywords': ['campaign', '6', 'month', 'yearly', 'year', 'analysis'],
                'required_keywords': ['campaign'],
                'required_tables': ['CampaignRpt'],  # Campaigns are in CampaignRpt
                'excluded_keywords': ['warranty', 'repair', 'order', 'pdi', 'inspection'],
                'description': '6-month or yearly campaign analysis',
                'sql_builder': self._get_campaign_analysis_period_sql
            },

            # FFS/SFS INSPECTION
            'dealership_most_ffs': {
                'keywords': ['dealership', 'ffs', 'most', 'service', 'inspection'],
                'required_keywords': ['ffs'],
                'required_tables': ['FFSMaster'],  # FFS services are in FFSMaster
                'excluded_keywords': ['pdi', 'delivery', 'warranty', 'repair', 'order', 'campaign'],
                'description': 'Dealership with most FFS services',
                'sql_builder': self._get_dealership_most_ffs_sql
            },

            'ffs_by_vehicle_type': {
                'keywords': ['ffs', 'haval', 'jolion', 'breakdown', 'type'],
                'required_keywords': ['ffs'],
                'required_tables': ['FFSMaster'],  # FFS services are in FFSMaster
                'excluded_keywords': ['pdi', 'delivery', 'warranty', 'repair', 'order', 'campaign'],
                'description': 'FFS breakdown by vehicle type',
                'sql_builder': self._get_ffs_by_vehicle_type_sql
            },

            # PDI INSPECTION
            'pdi_by_date_range': {
                'keywords': ['pdi', 'report', 'date', 'range', 'submitted'],
                'required_keywords': ['pdi'],
                'required_tables': ['PDIMaster'],  # PDI reports are in PDIMaster
                'excluded_keywords': ['warranty', 'repair', 'order', 'campaign', 'ffs', 'sfs'],
                'description': 'PDI reports by date range',
                'sql_builder': self._get_pdi_by_date_range_sql
            },

            'pdi_with_objections': {
                'keywords': ['pdi', 'objection', 'dealership', 'most'],
                'required_keywords': ['pdi'],
                'required_tables': ['PDIMaster'],  # PDI objections are in PDIMaster
                'excluded_keywords': ['warranty', 'repair', 'order', 'campaign', 'ffs', 'sfs'],
                'description': 'Dealerships with most PDI objections',
                'sql_builder': self._get_pdi_with_objections_sql
            },

            'rejected_vehicles': {
                'keywords': ['vehicle', 'rejected', 'dealership', 'how many'],
                'required_keywords': ['rejected'],
                'required_tables': ['PDIMaster'],  # Rejections are in PDIMaster
                'excluded_keywords': ['warranty', 'repair', 'order', 'campaign'],
                'description': 'Vehicles rejected by dealerships',
                'sql_builder': self._get_rejected_vehicles_sql
            },

            'yearly_pdi_totals': {
                'keywords': ['yearly', 'year', 'pdi', 'total', 'delivery'],
                'required_keywords': ['pdi'],
                'required_tables': ['PDIMaster'],  # PDI totals from PDIMaster
                'excluded_keywords': ['warranty', 'repair', 'order', 'campaign'],
                'description': 'Yearly PDI totals for delivery tracking',
                'sql_builder': self._get_yearly_pdi_totals_sql
            },

            'pdi_objection_percentage': {
                'keywords': ['pdi', 'percentage', 'objection', 'objections', 'last month', 'month'],
                'required_keywords': ['pdi'],
                'required_tables': ['PDIMaster'],  # PDI objections from PDIMaster
                'excluded_keywords': ['warranty', 'repair', 'order', 'campaign'],
                'description': 'Percentage of PDIs with objections for a given period',
                'sql_builder': self._get_pdi_objection_percentage_sql
            },

            # RO LIST (REPAIR ORDERS)
            'ro_count_by_vin': {
                'keywords': ['vin', 'specific vehicle', 'against vin', 'per vin', 'by vin'],
                'required_keywords': ['repair', 'order'],
                'required_tables': ['RoMaster'],  # Repair orders are in RoMaster
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign'],
                'description': 'Count of ROs against a specific VIN',
                'sql_builder': self._get_ro_count_by_vin_sql
            },

            'dealership_most_repair_orders': {
                'keywords': ['dealership', 'dealer', 'most', 'highest', 'repair', 'order', 'generated', 'top'],
                'required_keywords': ['dealership', 'repair'],
                'required_tables': ['RoMaster'],  # Repair orders are in RoMaster
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign', 'ffs', 'sfs', 'list'],
                'description': 'Dealerships ranked by number of repair orders',
                'sql_builder': self._get_dealership_most_repair_orders_sql
            },

            'dealership_most_warranty_complaints': {
                'keywords': ['dealership', 'dealer', 'most', 'highest', 'warranty', 'complaint', 'claim'],
                'required_keywords': ['dealership', 'warranty'],
                'required_tables': ['RoMaster'],  # Warranty claims are in RoMaster
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign', 'cancelled', 'cancel'],
                'description': 'Dealerships ranked by warranty complaint count',
                'sql_builder': self._get_dealership_most_warranty_complaints_sql
            },

            'customers_by_spending': {
                'keywords': ['customer', 'most', 'spent', 'spend', 'spending', 'amount', 'money', 'cost', 'total', 'top'],
                'required_keywords': ['customer'],
                'required_tables': ['RoMaster'],
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign', 'dealership', 'dealer'],
                'description': 'Customers ranked by total spending on repairs',
                'sql_builder': self._get_customers_by_spending_sql
            },

            'customers_frequent_visits': {
                'keywords': ['customer', 'most', 'frequent', 'visit', 'repair', 'came', 'time'],
                'required_keywords': ['customer'],
                'required_tables': ['RoMaster'],  # Customer visits in RoMaster
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign', 'dealership', 'dealer'],
                'description': 'Customers ranked by repair visit frequency',
                'sql_builder': self._get_customers_frequent_visits_sql
            },

            # COUNT QUERIES - Must come BEFORE listing queries for priority matching
            # These handle "count", "how many", "total number" queries for ALL major tables
            'count_repair_orders': {
                'keywords': ['count', 'how many', 'total', 'number', 'repair', 'order'],
                'required_keywords': ['repair', 'order'],
                'required_tables': ['RoMaster'],
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign', 'show', 'list', 'display', 'which', 'most'],
                'description': 'Count total repair orders',
                'sql_builder': self._get_count_repair_orders_sql
            },

            'count_pdi_reports': {
                'keywords': ['count', 'how many', 'total', 'number', 'pdi', 'report', 'inspection', 'delivery'],
                'required_keywords': ['pdi'],
                'required_tables': ['PDIMaster'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most', 'dealership'],
                'description': 'Count total PDI reports',
                'sql_builder': self._get_count_pdi_reports_sql
            },

            'count_ffs_inspections': {
                'keywords': ['count', 'how many', 'total', 'number', 'ffs', 'inspection', 'service', 'performed'],
                'required_keywords': ['ffs'],
                'required_tables': ['FFSMaster'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most', 'dealership'],
                'description': 'Count total FFS inspections',
                'sql_builder': self._get_count_ffs_inspections_sql
            },

            'count_sfs_inspections': {
                'keywords': ['count', 'how many', 'total', 'number', 'sfs', 'inspection', 'service', 'performed', 'across', 'all'],
                'required_keywords': ['sfs'],
                'required_tables': ['SFSMaster'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most'],
                'description': 'Count total SFS inspections',
                'sql_builder': self._get_count_sfs_inspections_sql
            },

            'count_campaigns': {
                'keywords': ['count', 'how many', 'total', 'number', 'campaign'],
                'required_keywords': ['campaign'],
                'required_tables': ['CampaignRpt'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most', 'dealership'],
                'description': 'Count total campaigns',
                'sql_builder': self._get_count_campaigns_sql
            },

            'count_warranty_claims': {
                'keywords': ['count', 'how many', 'total', 'number', 'warranty', 'claim'],
                'required_keywords': ['warranty'],
                'required_tables': ['RoMaster'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most', 'percentage', 'dealership'],
                'description': 'Count total warranty claims',
                'sql_builder': self._get_count_warranty_claims_sql
            },

            'count_csi_surveys': {
                'keywords': ['count', 'how many', 'total', 'number', 'csi', 'survey', 'satisfaction'],
                'required_keywords': ['csi'],
                'required_tables': ['CSIMaster'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most', 'dealership', 'average', 'score'],
                'description': 'Count total CSI surveys',
                'sql_builder': self._get_count_csi_surveys_sql
            },

            'count_vehicles': {
                'keywords': ['count', 'how many', 'total', 'number', 'vehicle', 'car'],
                'required_keywords': ['vehicle'],
                'required_tables': ['Vehicleinf'],
                'excluded_keywords': ['show', 'list', 'display', 'which', 'most', 'vin'],
                'description': 'Count total vehicles',
                'sql_builder': self._get_count_vehicles_sql
            },

            'show_all_repair_orders': {
                'keywords': ['show', 'all', 'repair', 'order', 'list', 'display'],
                'required_keywords': ['repair', 'order'],
                'required_tables': ['RoMaster'],  # Repair orders are in RoMaster
                'excluded_keywords': [
                    'pdi', 'inspection', 'delivery', 'campaign',
                    'most', 'highest', 'top', 'best', 'ranked', 'which', 'who',
                    'count', 'how many', 'total number'  # Exclude count keywords
                ],
                'description': 'Show all repair orders from RoMaster (listing, not ranking)',
                'sql_builder': self._get_show_all_repair_orders_sql
            },

            # ADDITIONAL TIER 2 VIEWS FOR PRODUCTION QUERIES
            'vins_with_multiple_ros': {
                'keywords': ['vin', 'multiple', 'repeated', 'more than', 'ros', 'repair', 'orders', 'frequently'],
                'required_keywords': ['vin'],  # Must explicitly mention VIN
                'required_tables': ['RoMaster'],  # Multiple repair orders from RoMaster
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign', 'dealership', 'dealer'],
                'description': 'VINs with multiple or repeated repair orders',
                'sql_builder': self._get_vins_multiple_ros_sql
            },

            'dealership_sales_vs_pdi': {
                'keywords': ['dealership', 'sales', 'pdi', 'completion', 'high', 'low'],
                'required_keywords': ['pdi', 'sales'],
                'required_tables': ['PDIMaster', 'Vehicleinf'],  # Uses both tables
                'excluded_keywords': ['warranty', 'repair', 'order', 'campaign'],
                'description': 'Dealerships with sales vs PDI completion comparison',
                'sql_builder': self._get_dealership_sales_vs_pdi_sql
            },

            'warranty_percentage_by_month': {
                'keywords': ['percentage', 'warranty', 'claims', 'december', 'month', 'tyre', 'related'],
                'required_keywords': ['warranty', 'percentage'],
                'required_tables': ['RoMaster'],  # Warranty claims are in repair orders
                'excluded_keywords': ['pdi', 'inspection', 'delivery', 'campaign'],
                'description': 'Percentage breakdown of warranty claims by type for a month',
                'sql_builder': self._get_warranty_percentage_by_month_sql
            },

            'monthly_summary_report': {
                'keywords': ['monthly', 'summary', 'month', 'december', 'november', 'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october'],
                'required_keywords': ['summary'],
                # No required_tables since this uses multiple tables
                'description': 'Monthly summary report (ROs, PDIs, campaigns)',
                'sql_builder': self._get_monthly_summary_sql
            },
        }

    def match(self, query: str) -> Optional[ViewMatch]:
        """
        Try to match query to a pre-built view with semantic validation.

        Args:
            query: User's natural language query

        Returns:
            ViewMatch if intent matched AND semantically valid, None otherwise
        """
        query_lower = query.lower()

        # CRITICAL: Check for unsupported relative date patterns
        # Tier 2 only supports explicit months (December, January) and years (2024)
        # If query has relative dates or complex temporal logic, reject and fall to Tier 3
        unsupported_date_patterns = [
            r'yesterday',
            r'last\s+\d+\s+days?',
            r'last\s+\d+\s+weeks?',
            r'past\s+\d+\s+days?',
            r'past\s+\d+\s+weeks?',
            r'this\s+week',
            r'last\s+week',
            r'year-over-year',
            r'year\s+over\s+year',
            r'yoy',
            r'which\s+months',  # Aggregation across months
            r'highest.*month',  # Finding peak months
        ]

        for unsupported_pattern in unsupported_date_patterns:
            if re.search(unsupported_pattern, query_lower):
                # Found unsupported date/temporal pattern - reject Tier 2, let Tier 3 handle it
                return None

        # Score each view
        best_match = None
        best_score = 0

        for view_name, config in self.views.items():
            # CHECK 1: Excluded keywords - if ANY present, skip this view
            excluded_kw = config.get('excluded_keywords', [])
            if any(kw in query_lower for kw in excluded_kw):
                continue  # Skip this view

            # CHECK 2: Required keywords - if specified, ALL must be present
            required_kw = config.get('required_keywords', [])
            if required_kw and not all(kw in query_lower for kw in required_kw):
                continue  # Skip this view

            # CHECK 3: Count keyword matches
            score = sum(1 for kw in config['keywords'] if kw in query_lower)

            if score > best_score:
                best_score = score
                best_match = view_name

        # Require at least 2 keyword matches
        if best_score >= 2:
            view_config = self.views[best_match]

            # CHECK 4: Semantic table validation (if schema_agent available)
            if self.schema_agent and 'required_tables' in view_config:
                # Get semantic top-k tables for this query
                try:
                    semantic_results = self.schema_agent.get_relevant_tables(query, top_k=5)
                    semantic_tables = [r['table_name'] for r in semantic_results]

                    # Check if view's required tables are in top-k
                    required_tables = view_config['required_tables']
                    tables_found = [t for t in required_tables if t in semantic_tables]

                    if not tables_found:
                        # View's tables not semantically relevant - reject match
                        return None  # Fall through to Tier 3

                    # CHECK 4B: Multi-table query detection (LLM-boosted tables check)
                    # If LLM hints extracted multiple high-priority tables (score > 0.7 indicates LLM boost),
                    # and the view doesn't use ALL of them, reject the view (fall to Tier 3 for multi-table JOIN)
                    llm_boosted_tables = [r['table_name'] for r in semantic_results if r['relevance_score'] > 0.7]

                    if len(llm_boosted_tables) > 1:
                        # Multi-table query detected
                        missing_tables = [t for t in llm_boosted_tables if t not in required_tables]
                        if missing_tables:
                            # View doesn't cover all LLM-suggested tables
                            return None  # Fall through to Tier 3

                except Exception as e:
                    # Continue anyway if semantic check fails
                    pass

            # Extract parameters (month, year, model, etc.)
            params = self._extract_parameters(query)

            # Build SQL
            sql = view_config['sql_builder'](params)

            # Inject RLS
            if self.dealer_id:
                sql = self._inject_rls(sql)

            return ViewMatch(
                view_name=best_match,
                sql=sql,
                parameters=params,
                description=view_config['description'],
                confidence=min(best_score / len(view_config['keywords']), 1.0)
            )

        return None

    def _extract_parameters(self, query: str) -> Dict[str, Any]:
        """Extract common parameters from query"""
        params = {}
        query_lower = query.lower()

        # Extract month
        months = {
            'january': '01', 'february': '02', 'march': '03',
            'april': '04', 'may': '05', 'june': '06',
            'july': '07', 'august': '08', 'september': '09',
            'october': '10', 'november': '11', 'december': '12'
        }

        for month_name, month_num in months.items():
            if month_name in query_lower:
                params['month'] = month_num
                break

        # Extract year - ONLY if explicitly mentioned in query
        year_match = re.search(r'20\d{2}', query)
        if year_match:
            params['year'] = year_match.group(0)
        # DO NOT default to current year - let views handle it based on query intent

        # Check for "all time" keywords - these should NOT have date filters
        # CRITICAL: Only use MULTI-WORD phrases to avoid false positives
        # "Total campaigns in 2025" should NOT be treated as all-time!
        # "in total", "all time", "of all time" ARE all-time queries
        all_time_keywords = ['in total', 'all time', 'of all time', 'historically', 'ever', 'across all time']
        if any(keyword in query_lower for keyword in all_time_keywords):
            params['period'] = 'all_time'
            # Remove any year/month that might have been extracted
            params.pop('year', None)
            params.pop('month', None)

        # Check for relative time periods
        if 'this year' in query_lower:
            params['period'] = 'this_year'
        elif 'last year' in query_lower:
            params['period'] = 'last_year'
        elif 'last month' in query_lower:
            params['period'] = 'last_month'
        elif 'this month' in query_lower:
            params['period'] = 'this_month'
        elif '6' in query and 'month' in query_lower:
            params['period'] = '6_months'
        elif 'quarterly' in query_lower or 'quarter' in query_lower:
            params['period'] = 'this_quarter'

        # Extract model
        if 'h6' in query_lower:
            params['model'] = 'H6'
        elif 'jolion' in query_lower:
            params['model'] = 'Jolion'

        return params

    # SQL BUILDERS
    # ------------

    def _get_vins_most_complaints_sql(self, params: Dict) -> str:
        """VINs with highest number of complaints with customer/model context"""
        return """
SELECT
    r.VINNO as VIN,
    v.CustomerName,
    v.Model,
    COUNT(*) as ComplaintCount,
    STRING_AGG(r.JobRequest, ',') as IssueTypes
FROM RoMaster r
LEFT JOIN Vehicleinf v ON r.VINNO = v.VinNo
WHERE r.JobRequest LIKE '%complaint%' OR r.JobRequest LIKE '%issue%'
GROUP BY r.VINNO, v.CustomerName, v.Model
ORDER BY ComplaintCount DESC
LIMIT 20
""".strip()

    def _get_dealership_most_pdis_sql(self, params: Dict) -> str:
        """Dealership that performed most PDIs with date filtering"""
        date_filter = self._build_date_filter(params)
        return f"""
SELECT
    DealershipName,
    COUNT(*) as TotalPDIs,
    SUM(CASE WHEN Status LIKE '%objection%' OR Status LIKE '%Rejected%' THEN 1 ELSE 0 END) as PDIsWithObjections,
    ROUND(100.0 * SUM(CASE WHEN Status LIKE '%objection%' OR Status LIKE '%Rejected%' THEN 1 ELSE 0 END) / COUNT(*), 2) as ObjectionRate
FROM PDIMaster
WHERE DealershipName IS NOT NULL
  {date_filter}
GROUP BY DealershipName
ORDER BY TotalPDIs DESC
LIMIT 10
""".strip()

    def _get_tyre_complaints_sql(self, params: Dict) -> str:
        """Tyre-related complaints by month"""
        month = params.get('month', datetime.now().strftime('%m'))
        year = params.get('year', str(datetime.now().year))

        return f"""
SELECT
    FORMAT(Date, 'yyyy-MM') as Month,
    COUNT(*) as TyreComplaints,
    STRING_AGG(Model, ',') as AffectedModels
FROM RoMaster
WHERE (JobRequest LIKE '%tyre%' OR JobRequest LIKE '%tire%')
  AND FORMAT(Date, 'yyyy-MM') = '{year}-{month}'
GROUP BY FORMAT(Date, 'yyyy-MM')
""".strip()

    def _get_warranty_claims_by_type_sql(self, params: Dict) -> str:
        """Total warranty claims by type with date filtering"""
        date_filter = self._build_date_filter(params)
        return f"""
SELECT
    CASE
        WHEN JobRequest LIKE '%tyre%' OR JobRequest LIKE '%tire%' THEN 'Tyre'
        WHEN JobRequest LIKE '%engine%' THEN 'Engine'
        WHEN JobRequest LIKE '%brake%' THEN 'Brake'
        WHEN JobRequest LIKE '%electrical%' THEN 'Electrical'
        ELSE 'Other'
    END as ClaimType,
    COUNT(*) as TotalClaims,
    SUM(TAmount) as TotalCost
FROM RoMaster
WHERE JobRequest LIKE '%warranty%'
  {date_filter}
GROUP BY ClaimType
ORDER BY TotalClaims DESC
""".strip()

    def _get_campaign_by_model_sql(self, params: Dict) -> str:
        """Campaigns by vehicle model with date filtering"""
        # CampaignRpt uses RDate column, not Date
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)

        # Build WHERE clause combining model and date filters
        where_clauses = []

        if params.get('model'):
            where_clauses.append(f"Vmodel LIKE '%{params['model']}%'")

        # Add date filter
        if year and month:
            month_int = int(month) if isinstance(month, str) else month
            where_clauses.append(f"FORMAT(RDate, 'yyyy-MM') = '{year}-{month_int:02d}'")
        elif year:
            where_clauses.append(f"YEAR(RDate) = '{year}'")
        elif period == 'this_year':
            where_clauses.append("YEAR(RDate) = YEAR(GETDATE())")
        elif period == 'last_year':
            where_clauses.append("YEAR(RDate) = YEAR(DATEADD(YEAR, -1, GETDATE()))")

        where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        return f"""
SELECT
    Vmodel as Model,
    COUNT(*) as TotalCampaigns,
    COUNT(DISTINCT VIN) as UniqueVehicles,
    COUNT(DISTINCT DealerId) as DealershipsInvolved
FROM CampaignRpt
{where_clause}
GROUP BY Vmodel
ORDER BY TotalCampaigns DESC
""".strip()

    def _get_dealership_campaigns_sql(self, params: Dict) -> str:
        """Dealership with most campaigns"""
        return """
SELECT
    d.DealerName,
    d.DealerCode,
    COUNT(*) as TotalCampaigns,
    COUNT(DISTINCT c.CampaignNo) as UniqueCampaigns,
    COUNT(DISTINCT c.Vmodel) as ModelsServiced
FROM CampaignRpt c
LEFT JOIN DealerRegister d ON c.DealerId = d.ID
WHERE d.DealerName IS NOT NULL
GROUP BY d.DealerName, d.DealerCode
ORDER BY TotalCampaigns DESC
LIMIT 10
""".strip()

    def _get_campaign_analysis_period_sql(self, params: Dict) -> str:
        """6-month or yearly campaign analysis"""
        period = params.get('period', '6_months')

        if period == '6_months':
            date_filter = "WHERE c.RDate >= DATEADD(MONTH, -6, GETDATE())"
        else:  # yearly
            year = params.get('year', str(datetime.now().year))
            date_filter = f"WHERE YEAR(c.RDate) = '{year}'"

        return f"""
SELECT
    d.DealerName,
    d.DealerCode,
    COUNT(*) as TotalCampaigns,
    FORMAT(c.RDate, 'yyyy-MM') as Month,
    COUNT(DISTINCT c.VIN) as VehiclesServiced
FROM CampaignRpt c
LEFT JOIN DealerRegister d ON c.DealerId = d.ID
{date_filter}
  AND d.DealerName IS NOT NULL
GROUP BY d.DealerName, d.DealerCode, FORMAT(c.RDate, 'yyyy-MM')
ORDER BY d.DealerName, Month
""".strip()

    def _get_dealership_most_ffs_sql(self, params: Dict) -> str:
        """Dealership with most FFS services"""
        return """
SELECT
    DealershipName,
    COUNT(*) as TotalFFS,
    COUNT(DISTINCT VIN) as UniqueVehicles,
    COUNT(DISTINCT Vmodel) as Models
FROM FFSMaster
WHERE DealershipName IS NOT NULL
GROUP BY DealershipName
ORDER BY TotalFFS DESC
LIMIT 10
""".strip()

    def _get_ffs_by_vehicle_type_sql(self, params: Dict) -> str:
        """FFS breakdown by vehicle type"""
        return """
SELECT
    CASE
        WHEN Vmodel LIKE '%Haval%' THEN 'Haval'
        WHEN Vmodel LIKE '%Jolion%' THEN 'Jolion'
        ELSE 'Other'
    END as VehicleType,
    COUNT(*) as TotalFFS,
    COUNT(DISTINCT VIN) as UniqueVehicles
FROM FFSMaster
GROUP BY VehicleType
ORDER BY TotalFFS DESC
""".strip()

    def _get_pdi_by_date_range_sql(self, params: Dict) -> str:
        """PDI reports by date range"""
        month = params.get('month')
        year = params.get('year', str(datetime.now().year))

        if month:
            date_filter = f"WHERE FORMAT(Date, 'yyyy-MM') = '{year}-{month}'"
        else:
            date_filter = f"WHERE YEAR(Date) = '{year}'"

        return f"""
SELECT
    DealerID,
    COUNT(*) as TotalPDIs,
    COUNT(DISTINCT VIN) as UniqueVehicles,
    SUM(CASE WHEN Status LIKE '%objection%' THEN 1 ELSE 0 END) as WithObjections
FROM PDIMaster
{date_filter}
GROUP BY DealerID
ORDER BY TotalPDIs DESC
""".strip()

    def _get_pdi_with_objections_sql(self, params: Dict) -> str:
        """Dealerships with most PDI objections"""
        return """
SELECT
    DealershipName,
    COUNT(*) as TotalObjections,
    STRING_AGG(FaultCode, ',') as CommonFaults
FROM PDIMaster
WHERE (Status LIKE '%objection%' OR Status LIKE '%Rejected%')
  AND DealershipName IS NOT NULL
GROUP BY DealershipName
ORDER BY TotalObjections DESC
LIMIT 10
""".strip()

    def _get_rejected_vehicles_sql(self, params: Dict) -> str:
        """Vehicles rejected by dealerships"""
        return """
SELECT
    DealershipName,
    Vmodel as Model,
    COUNT(*) as RejectedCount,
    STRING_AGG(FaultCode, ',') as RejectionReasons
FROM PDIMaster
WHERE (Status LIKE '%reject%' OR Status LIKE '%Rejected%')
  AND DealershipName IS NOT NULL
GROUP BY DealershipName, Vmodel
ORDER BY RejectedCount DESC
LIMIT 10
""".strip()

    def _get_yearly_pdi_totals_sql(self, params: Dict) -> str:
        """Yearly PDI totals for delivery tracking"""
        year = params.get('year', str(datetime.now().year))

        return f"""
SELECT
    '{year}' as Year,
    COUNT(*) as TotalPDIs,
    COUNT(DISTINCT VIN) as UniqueVehicles,
    COUNT(DISTINCT Vmodel) as ModelsProcessed,
    SUM(CASE WHEN Status LIKE '%complete%' THEN 1 ELSE 0 END) as Completed,
    SUM(CASE WHEN Status LIKE '%reject%' THEN 1 ELSE 0 END) as Rejected
FROM PDIMaster
WHERE YEAR(Date) = '{year}'
""".strip()

    def _get_pdi_objection_percentage_sql(self, params: Dict) -> str:
        """
        Calculate percentage of PDIs with objections for a given period.

        Objections are identified by FaultCode != 'No Issue'
        """
        # Extract month/year from params if provided, otherwise use last month
        month_text = params.get('month', 'last month')

        if 'last' in month_text.lower():
            # Last month
            date_filter = "Date >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND Date < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        elif 'this' in month_text.lower() or 'current' in month_text.lower():
            # Current month
            date_filter = "Date >= DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        else:
            # Try to parse specific month/year
            # For now, default to last month
            date_filter = "Date >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND Date < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"

        return f"""
SELECT
    COUNT(*) as TotalPDIs,
    SUM(CASE WHEN FaultCode IS NOT NULL AND FaultCode != '' AND FaultCode != 'No Issue' THEN 1 ELSE 0 END) as PDIsWithObjections,
    ROUND(CAST(SUM(CASE WHEN FaultCode IS NOT NULL AND FaultCode != '' AND FaultCode != 'No Issue' THEN 1 ELSE 0 END) AS FLOAT) * 100.0 / COUNT(*), 2) as ObjectionPercentage,
    MIN(date(Date)) as PeriodStart,
    MAX(date(Date)) as PeriodEnd
FROM PDIMaster
WHERE {date_filter}
""".strip()

    def _get_ro_count_by_vin_sql(self, params: Dict) -> str:
        """Count of ROs against a VIN"""
        return """
SELECT
    VINNO as VIN,
    COUNT(*) as TotalROs,
    SUM(TAmount) as TotalSpent,
    MAX(Date) as LastServiceDate,
    MIN(Date) as FirstServiceDate
FROM RoMaster
GROUP BY VINNO
HAVING COUNT(*) > 1
ORDER BY TotalROs DESC
LIMIT 20
""".strip()

    def _get_show_all_repair_orders_sql(self, params: Dict) -> str:
        """Show all repair orders - simple list from RoMaster with robust date filtering"""
        # Extract date parameters
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)

        # Build date filter
        date_filter = ""
        if year and month:
            # FIX: Convert month to int to avoid format string error
            month_int = int(month) if isinstance(month, str) else month
            date_filter = f"AND FORMAT(r.Date, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            date_filter = f"AND YEAR(r.Date) = '{year}'"
        elif period == 'this_year':
            date_filter = "AND YEAR(r.Date) = YEAR(GETDATE())"
        elif period == 'last_month':
            date_filter = "AND r.Date >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND r.Date < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        elif period == 'this_month':
            date_filter = "AND FORMAT(r.Date, 'yyyy-MM') = FORMAT(GETDATE(), 'yyyy-MM')"
        # If no period specified, show all (no date filter)

        return f"""
SELECT
    r.RoNo as RepairOrderNo,
    r.Date as OrderDate,
    r.CustomerName,
    r.VINNO as VIN,
    r.Model,
    r.JobRequest as ServiceType,
    r.TAmount as TotalAmount,
    d.DealerName,
    d.DealerCode
FROM RoMaster r
LEFT JOIN DealerRegister d ON r.DealerId = d.ID
WHERE d.DealerName IS NOT NULL
  {date_filter}
ORDER BY r.Date DESC
LIMIT 100
""".strip()

    def _get_vins_multiple_ros_sql(self, params: Dict) -> str:
        """VINs with multiple or repeated repair orders WITH context enrichment"""
        # Extract threshold if mentioned (default: 3)
        threshold = 3

        return f"""
SELECT
    r.VINNO as VIN,
    v.CustomerName,
    v.Model,
    v.Variant,
    d.DealerName as PrimaryDealer,
    COUNT(*) as RepairOrderCount,
    MIN(r.Date) as FirstRepair,
    MAX(r.Date) as LastRepair,
    SUM(r.TAmount) as TotalSpent,
    STRING_AGG(r.JobRequest, ',') as ServiceTypes
FROM RoMaster r
LEFT JOIN Vehicleinf v ON r.VINNO = v.VinNo
LEFT JOIN DealerRegister d ON r.DealerId = d.ID
WHERE r.VINNO IS NOT NULL AND r.VINNO != ''
GROUP BY r.VINNO, v.CustomerName, v.Model, v.Variant, d.DealerName
HAVING COUNT(*) >= {threshold}
ORDER BY RepairOrderCount DESC, TotalSpent DESC
LIMIT 50
""".strip()

    def _get_dealership_sales_vs_pdi_sql(self, params: Dict) -> str:
        """Dealerships with sales vs PDI completion comparison"""
        return """
SELECT
    d.DealerName as Dealership,
    d.DealerCode,
    COUNT(DISTINCT v.VinNo) as VehiclesSold,
    COUNT(DISTINCT p.VIN) as PDIsCompleted,
    ROUND(CAST(COUNT(DISTINCT p.VIN) AS FLOAT) * 100.0 / NULLIF(COUNT(DISTINCT v.VinNo), 0), 2) as PDICompletionRate,
    COUNT(DISTINCT v.VinNo) - COUNT(DISTINCT p.VIN) as MissingPDIs
FROM DealerRegister d
LEFT JOIN Vehicleinf v ON d.ID = v.DealerID
LEFT JOIN PDIMaster p ON v.VinNo = p.VIN AND CAST(v.DealerID AS VARCHAR(MAX)) = CAST(p.DealerID AS VARCHAR(MAX))
GROUP BY d.DealerName, d.DealerCode
HAVING COUNT(DISTINCT v.VinNo) > 0
ORDER BY PDICompletionRate ASC, VehiclesSold DESC
LIMIT 20
""".strip()

    def _get_warranty_percentage_by_month_sql(self, params: Dict) -> str:
        """Percentage breakdown of warranty claims by type for a month"""
        # Extract month/year from params or use current
        month = params.get('month', datetime.now().strftime('%m'))
        year = params.get('year', str(datetime.now().year))

        # Check for specific complaint types (e.g., "tyre")
        complaint_type = params.get('complaint_type', None)

        if complaint_type:
            # Specific type percentage
            return f"""
WITH MonthlyWarranty AS (
    SELECT
        COUNT(*) as TotalClaims,
        SUM(CASE WHEN LOWER(JobRequest) LIKE '%{complaint_type.lower()}%' THEN 1 ELSE 0 END) as SpecificClaims
    FROM RoMaster
    WHERE JobCatagories LIKE '%Warranty%'
      AND FORMAT(Date, 'yyyy-MM') = '{year}-{month}'
)
SELECT
    TotalClaims,
    SpecificClaims,
    ROUND(CAST(SpecificClaims AS FLOAT) * 100.0 / NULLIF(TotalClaims, 0), 2) as PercentageOfType,
    '{complaint_type}' as ClaimType,
    '{year}-{month}' as Period
FROM MonthlyWarranty
""".strip()
        else:
            # General breakdown
            return f"""
SELECT
    CASE
        WHEN LOWER(JobRequest) LIKE '%accident%' THEN 'Accident'
        WHEN LOWER(JobRequest) LIKE '%oil%' THEN 'Oil Related'
        WHEN LOWER(JobRequest) LIKE '%tyre%' OR LOWER(JobRequest) LIKE '%tire%' THEN 'Tyre Related'
        WHEN LOWER(JobRequest) LIKE '%engine%' THEN 'Engine Issues'
        WHEN LOWER(JobRequest) LIKE '%brake%' THEN 'Brake Issues'
        WHEN LOWER(JobRequest) LIKE '%transmission%' THEN 'Transmission Issues'
        WHEN LOWER(JobRequest) LIKE '%electrical%' OR LOWER(JobRequest) LIKE '%electric%' THEN 'Electrical Issues'
        ELSE 'Other'
    END as ClaimType,
    COUNT(*) as ClaimCount,
    ROUND(CAST(COUNT(*) AS FLOAT) * 100.0 / (SELECT COUNT(*) FROM RoMaster WHERE JobCatagories LIKE '%Warranty%' AND FORMAT(Date, 'yyyy-MM') = '{year}-{month}'), 2) as Percentage
FROM RoMaster
WHERE JobCatagories LIKE '%Warranty%'
  AND FORMAT(Date, 'yyyy-MM') = '{year}-{month}'
GROUP BY ClaimType
ORDER BY ClaimCount DESC
""".strip()

    def _get_monthly_summary_sql(self, params: Dict) -> str:
        """Monthly summary report"""
        month = params.get('month', datetime.now().strftime('%m'))
        year = params.get('year', str(datetime.now().year))

        return f"""
SELECT
    'Repair Orders' as Category,
    COUNT(*) as Count,
    SUM(TAmount) as Revenue
FROM RoMaster
WHERE FORMAT(Date, 'yyyy-MM') = '{year}-{month}'

UNION ALL

SELECT
    'PDI Inspections',
    COUNT(*),
    NULL
FROM PDIMaster
WHERE FORMAT(Date, 'yyyy-MM') = '{year}-{month}'

UNION ALL

SELECT
    'Campaigns',
    COUNT(*),
    NULL
FROM CampaignRpt
WHERE FORMAT(RDate, 'yyyy-MM') = '{year}-{month}'

UNION ALL

SELECT
    'FFS Services',
    COUNT(*),
    NULL
FROM FFSMaster
WHERE FORMAT(Date, 'yyyy-MM') = '{year}-{month}'
""".strip()

    def _get_dealership_most_repair_orders_sql(self, params: Dict) -> str:
        """Dealerships ranked by repair order count with robust date filtering"""
        # Extract date parameters
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)  # 'this_year', 'last_month', etc.

        # Build date filter - ONLY if explicitly requested
        date_filter = ""
        if year and month:
            # FIX: Convert month to int to avoid format string error
            month_int = int(month) if isinstance(month, str) else month
            date_filter = f"AND FORMAT(r.Date, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            date_filter = f"AND YEAR(r.Date) = '{year}'"
        elif period == 'this_year':
            date_filter = "AND YEAR(r.Date) = YEAR(GETDATE())"
        elif period == 'last_year':
            date_filter = "AND YEAR(r.Date) = YEAR(DATEADD(YEAR, -1, GETDATE()))"
        elif period == 'last_month':
            date_filter = "AND r.Date >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND r.Date < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        elif period == 'this_month':
            date_filter = "AND FORMAT(r.Date, 'yyyy-MM') = FORMAT(GETDATE(), 'yyyy-MM')"
        # If period is None or 'all_time', NO date filter

        return f"""
SELECT
    d.DealerName,
    d.DealerCode,
    COUNT(*) as TotalOrders,
    SUM(r.TAmount) as TotalRevenue,
    COUNT(DISTINCT r.VINNO) as UniqueVehicles,
    MIN(r.Date) as FirstOrder,
    MAX(r.Date) as LastOrder
FROM RoMaster r
LEFT JOIN DealerRegister d ON r.DealerId = d.ID
WHERE d.DealerName IS NOT NULL
  {date_filter}
GROUP BY d.DealerName, d.DealerCode
ORDER BY TotalOrders DESC
LIMIT 10
""".strip()

    def _get_dealership_most_warranty_complaints_sql(self, params: Dict) -> str:
        """Dealerships ranked by warranty complaint count"""
        # Extract date parameters
        year = params.get('year')
        month = params.get('month')

        date_filter = ""
        if year and month:
            # FIX: Convert month to int to avoid format string error
            month_int = int(month) if isinstance(month, str) else month
            date_filter = f"AND FORMAT(r.Date, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            date_filter = f"AND YEAR(r.Date) = '{year}'"

        return f"""
SELECT
    d.DealerName,
    d.DealerCode,
    COUNT(*) as ComplaintCount,
    SUM(r.TAmount) as TotalWarrantyCost,
    STRING_AGG(SUBSTRING(r.JobRequest, 1, 50), ',') as CommonIssues
FROM RoMaster r
LEFT JOIN DealerRegister d ON r.DealerId = d.ID
WHERE r.JobCatagories LIKE '%Warranty%'
  AND d.DealerName IS NOT NULL
  {date_filter}
GROUP BY d.DealerName, d.DealerCode
ORDER BY ComplaintCount DESC
LIMIT 10
""".strip()

    def _get_customers_by_spending_sql(self, params: Dict) -> str:
        """Customers ranked by total spending on repairs"""
        # Extract date parameters for optional filtering
        year = params.get('year')

        date_filter = ""
        if year:
            date_filter = f"AND YEAR(r.Date) = '{year}'"

        return f"""
SELECT
    r.CustomerName,
    COUNT(*) as RepairCount,
    SUM(r.TAmount) as TotalSpent,
    AVG(r.TAmount) as AvgSpentPerVisit,
    MIN(r.Date) as FirstVisit,
    MAX(r.Date) as LastVisit
FROM RoMaster r
WHERE r.CustomerName IS NOT NULL
  AND r.CustomerName != ''
  {date_filter}
GROUP BY r.CustomerName
ORDER BY TotalSpent DESC
LIMIT 10
""".strip()

    def _get_customers_frequent_visits_sql(self, params: Dict) -> str:
        """Customers ranked by repair visit frequency"""
        # Extract date parameters for optional filtering
        year = params.get('year')

        date_filter = ""
        if year:
            date_filter = f"AND YEAR(r.Date) = '{year}'"

        return f"""
SELECT
    r.CustomerName,
    COUNT(*) as VisitCount,
    STRING_AGG(r.RegistrationNo, ',') as Vehicles,
    STRING_AGG(r.Model, ',') as Models,
    SUM(r.TAmount) as TotalSpent,
    MIN(r.Date) as FirstVisit,
    MAX(r.Date) as LastVisit,
    ROUND((DATEDIFF(DAY, MIN(r.Date), MAX(r.Date))) / NULLIF(COUNT(*) - 1, 0), 1) as AvgDaysBetweenVisits
FROM RoMaster r
WHERE r.CustomerName IS NOT NULL
  AND r.CustomerName != ''
  {date_filter}
GROUP BY r.CustomerName
ORDER BY VisitCount DESC
LIMIT 10
""".strip()

    # COUNT SQL BUILDERS - For all major tables
    # ------------------------------------------

    def _build_date_filter(self, params: Dict) -> str:
        """Build date filter string with proper month int conversion (fixes format bug)"""
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)

        if year and month:
            # CRITICAL FIX: Convert month to int to avoid "Unknown format code 'd' for object of type 'str'" error
            month_int = int(month) if isinstance(month, str) else month
            return f"AND FORMAT(Date, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            return f"AND YEAR(Date) = '{year}'"
        elif period == 'this_year':
            return "AND YEAR(Date) = YEAR(GETDATE())"
        elif period == 'last_year':
            return "AND YEAR(Date) = YEAR(DATEADD(YEAR, -1, GETDATE()))"
        elif period == 'last_month':
            return "AND Date >= DATEADD(MONTH, -1, DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)) AND Date < DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)"
        elif period == 'this_month':
            return "AND FORMAT(Date, 'yyyy-MM') = FORMAT(GETDATE(), 'yyyy-MM')"
        # If period is 'all_time' or None, return empty (no filter)
        return ""

    def _get_count_repair_orders_sql(self, params: Dict) -> str:
        """Count total repair orders"""
        date_filter = self._build_date_filter(params)
        return f"""
SELECT COUNT(*) as TotalRepairOrders
FROM RoMaster
WHERE 1=1
  {date_filter}
""".strip()

    def _get_count_pdi_reports_sql(self, params: Dict) -> str:
        """Count total PDI reports"""
        date_filter = self._build_date_filter(params)
        return f"""
SELECT COUNT(*) as TotalPDIReports
FROM PDIMaster
WHERE 1=1
  {date_filter}
""".strip()

    def _get_count_ffs_inspections_sql(self, params: Dict) -> str:
        """Count total FFS inspections"""
        date_filter = self._build_date_filter(params)
        return f"""
SELECT COUNT(*) as TotalFFSInspections
FROM FFSMaster
WHERE 1=1
  {date_filter}
""".strip()

    def _get_count_sfs_inspections_sql(self, params: Dict) -> str:
        """Count total SFS inspections"""
        # SFSMaster uses ServiceDate, not Date
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)

        date_filter = ""
        if year and month:
            month_int = int(month) if isinstance(month, str) else month
            date_filter = f"AND FORMAT(ServiceDate, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            date_filter = f"AND YEAR(ServiceDate) = '{year}'"
        elif period == 'this_year':
            date_filter = "AND YEAR(ServiceDate) = YEAR(GETDATE())"
        elif period == 'last_year':
            date_filter = "AND YEAR(ServiceDate) = YEAR(DATEADD(YEAR, -1, GETDATE()))"

        return f"""
SELECT COUNT(*) as TotalSFSInspections
FROM SFSMaster
WHERE 1=1
  {date_filter}
""".strip()

    def _get_count_campaigns_sql(self, params: Dict) -> str:
        """Count total campaigns"""
        # CampaignRpt uses RDate, not Date
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)

        date_filter = ""
        if year and month:
            month_int = int(month) if isinstance(month, str) else month
            date_filter = f"AND FORMAT(RDate, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            date_filter = f"AND YEAR(RDate) = '{year}'"
        elif period == 'this_year':
            date_filter = "AND YEAR(RDate) = YEAR(GETDATE())"
        elif period == 'last_year':
            date_filter = "AND YEAR(RDate) = YEAR(DATEADD(YEAR, -1, GETDATE()))"

        return f"""
SELECT COUNT(*) as TotalCampaigns
FROM CampaignRpt
WHERE 1=1
  {date_filter}
""".strip()

    def _get_count_warranty_claims_sql(self, params: Dict) -> str:
        """Count total warranty claims"""
        date_filter = self._build_date_filter(params)
        return f"""
SELECT COUNT(*) as TotalWarrantyClaims
FROM RoMaster
WHERE JobCatagories LIKE '%Warranty%'
  {date_filter}
""".strip()

    def _get_count_csi_surveys_sql(self, params: Dict) -> str:
        """Count total CSI surveys"""
        # CSIMaster uses CurrentDateTime, not Date
        year = params.get('year')
        month = params.get('month')
        period = params.get('period', None)

        date_filter = ""
        if year and month:
            month_int = int(month) if isinstance(month, str) else month
            date_filter = f"AND FORMAT(CurrentDateTime, 'yyyy-MM') = '{year}-{month_int:02d}'"
        elif year:
            date_filter = f"AND YEAR(CurrentDateTime) = '{year}'"
        elif period == 'this_year':
            date_filter = "AND YEAR(CurrentDateTime) = YEAR(GETDATE())"

        return f"""
SELECT COUNT(*) as TotalCSISurveys
FROM CSIMaster
WHERE 1=1
  {date_filter}
""".strip()

    def _get_count_vehicles_sql(self, params: Dict) -> str:
        """Count total vehicles"""
        # Vehicleinf has Date column for delivery date
        date_filter = self._build_date_filter(params)
        return f"""
SELECT COUNT(*) as TotalVehicles
FROM Vehicleinf
WHERE 1=1
  {date_filter}
""".strip()

    def _inject_rls(self, sql: str) -> str:
        """Inject row-level security"""
        if not self.dealer_id:
            return sql

        # Add DealerId filter if not present
        if 'WHERE' in sql.upper() and 'DealerId' not in sql:
            # Insert after WHERE
            sql = sql.replace('WHERE', f"WHERE DealerId = '{self.dealer_id}' AND")
        elif 'GROUP BY' in sql.upper() and 'WHERE' not in sql.upper():
            # Insert before GROUP BY
            sql = sql.replace('GROUP BY', f"WHERE DealerId = '{self.dealer_id}'\nGROUP BY")

        return sql
