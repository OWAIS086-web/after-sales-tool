"""
Company Configuration Module

Centralized configuration for all supported automotive companies.
Each company has its own:
- PakWheels discussion thread URL
- ChromaDB database paths
- Data file paths (.pkl, .json)
- Background image
- Available data sources (PakWheels, WhatsApp, Insights)
- WATI API credentials (optional, for WhatsApp data fetching)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import os
from ai.dms_engine.db_adapter import DatabaseConfig  # For MSSQL support


@dataclass
class CompanyConfig:
    """Configuration for a single company"""

    # Company identification
    id: str  # Unique identifier (e.g., "haval", "kia", "toyota")
    name: str  # Display name (e.g., "Haval", "Kia", "Toyota")
    full_name: str  # Full company name (e.g., "Haval H6", "Kia Lucky Motors")

    # PakWheels configuration
    pakwheels_url: str  # Discussion thread URL
    pakwheels_thread_id: str  # Thread ID extracted from URL

    # Reddit configuration
    reddit_url: str  # Main Reddit subreddit or post URL

    # Database paths
    chroma_pakwheels_path: str  # Vector store for PakWheels data
    chroma_whatsapp_path: Optional[str]  # Vector store for WhatsApp data (None if unavailable)
    chroma_reddit_path: str  # Vector store for Reddit data
    pakwheels_blocks_file: str  # Pickle file for PakWheels conversation blocks
    whatsapp_blocks_file: Optional[str]  # Pickle file for WhatsApp conversation blocks
    reddit_blocks_file: str  # Pickle file for Reddit conversation blocks

    # Data file paths
    pakwheels_json_pattern: str  # Pattern for PakWheels JSON files (e.g., "featured_research__{thread_title}.json")
    whatsapp_json_path: Optional[str]  # WhatsApp data JSON file path

    # UI Configuration
    background_image: str  # Background image filename (e.g., "bk.jpg", "kia.jpg")
    primary_color: str  # Primary brand color (hex)

    # Lucid configuration (optional fields with defaults)
    lucid_url: Optional[str] = None  # Lucid forum base URL
    lucid_thread_id: Optional[str] = None  # Lucid thread ID extracted from URL
    chroma_lucid_path: Optional[str] = None  # Vector store for Lucid forum data
    lucid_blocks_file: Optional[str] = None  # Pickle file for Lucid conversation blocks
    chroma_reddit_lucid_path: Optional[str] = None  # Vector store for Reddit Lucid data
    reddit_lucid_blocks_file: Optional[str] = None  # Pickle file for Reddit Lucid conversation blocks

    # Data source availability (with defaults)
    has_pakwheels: bool = True  # PakWheels data available
    has_whatsapp: bool = True  # WhatsApp data available
    has_insights: bool = True  # Insights mode available (uses OpenAI)
    has_dms: bool = False  # Dealership Management System data available
    has_reddit: bool = True  # Reddit data available
    has_lucid: bool = False  # Lucid forum data available

    # WATI API Configuration (optional - for WhatsApp data fetching)
    wati_api_token: Optional[str] = None  # WATI API bearer token
    wati_tenant_id: Optional[str] = None  # WATI tenant ID
    wati_api_base: str = "https://live-mt-server.wati.io"  # WATI API base URL

    # DMS (Dealership Management System) Configuration
    dms_db_path: Optional[str] = None  # Path to DMS SQLite database (legacy)
    dms_db_config: Optional[DatabaseConfig] = None  # Database config (MSSQL or SQLite)
    dms_chroma_path: Optional[str] = None  # Path to DMS schema ChromaDB
    dms_dealer_id: Optional[str] = None  # Dealer ID for row-level security
    dms_type: Optional[str] = None  # DMS type: "production" (ai/dms_engine) or "dummy" (ai/dealership_engine)
    dms_data_source: str = "mssql"  # "sqlite" (old pipeline in ai/dms_engine_sqlite) or "mssql" (new pipeline in ai/dms_engine)

    # Enrichment Configuration
    variants: List[str] = None  # Vehicle variants/models for this company (e.g., ["PHEV", "HEV", "Jolion"])

    # Data Filtering Configuration (Scraping Only)
    min_year: Optional[int] = None  # Minimum year for NEW scraping (e.g., 2025) - only scrapes posts from this year onwards, does NOT filter existing database data

    # WATI/WhatsApp Data Filtering Configuration
    # Only process WhatsApp messages from this date onwards (ISO format: "2025-01-01")
    # This prevents old historical conversations from polluting the data
    wati_message_cutoff_date: Optional[str] = None

    def get_available_sources(self) -> List[str]:
        """Return list of available data sources for this company"""
        sources = []
        if self.has_pakwheels:
            sources.append("pakwheels")
        if self.has_whatsapp:
            sources.append("whatsapp")
        if self.has_insights:
            sources.append("insights")
        if self.has_dms:
            sources.append("dms")
        if self.has_reddit:
            sources.append("reddit")
        if self.has_lucid:
            sources.append("lucid")
        return sources
        

    def is_source_available(self, source: str) -> bool:
        """Check if a specific data source is available"""
        source_lower = source.lower()
        if source_lower == "pakwheels":
            return self.has_pakwheels
        elif source_lower == "whatsapp":
            return self.has_whatsapp
        elif source_lower == "reddit":
            return self.has_reddit
        elif source_lower == "lucid":
            return self.has_lucid
        elif source_lower == "insights":
            return self.has_insights
        elif source_lower == "dms" or source_lower == "dealership":
            return self.has_dms
        return False

    def has_wati_api(self) -> bool:
        """Check if company has WATI API credentials configured"""
        return self.wati_api_token is not None and self.wati_tenant_id is not None

    def get_all_pakwheels_urls(self) -> List[str]:
        """Get all PakWheels URLs configured for this company (pakwheels_url, pakwheels_url_1, pakwheels_url_2, etc.)"""
        urls = []

        # Add main URL if exists
        if hasattr(self, 'pakwheels_url') and self.pakwheels_url and self.pakwheels_url.strip():
            urls.append(self.pakwheels_url)

        # Look for numbered URLs (pakwheels_url_1, pakwheels_url_2, etc.)
        i = 1
        while True:
            attr_name = f'pakwheels_url_{i}'
            if hasattr(self, attr_name):
                url = getattr(self, attr_name)
                if url and url.strip():
                    urls.append(url)
                i += 1
            else:
                break

        return urls

    def get_all_reddit_urls(self) -> List[str]:
        """Get all Reddit URLs configured for this company (reddit_url, reddit_url_1, reddit_url_2, etc.)"""
        urls = []

        # Add main URL if exists
        if hasattr(self, 'reddit_url') and self.reddit_url and self.reddit_url.strip():
            urls.append(self.reddit_url)

        # Look for numbered URLs (reddit_url_1, reddit_url_2, etc.)
        i = 1
        while True:
            attr_name = f'reddit_url_{i}'
            if hasattr(self, attr_name):
                url = getattr(self, attr_name)
                if url and url.strip():
                    urls.append(url)
                i += 1
            else:
                break

        return urls


# Company Configurations
COMPANIES: Dict[str, CompanyConfig] = {
    "haval": CompanyConfig(
        id="haval",
        name="Haval",
        full_name="Haval H6",
        pakwheels_url="https://www.pakwheels.com/forums/t/haval-h6-dedicated-discussion-owner-fan-club-thread/2198325",
        pakwheels_thread_id="haval_h6_pakwheels",
        reddit_url="https://www.reddit.com/r/HavalTipsAndTricks/",
        lucid_url="https://lucidowners.com",
        lucid_thread_id="haval_lucid",
        chroma_pakwheels_path="data/chroma_pakwheels",
        chroma_whatsapp_path="data/chroma_whatsapp",
        chroma_reddit_path="data/chroma_reddit",
        chroma_lucid_path="data/chroma_lucid",
        pakwheels_blocks_file="data/pakwheels_blocks.pkl",
        whatsapp_blocks_file="data/whatsapp_blocks.pkl",
        reddit_blocks_file="data/reddit_blocks_haval.pkl",
        lucid_blocks_file="data/lucid_blocks.pkl",
        pakwheels_json_pattern="featured_research__Haval H6 Dedicated Discussion.json",
        whatsapp_json_path="data/all_messages.json",
        background_image="bk.jpg",
        primary_color="#C8102E",  # Haval red
        has_pakwheels=True,
        has_whatsapp=True,
        has_reddit=True,
        has_lucid=True,  # Lucid forum scraping enabled
        has_insights=True,
        has_dms=True,  # DMS data available for Haval
        # DMS Configuration
        # ⚠️ MIGRATION NOTE: After MSSQL migration, replace dms_db_path with dms_db_config
        # See DEPLOYMENT.md for full migration guide
        dms_db_path="data/SazgarDMSDW.sqlite",  # SQLite (current - for development)
        dms_chroma_path="data/chroma_dms_haval",  # Haval DMS schema vector store
        dms_dealer_id=None,  # No RLS filtering - show all dealers (change to integer like 14 to filter by dealer)
        dms_type="production",  # Uses ai/dms_engine (production-grade DMS with Tier 0/1/2/3)
        dms_data_source="mssql",  # "sqlite" = ai/dms_engine_sqlite (old prompts), "mssql" = ai/dms_engine (new prompts)

        # MSSQL Configuration (reads from .env file):
        dms_db_config=DatabaseConfig(
            provider=os.getenv("DMS_DB_PROVIDER", "mssql"),  # "mssql" or "sqlite"
            # MSSQL settings (production)
            mssql_server=os.getenv("DMS_MSSQL_SERVER", "localhost"),
            mssql_database=os.getenv("DMS_MSSQL_DATABASE", "SazgarDMSDW"),
            mssql_username=os.getenv("DMS_MSSQL_USERNAME", "haval_app_user"),
            mssql_password=os.getenv("DMS_MSSQL_PASSWORD"),  # Never hardcode passwords!
            mssql_port=int(os.getenv("DMS_MSSQL_PORT", "1433")),
            mssql_trusted_connection=os.getenv("DMS_MSSQL_TRUSTED_CONNECTION", "true").lower() == "true",  # Windows Auth for local
            # SQLite settings (fallback/development)
            sqlite_path="data/SazgarDMSDW.sqlite"
        ),
        # WATI API credentials for WhatsApp data fetching
        wati_api_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1bmlxdWVfbmFtZSI6ImFsaS5pcWJhbEBzYXpnYXJhdXRvcy5jb20iLCJuYW1laWQiOiJhbGkuaXFiYWxAc2F6Z2FyYXV0b3MuY29tIiwiZW1haWwiOiJhbGkuaXFiYWxAc2F6Z2FyYXV0b3MuY29tIiwiYXV0aF90aW1lIjoiMDUvMjEvMjAyNSAxNDoxODo0MyIsInRlbmFudF9pZCI6IjEwNDgyMiIsImp0aSI6IjdhMDVkODUwLTQ2ZGItNGRlYS04NmNhLTIzNzUzNzA2ZDRjNCIsImRiX25hbWUiOiJtdC1wcm9kLVRlbmFudHMiLCJodHRwOi8vc2NoZW1hcy5taWNyb3NvZnQuY29tL3dzLzIwMDgvMDYvaWRlbnRpdHkvY2xhaW1zL3JvbGUiOiJBRE1JTklTVFJBVE9SIiwiZXhwIjoyNTM0MDIzMDA4MDAsImlzcyI6IkNsYXJlX0FJIiwiYXVkIjoiQ2xhcmVfQUkifQ.X01JY-X9Y-Y0NvWx02nzVys4T-_Dk-l0rlqxFAJ82dI",
        wati_tenant_id="104822",
        wati_api_base="https://live-mt-server.wati.io",
        # Vehicle variants/models for enrichment
        variants=["H6", "PHEV", "HEV", "ICE", "Jolion", "H9", "Dargo", "Unknown"],
        # Data filtering - only scrape/process data from 2025 onwards
        min_year=2025,  # Only scrape PakWheels posts from 2025 onwards
        # WATI/WhatsApp data filtering - only process messages from Jan 1, 2025 onwards
        wati_message_cutoff_date="2025-01-01",
    )
    ,

    "kia": CompanyConfig(
        id="kia",
        name="Kia",
        full_name="Kia Lucky Motors Pakistan",
        pakwheels_url="https://www.pakwheels.com/forums/t/kia-lucky-motors-pakistan-discussion-thread-grand-carnival-rio-picanto-sportage-cerato/825345",
        pakwheels_thread_id="kia_lucky_motors_pakwheels",
        reddit_url="https://www.reddit.com/r/PakistanAutoHub/",
        lucid_url=None,  # No Lucid forum for Kia
        lucid_thread_id=None,
        chroma_pakwheels_path="data/chroma_pakwheels_kia",
        chroma_whatsapp_path="data/chroma_whatsapp_kia",  # No WhatsApp data for Kia
        chroma_reddit_path="data/chroma_reddit_kia",
        chroma_lucid_path=None,
        pakwheels_blocks_file="data/pakwheels_blocks_kia.pkl",
        whatsapp_blocks_file="data/whatsapp_blocks_kia.pkl",
        reddit_blocks_file="data/reddit_blocks_kia.pkl",
        lucid_blocks_file=None,
        pakwheels_json_pattern="featured_research__Kia Lucky Motors Pakistan.json",
        whatsapp_json_path=None,
        background_image="kia.jpg",
        primary_color="#BB162B",  # Kia red
        has_pakwheels=True,
        has_whatsapp=True,  # Dummy whatsapp
        has_reddit=True,
        has_lucid=False,
        has_insights=True,
        has_dms=True,  # Dummy DMS data available for Kia
        # DMS Configuration (Dummy Dealership Database)
        dms_db_path="data/dealership_kia.db",  # Kia dummy dealership database
        dms_chroma_path=None,  # Not used for dummy dealership
        dms_dealer_id=None,  # Not used for dummy dealership
        dms_type="dummy",  # Uses ai/dealership_engine (dummy dealership pipeline)
        dms_data_source="sqlite",  # SQLite for dummy database (not MSSQL)
        # Vehicle variants/models for enrichment
        variants = [
    "Sportage",   # Available in Pakistan
    "Stonic",     # Available in Pakistan
    "Picanto",    # Available in Pakistan
    "Sorento",    # Available in Pakistan
    "Carnival",   # Available in Pakistan
    "Rio",        # Not available in Pakistan
    "Cerato",     # Not available in Pakistan
    "Unknown"     # Invalid model
],
        # Data filtering - only scrape NEW posts from 2025+ (existing data remains accessible)
        min_year=2025,  # Only scrape posts from 2025+ when doing NEW Reddit/PakWheels scraping (existing 2017-2024 data remains in database)
    ),

    "toyota": CompanyConfig(
        id="toyota",
        name="Toyota",
        full_name="Toyota Indus Pakistan",
        pakwheels_url="",  # TODO: Add Toyota PakWheels URL when available
        pakwheels_thread_id="toyota_pakwheels",
        reddit_url="https://www.reddit.com/r/PakistanAutoHub/",
        lucid_url=None,  # No Lucid forum for Toyota
        lucid_thread_id=None,
        chroma_pakwheels_path="data/chroma_pakwheels_toyota",
        chroma_whatsapp_path=None,
        chroma_reddit_path="data/chroma_reddit_toyota",
        chroma_lucid_path=None,
        pakwheels_blocks_file="data/pakwheels_blocks_toyota.pkl",
        whatsapp_blocks_file=None,
        reddit_blocks_file="data/reddit_blocks_toyota.pkl",
        lucid_blocks_file=None,
        pakwheels_json_pattern="featured_research__Toyota.json",
        whatsapp_json_path=None,
        background_image="bk.jpg",  # Use default until Toyota image is added
        primary_color="#EB0A1E",  # Toyota red
        has_pakwheels=False,  # Not yet configured
        has_whatsapp=False,
        has_reddit=True,
        has_lucid=False,
        has_insights=True,
        has_dms=False,  # No DMS data available for Toyota yet
        # Vehicle variants/models for enrichment
        variants = [
    "Yaris",          # Available in Pakistan 🇵🇰 (Toyota Yaris sedan) :contentReference[oaicite:0]{index=0}
    "Corolla",        # Available in Pakistan 🇵🇰 (Toyota Corolla) :contentReference[oaicite:1]{index=1}
    "Corolla Cross",  # Available in Pakistan 🇵🇰 (Toyota Corolla Cross crossover) :contentReference[oaicite:2]{index=2}
    "Hilux",          # Available in Pakistan 🇵🇰 (Toyota Hilux pickup) :contentReference[oaicite:3]{index=3}
    "Fortuner",       # Available in Pakistan 🇵🇰 (Toyota Fortuner SUV) :contentReference[oaicite:4]{index=4}
    "Hiace",          # Available in Pakistan 🇵🇰 (Toyota Hiace van/commuter) :contentReference[oaicite:5]{index=5}
    "Coaster",        # Available in Pakistan 🇵🇰 (Toyota Coaster minibus) :contentReference[oaicite:6]{index=6}
    "Prado",          # Available in Pakistan 🇵🇰 (Toyota Prado SUV) :contentReference[oaicite:7]{index=7}
    "Land Cruiser",   # Available in Pakistan 🇵🇰 (Toyota Land Cruiser SUV) :contentReference[oaicite:8]{index=8}
    "Camry",          # Available in Pakistan 🇵🇰 (Toyota Camry sedan) :contentReference[oaicite:9]{index=9}
    "Unknown"         # Invalid / unspecified model
],
        # Data filtering - show all historical data for Toyota
        min_year=None,  # No year filter - scrape all posts regardless of date
    ),
    "lucid": CompanyConfig(
        id="lucid",
        name="Lucid",
        full_name="Lucid Motors",
        pakwheels_url=None,  # No PakWheels for Lucid
        pakwheels_thread_id=None,
        reddit_url="https://www.reddit.com/r/lucidmotors/",  # Lucid Motors subreddit
        lucid_url="https://lucidowners.com",
        lucid_thread_id="lucid_owners",
        chroma_pakwheels_path=None,
        chroma_whatsapp_path=None,
        chroma_reddit_path="data/chroma_reddit_lucid",  # Separate Reddit vector store for Lucid
        chroma_lucid_path="data/chroma_lucid",
        chroma_reddit_lucid_path="data/chroma_reddit_lucid",  # Reddit Lucid vector store
        pakwheels_blocks_file=None,
        whatsapp_blocks_file=None,
        reddit_blocks_file="data/reddit_blocks_lucid.pkl",  # Separate Reddit blocks file for Lucid
        reddit_lucid_blocks_file="data/reddit_blocks_lucid.pkl",  # Reddit Lucid blocks file (same as reddit_blocks_file)
        lucid_blocks_file="data/lucid_blocks.pkl",
        pakwheels_json_pattern=None,
        whatsapp_json_path=None,
        background_image="bk.jpg",
        primary_color="#0066CC",  # Lucid blue
        has_pakwheels=False,
        has_whatsapp=False,
        has_reddit=True,  # Reddit data available for Lucid
        has_lucid=True,  # Lucid forum is the primary data source
        has_insights=True,
        has_dms=True,  # No DMS for Lucid
        dms_db_path="data/lucid_dms_demo.db",
        dms_chroma_path="data/chroma_dms_lucid",
        dms_dealer_id=None,
        dms_type="production",
        dms_data_source="sqlite",
        dms_db_config=DatabaseConfig(
            provider="sqlite",
            sqlite_path="data/lucid_dms_demo.db"
        ),
        # Vehicle variants/models for enrichment
        variants=[
            "Air",
            "Gravity",
            "Sapphire",
            "Sedan",
            "SUV",
            "Unknown"
        ],
        # Data filtering
        min_year=None,
    ),
}

# Add additional PakWheels URLs dynamically (for multi-URL scraping support)
COMPANIES["kia"].pakwheels_url_1 = "https://www.pakwheels.com/forums/t/5th-generation-kia-sportage-nq5-discussion-thread/2861699"
COMPANIES["kia"].pakwheels_url_2 = "https://www.pakwheels.com/forums/t/kia-sorento-dedicated-discussion-owner-fan-club-thread/1647607"
COMPANIES["kia"].pakwheels_url_3 = "https://www.pakwheels.com/forums/t/kia-sportage-ql-dedicated-discussion-owner-fan-club-thread/1119279"
COMPANIES["kia"].pakwheels_url_4 = "https://www.pakwheels.com/forums/t/kia-sportage-l-hev-carplay-wont-connect-fixed-by-updating-firmware-from-kia/3018032"
COMPANIES["kia"].pakwheels_url_5 = "https://www.pakwheels.com/forums/t/kia-picanto-dedicated-discussion-owner-fan-club-thread/1130026"

# Add Haval URLs (example - add your actual URLs here)
COMPANIES["haval"].pakwheels_url_1 = "https://www.pakwheels.com/forums/t/haval-jolion-dedicated-discussion-owner-fan-club-thread/2156716"
COMPANIES["haval"].pakwheels_url_2 = "https://www.pakwheels.com/forums/t/choosing-between-changan-oshan-x7-future-sense-and-haval-h6/3015547"
COMPANIES["haval"].pakwheels_url_3 = "https://www.pakwheels.com/forums/t/the-ev-thread-fully-electric-vehicles-exclusive-discussion/1533817"


# Add additional Reddit URLs dynamically (for multi-URL scraping support)
# Haval Reddit URLs - using the default URLs from reddit.txt
COMPANIES["haval"].reddit_url_1 = "https://www.reddit.com/r/PakistanAutoHub/"
COMPANIES["haval"].reddit_url_2 = "https://www.reddit.com/r/HavalTipsAndTricks/"

# Kia Reddit URLs - you can add more specific Kia subreddits here
# COMPANIES["kia"].reddit_url_1 = "https://www.reddit.com/r/kia/"
# COMPANIES["kia"].reddit_url_2 = "https://www.reddit.com/r/KiaEV6/"

# Toyota Reddit URLs - you can add more specific Toyota subreddits here
# COMPANIES["toyota"].reddit_url_1 = "https://www.reddit.com/r/Toyota/"
# COMPANIES["toyota"].reddit_url_2 = "https://www.reddit.com/r/Corolla/"

# Lucid Reddit URLs - Lucid Motors subreddits
COMPANIES["lucid"].reddit_url_1 = "https://www.reddit.com/r/lucidmotors/"
COMPANIES["lucid"].reddit_url_2 = "https://www.reddit.com/r/LUCID/"

# Default company (Haval)
DEFAULT_COMPANY = "haval"


def get_company_config(company_id: str) -> CompanyConfig:
    """
    Get configuration for a specific company.

    Args:
        company_id: Company identifier (e.g., "haval", "kia", "toyota")

    Returns:
        CompanyConfig object

    Raises:
        ValueError: If company_id is not recognized
    """
    if company_id not in COMPANIES:
        raise ValueError(f"Unknown company: {company_id}. Available: {list(COMPANIES.keys())}")
    return COMPANIES[company_id]


def get_all_companies() -> Dict[str, CompanyConfig]:
    """Get all company configurations"""
    return COMPANIES.copy()


def get_enabled_companies() -> Dict[str, CompanyConfig]:
    """Get only companies that have at least one data source configured"""
    return {
        company_id: config
        for company_id, config in COMPANIES.items()
        if config.has_pakwheels or config.has_whatsapp or config.has_reddit or config.has_lucid
    }


def is_company_enabled(company_id: str) -> bool:
    """Check if a company is enabled (has at least one data source)"""
    try:
        config = get_company_config(company_id)
        return config.has_pakwheels or config.has_whatsapp or config.has_reddit
    except ValueError:
        return False


def get_company_display_name(company_id: str) -> str:
    """Get the display name for a company"""
    try:
        return get_company_config(company_id).name
    except ValueError:
        return "Unknown"