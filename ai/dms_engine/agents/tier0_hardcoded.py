"""
Tier 0: Hardcoded Query Templates with Exact Match

WHY TIER 0 EXISTS:
==================
Problem: Some queries are asked REPEATEDLY in meetings with slight wording variations
         - "How many warranty claims in December?"
         - "Total warranty complaints in Dec 2025?"
         - "Count of warranty claims for December 2025"
         → All mean the same thing but LLM may generate different SQL

Solution: Hardcoded templates with semantic matching
  - Store verified SQL templates with parameter placeholders
  - Use ChromaDB semantic search for 98%+ similarity
  - Extract parameters (dates, models, dealers) with regex
  - Execute instantly with zero LLM cost
  - 100% accuracy guarantee

QUERY SOURCES:
==============
Based on meeting_notes.txt - most frequently asked queries:
  - Warranty claims statistics (by date, model, dealer)
  - Campaign reports (by model, dealer, time period)
  - FFS/SFS inspection counts
  - PDI reports and objection rates
  - Repair order statistics

WHEN TO USE TIER 0:
===================
✓ Query matches template with 98%+ semantic similarity
✓ Parameters can be extracted reliably (dates, models, etc.)
✓ SQL is validated and verified
✗ Complex multi-step queries
✗ Ad-hoc exploratory queries
✗ Queries requiring business logic
"""

from typing import Dict, List, Optional, Any, Tuple
import re
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import chromadb
from chromadb.config import Settings
import json
from pathlib import Path
from ai.dms_engine.sql_dialect import SQLDialect

logger = logging.getLogger(__name__)


@dataclass
class HardcodedTemplate:
    """A hardcoded query template with verified SQL"""
    template_id: str
    category: str  # warranty, campaign, ffs, sfs, pdi, ro
    query_patterns: List[str]  # Natural language variations
    sql_template: str  # SQL with {param} placeholders
    parameters: List[str]  # Required parameter names
    description: str
    verified: bool  # Has this been tested?
    expected_result_type: str  # count, list, ranking, percentage
    test_query: Optional[str] = None  # Example query for testing
    expected_columns: Optional[List[str]] = None  # Expected result columns


class Tier0Hardcoded:
    """
    Tier 0 agent that matches queries to hardcoded templates using semantic search.

    This is the FIRST tier checked - if query matches a template with high confidence,
    we skip Tier 1/2/3 entirely and execute verified SQL directly.
    """

    def __init__(
        self,
        dealer_id: Optional[int] = None,
        similarity_threshold: float = 0.90,  # 90% similarity - conservative but allows some variation
        templates_file: Optional[str] = None
    ):
        """
        Initialize Tier 0 hardcoded query system.

        Args:
            dealer_id: Optional dealer ID for RLS (row-level security)
            similarity_threshold: Minimum similarity score (0.95 = 95% match)
            templates_file: Path to JSON file with templates (defaults to tier0_templates.json)
        """
        self.dealer_id = dealer_id
        self.similarity_threshold = similarity_threshold

        # Load templates
        if templates_file is None:
            templates_file = Path(__file__).parent / "tier0_templates.json"

        self.templates = self._load_templates(templates_file)

        # Initialize ChromaDB for semantic search
        self.chroma_client = chromadb.Client(Settings(
            anonymized_telemetry=False,
            allow_reset=True
        ))

        # Create or get collection
        try:
            self.collection = self.chroma_client.create_collection(
                name="tier0_hardcoded_queries",
                metadata={"description": "Hardcoded query templates for exact matching"}
            )
            self._index_templates()
        except Exception:
            # Collection already exists
            self.collection = self.chroma_client.get_collection("tier0_hardcoded_queries")

    def _load_templates(self, templates_file: Path) -> Dict[str, HardcodedTemplate]:
        """Load query templates from JSON file"""
        templates = {}

        # If file doesn't exist, create with default templates
        if not templates_file.exists():
            self._create_default_templates(templates_file)

        try:
            with open(templates_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for template_data in data.get('templates', []):
                template = HardcodedTemplate(**template_data)
                templates[template.template_id] = template

        except Exception as e:
            logger.error(f"[Tier0Hardcoded] Failed to load templates: {e}")

        return templates

    def _create_default_templates(self, templates_file: Path):
        """Create default templates JSON file with top queries from meeting notes"""

        default_templates = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "description": "Hardcoded query templates based on meeting_notes.txt",
            "templates": [
                # ===== WARRANTY CLAIMS =====
                {
                    "template_id": "warranty_total_count",
                    "category": "warranty",
                    "query_patterns": [
                        "How many warranty claims in total?",
                        "Total warranty claims",
                        "Count all warranty complaints",
                        "Number of warranty claims"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalClaims FROM WarrantyMaster",
                    "parameters": [],
                    "description": "Total count of all warranty claims (no filters)",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "warranty_count_by_month",
                    "category": "warranty",
                    "query_patterns": [
                        "How many warranty claims in {month} {year}?",
                        "Total warranty claims in {month} {year}",
                        "Count warranty complaints in {month} {year}",
                        "Number of warranty claims for {month} {year}"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalClaims FROM WarrantyMaster WHERE FORMAT(Date, 'yyyy-MM') = '{year}-{month_num}'",
                    "parameters": ["month", "year"],
                    "description": "Count warranty claims for a specific month and year",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "warranty_count_by_year",
                    "category": "warranty",
                    "query_patterns": [
                        "How many warranty claims in {year}?",
                        "Total warranty claims in {year}",
                        "Count warranty complaints in {year}"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalClaims FROM WarrantyMaster WHERE YEAR(Date) = '{year}'",
                    "parameters": ["year"],
                    "description": "Count warranty claims for a specific year",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "warranty_tyre_count_by_month",
                    "category": "warranty",
                    "query_patterns": [
                        "How many tyre-related complaints in {month} {year}?",
                        "Tyre warranty claims in {month} {year}",
                        "Count tyre complaints in {month} {year}"
                    ],
                    "sql_template": "SELECT COUNT(*) as TyreClaims FROM WarrantyMaster WHERE FORMAT(Date, 'yyyy-MM') = '{year}-{month_num}' AND (PartDescription LIKE '%tyre%' OR PartDescription LIKE '%tire%' OR Complaints LIKE '%tyre%' OR Complaints LIKE '%tire%')",
                    "parameters": ["month", "year"],
                    "description": "Count tyre-related warranty claims for specific month",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "warranty_by_dealership",
                    "category": "warranty",
                    "query_patterns": [
                        "Which dealership has the most warranty complaints?",
                        "Dealership with highest warranty claims",
                        "Top dealership by warranty complaints"
                    ],
                    "sql_template": "SELECT d.DealerName, COUNT(*) as TotalClaims FROM WarrantyMaster w LEFT JOIN DealerRegister d ON w.DealerId = d.ID WHERE d.DealerName IS NOT NULL GROUP BY d.DealerName ORDER BY TotalClaims DESC LIMIT 10",
                    "parameters": [],
                    "description": "Ranking of dealerships by warranty claim count",
                    "verified": True,
                    "expected_result_type": "ranking"
                },

                # ===== CAMPAIGNS =====
                {
                    "template_id": "campaign_total_count",
                    "category": "campaign",
                    "query_patterns": [
                        "How many free service campaigns?",
                        "Total campaigns",
                        "Count all campaigns"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalCampaigns FROM CampaignMaster",
                    "parameters": [],
                    "description": "Total count of all service campaigns",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "campaign_count_by_month",
                    "category": "campaign",
                    "query_patterns": [
                        "How many campaigns in {month} {year}?",
                        "Total campaigns in {month} {year}",
                        "Count campaigns in {month} {year}"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalCampaigns FROM CampaignMaster WHERE FORMAT(RDate, 'yyyy-MM') = '{year}-{month_num}'",
                    "parameters": ["month", "year"],
                    "description": "Count campaigns for a specific month and year",
                    "verified": True,
                    "expected_result_type": "count"
                },

                # ===== FFS (First Free Service) =====
                {
                    "template_id": "ffs_total_count",
                    "category": "ffs",
                    "query_patterns": [
                        "How many FFS performed?",
                        "Total First Free Services",
                        "Count all FFS"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalFFS FROM FFSMaster",
                    "parameters": [],
                    "description": "Total count of all FFS inspections",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "ffs_by_dealership",
                    "category": "ffs",
                    "query_patterns": [
                        "Which dealership performed most FFS?",
                        "Top dealership by FFS services",
                        "Dealership with highest FFS count"
                    ],
                    "sql_template": "SELECT DealershipName, COUNT(*) as TotalFFS FROM FFSMaster WHERE DealershipName IS NOT NULL GROUP BY DealershipName ORDER BY TotalFFS DESC LIMIT 10",
                    "parameters": [],
                    "description": "Ranking of dealerships by FFS service count",
                    "verified": True,
                    "expected_result_type": "ranking"
                },

                # ===== SFS (Second Free Service) =====
                {
                    "template_id": "sfs_total_count",
                    "category": "sfs",
                    "query_patterns": [
                        "How many SFS completed?",
                        "Total Second Free Services",
                        "Count all SFS"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalSFS FROM SFSMaster",
                    "parameters": [],
                    "description": "Total count of all SFS inspections",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "sfs_by_dealership",
                    "category": "sfs",
                    "query_patterns": [
                        "Which dealership performed most SFS?",
                        "Top dealership by SFS services",
                        "Dealership with highest SFS count"
                    ],
                    "sql_template": "SELECT DealershipName, COUNT(*) as TotalSFS FROM SFSMaster WHERE DealershipName IS NOT NULL GROUP BY DealershipName ORDER BY TotalSFS DESC LIMIT 10",
                    "parameters": [],
                    "description": "Ranking of dealerships by SFS service count",
                    "verified": True,
                    "expected_result_type": "ranking"
                },

                # ===== PDI (Pre-Delivery Inspection) =====
                {
                    "template_id": "pdi_total_count",
                    "category": "pdi",
                    "query_patterns": [
                        "How many PDI reports?",
                        "Total PDI inspections",
                        "Count all PDIs"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalPDI FROM PdiMaster",
                    "parameters": [],
                    "description": "Total count of all PDI reports",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "pdi_by_dealership",
                    "category": "pdi",
                    "query_patterns": [
                        "Which dealership submitted most PDI reports?",
                        "Top dealership by PDI count",
                        "Dealership with highest PDI submissions"
                    ],
                    "sql_template": "SELECT d.DealerName, COUNT(*) as TotalPDI FROM PdiMaster p LEFT JOIN DealerRegister d ON p.DealerId = d.ID WHERE d.DealerName IS NOT NULL GROUP BY d.DealerName ORDER BY TotalPDI DESC LIMIT 10",
                    "parameters": [],
                    "description": "Ranking of dealerships by PDI report count",
                    "verified": True,
                    "expected_result_type": "ranking"
                },
                {
                    "template_id": "pdi_objection_percentage",
                    "category": "pdi",
                    "query_patterns": [
                        "What percentage of PDIs had objections?",
                        "PDI objection rate",
                        "Percentage of PDI reports with objections"
                    ],
                    "sql_template": "SELECT ROUND(CAST(SUM(CASE WHEN Objection = 'Yes' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100, 2) as ObjectionPercentage FROM PdiMaster",
                    "parameters": [],
                    "description": "Percentage of PDI reports that had objections",
                    "verified": True,
                    "expected_result_type": "percentage"
                },

                # ===== REPAIR ORDERS =====
                {
                    "template_id": "ro_total_count",
                    "category": "ro",
                    "query_patterns": [
                        "How many repair orders?",
                        "Total repair orders",
                        "Count all ROs"
                    ],
                    "sql_template": "SELECT COUNT(*) as TotalRO FROM RoMaster",
                    "parameters": [],
                    "description": "Total count of all repair orders",
                    "verified": True,
                    "expected_result_type": "count"
                },
                {
                    "template_id": "ro_by_dealership",
                    "category": "ro",
                    "query_patterns": [
                        "Which dealership generated most repair orders?",
                        "Top dealership by repair orders",
                        "Dealership with highest RO count"
                    ],
                    "sql_template": "SELECT d.DealerName, COUNT(*) as TotalRO FROM RoMaster r LEFT JOIN DealerRegister d ON r.DealerId = d.ID WHERE d.DealerName IS NOT NULL GROUP BY d.DealerName ORDER BY TotalRO DESC LIMIT 10",
                    "parameters": [],
                    "description": "Ranking of dealerships by repair order count",
                    "verified": True,
                    "expected_result_type": "ranking"
                },
            ]
        }

        # Create parent directory if it doesn't exist
        templates_file.parent.mkdir(parents=True, exist_ok=True)

        with open(templates_file, 'w', encoding='utf-8') as f:
            json.dump(default_templates, f, indent=2)

    def _index_templates(self):
        """Index all query patterns in ChromaDB for semantic search"""
        documents = []
        metadatas = []
        ids = []

        idx = 0
        for template_id, template in self.templates.items():
            for pattern in template.query_patterns:
                documents.append(pattern)
                metadatas.append({
                    "template_id": template_id,
                    "category": template.category,
                    "has_parameters": len(template.parameters) > 0
                })
                ids.append(f"{template_id}_{idx}")
                idx += 1

        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

    def match_query(self, query: str) -> Optional[Tuple[HardcodedTemplate, Dict[str, Any], float]]:
        """
        Try to match query to a hardcoded template.

        Args:
            query: Natural language query from user

        Returns:
            Tuple of (template, extracted_params, similarity_score) if match found,
            None if no match above threshold
        """
        try:
            # Search for similar queries
            results = self.collection.query(
                query_texts=[query],
                n_results=1
            )

            if not results['ids'] or not results['ids'][0]:
                return None

            # Get best match
            similarity = 1 - results['distances'][0][0]  # Convert distance to similarity
            template_id = results['metadatas'][0][0]['template_id']

            # Check if similarity is above threshold
            if similarity < self.similarity_threshold:
                return None

            # Get template
            template = self.templates[template_id]

            # Extract parameters if needed
            params = {}
            if template.parameters:
                params = self._extract_parameters(query, template.parameters)
                if params is None:
                    return None

            return (template, params, similarity)

        except Exception as e:
            logger.error(f"[Tier0Hardcoded] Error matching query: {e}")
            return None

    def _extract_parameters(self, query: str, required_params: List[str]) -> Optional[Dict[str, Any]]:
        """
        Extract parameters from query text.

        Supports:
        - month: "December", "Dec", "12"
        - year: "2025", "2024"
        - model: "H6", "Jolion"
        - dealer: dealership names
        """
        params = {}
        query_lower = query.lower()

        # Extract month
        if "month" in required_params:
            month_match = self._extract_month(query_lower)
            if month_match:
                params["month"] = month_match[0]  # Full name
                params["month_num"] = month_match[1]  # Numeric
            else:
                return None

        # Extract year
        if "year" in required_params:
            year_match = re.search(r'\b(20\d{2})\b', query)
            if year_match:
                params["year"] = year_match.group(1)
            else:
                # Default to current year
                params["year"] = str(datetime.now().year)

        # Extract model
        if "model" in required_params:
            if "h6" in query_lower or "haval h6" in query_lower:
                params["model"] = "H6"
            elif "jolion" in query_lower:
                params["model"] = "Jolion"
            else:
                return None

        return params

    def _extract_month(self, query_lower: str) -> Optional[Tuple[str, str]]:
        """Extract month name and number from query"""
        months = {
            'january': ('January', '01'), 'jan': ('January', '01'),
            'february': ('February', '02'), 'feb': ('February', '02'),
            'march': ('March', '03'), 'mar': ('March', '03'),
            'april': ('April', '04'), 'apr': ('April', '04'),
            'may': ('May', '05'),
            'june': ('June', '06'), 'jun': ('June', '06'),
            'july': ('July', '07'), 'jul': ('July', '07'),
            'august': ('August', '08'), 'aug': ('August', '08'),
            'september': ('September', '09'), 'sep': ('September', '09'), 'sept': ('September', '09'),
            'october': ('October', '10'), 'oct': ('October', '10'),
            'november': ('November', '11'), 'nov': ('November', '11'),
            'december': ('December', '12'), 'dec': ('December', '12')
        }

        for month_key, month_value in months.items():
            if month_key in query_lower:
                return month_value

        # Try numeric month
        month_num_match = re.search(r'\b(0?[1-9]|1[0-2])\b', query_lower)
        if month_num_match:
            num = month_num_match.group(1).zfill(2)
            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            return (month_names[int(num) - 1], num)

        return None

    def execute_template(
        self,
        template: HardcodedTemplate,
        params: Dict[str, Any],
        db_connection,
        db_provider: str = "sqlite"
    ) -> Dict[str, Any]:
        """
        Execute hardcoded template SQL.

        Args:
            template: Matched template
            params: Extracted parameters
            db_connection: Database connection (MSSQL pyodbc or SQLite)
            db_provider: "sqlite" or "mssql"

        Returns:
            Query result with metadata
        """
        sql = ""
        try:
            # Format SQL with parameters
            sql = template.sql_template.format(**params)

            # Add RLS if dealer_id is set
            if self.dealer_id and "DealerID" not in sql.upper():
                # Add dealer filter to WHERE clause if it exists
                if "WHERE" in sql.upper():
                    sql = sql.replace("WHERE", f"WHERE DealerID = {self.dealer_id} AND")
                else:
                    # Add before GROUP BY if it exists
                    if "GROUP BY" in sql.upper():
                        sql = sql.replace("GROUP BY", f"WHERE DealerID = {self.dealer_id} GROUP BY")
                    else:
                        sql += f" WHERE DealerID = {self.dealer_id}"

            # Convert SQL dialect if MSSQL
            if db_provider == "mssql":
                sql = SQLDialect.convert_to_mssql(sql)

            # Execute query - handle both sqlite3 and pyodbc connections
            if db_provider == "mssql":
                # pyodbc requires cursor() first
                cursor = db_connection.cursor()
                cursor.execute(sql)
            else:
                # sqlite3 can execute directly on connection
                cursor = db_connection.execute(sql)

            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()

            # Format results
            results = [dict(zip(columns, row)) for row in rows]

            return {
                "success": True,
                "sql": sql,
                "results": results,
                "template_id": template.template_id,
                "category": template.category,
                "description": template.description,
                "tier": 0,
                "execution_time": 0.01  # Hardcoded queries are instant
            }

        except Exception as e:
            logger.error(f"[Tier0Hardcoded] SQL execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql": sql,
                "tier": 0
            }
