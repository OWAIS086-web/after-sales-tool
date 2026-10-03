# ai/rag_engine/regex_classifiers.py
"""
Regex-Based Pre-Classification Module v2.0

Fast-path optimization for simple classification tasks that don't need LLM.
Comprehensive support for:
- Domain Classification (IN_DOMAIN, OUT_OF_DOMAIN, SMALL_TALK)
- Intent Classification (META_OP, STANDALONE, CONTEXT_DEPENDENT, TOPIC_SWITCH)
- Multilingual support (English + Roman Urdu/Pakistani slang)
- Typo tolerance for common misspellings
- Robust negative lookaheads to prevent false positives

Strategy:
1. Try regex first (instant, 0 tokens)
2. Fall back to LLM only if regex returns None (ambiguous cases)

Coverage Targets:
- Domain Classification: ~80% hit rate (saves ~110 tokens/query)
- Intent Classification: ~70% hit rate (saves ~500 tokens/query)

Total potential savings: ~450 tokens/query average
"""

import re
import os
import yaml
from typing import Optional, Tuple, Dict, List
from enum import Enum
from dataclasses import dataclass


# =============================================================================
# CONFIGURATION LOADER
# =============================================================================

def load_regex_config() -> dict:
    """
    Load regex classifier configuration from config/regex_config.yml

    Returns default configuration if file not found.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config",
        "regex_config.yml"
    )

    # Default configuration (all enabled)
    default_config = {
        "domain_classification": {
            "enabled": True,
            "small_talk": {"enabled": True},
            "in_domain": {"enabled": True},
            "out_of_domain": {"enabled": True}
        },
        "intent_classification": {
            "enabled": True,
            "meta_op": {"enabled": True},
            "standalone": {"enabled": True},
            "context_dependent": {"enabled": True},
            "topic_switch": {"enabled": True}
        },
        "advanced": {
            "typo_matching": {"enabled": True},
            "urdu_support": {"enabled": True},
            "negative_lookahead": {"enabled": True},
            "track_stats": {"enabled": True}
        }
    }

    # Try to load from file
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config if config else default_config
    except Exception as e:
        pass
        # print(f"[RegexConfig] Warning: Could not load config from {config_path}: {e}")
        print(f"[RegexConfig] Using default configuration (all enabled)")

    return default_config


# Load configuration on module import
REGEX_CONFIG = load_regex_config()


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class DomainClass(Enum):
    IN_DOMAIN = "in_domain"
    OUT_OF_DOMAIN = "out_of_domain"
    SMALL_TALK = "small_talk"


class IntentClass(Enum):
    META_OP = "META_OP"
    STANDALONE = "STANDALONE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    TOPIC_SWITCH = "TOPIC_SWITCH"


# =============================================================================
# PATTERN COLLECTIONS - Centralized for easy maintenance
# =============================================================================

@dataclass
class PatternConfig:
    """Configuration for all regex patterns - easy to extend"""
    
    # -------------------------------------------------------------------------
    # CAR BRANDS with typo variants
    # -------------------------------------------------------------------------
    CAR_BRANDS: Dict[str, List[str]] = None
    
    # -------------------------------------------------------------------------
    # CAR MODELS with typo variants
    # -------------------------------------------------------------------------
    CAR_MODELS: Dict[str, List[str]] = None
    
    # -------------------------------------------------------------------------
    # URDU/ROMAN URDU AUTOMOTIVE TERMS
    # -------------------------------------------------------------------------
    URDU_AUTOMOTIVE_TERMS: List[str] = None
    
    def __post_init__(self):
        # Car brands with common typos/variants
        self.CAR_BRANDS = {
            # Primary brand -> [variants/typos]
            'haval': ['havel', 'havall', 'hawall', 'hawl', 'havl', 'haaval', 'haavl'],
            'gwm': ['gwm', 'g.w.m', 'g w m', 'greatwall', 'great wall', 'great-wall'],
            'sazgar': ['sazgaar', 'sazger', 'sazgr'],
            'jolion': ['jolon', 'jolian', 'julion', 'jolin', 'jolyon', 'joleon'],
            'tank': ['tank300', 'tank500', 'tank-300', 'tank-500', 'tank 300', 'tank 500'],
            'kia': ['kiya', 'kya', 'kiaa'],
            'toyota': ['toyata', 'toyoto', 'toyta', 'tuyota'],
            'honda': ['hondaa', 'hnda', 'honada'],
            'suzuki': ['suziki', 'suzku', 'suzki', 'susuki'],
            'hyundai': ['hundai', 'hyundia', 'hundayi', 'hyundi', 'huyndai'],
            'nissan': ['nisan', 'nissaan'],
            'mazda': ['masda', 'mazada'],
            'mg': ['m.g', 'm g', 'morris garages'],
            'changan': ['changaan', 'changa', 'changn'],
            'proton': ['protoon', 'protn'],
            'dfsk': ['dfsk', 'd.f.s.k', 'glory'],
            'faw': ['f.a.w', 'faw motors'],
            'chery': ['cherry', 'cheri', 'chry'],
            'baic': ['baic', 'b.a.i.c'],
            'prince': ['princ', 'prins'],
            'united': ['unitd', 'unted'],
        }
        
        # Car models with common typos/variants
        self.CAR_MODELS = {
            # Haval/GWM models
            'h6': ['h-6', 'h 6', 'hh6', 'haval h6', 'h6 hev'],
            'jolion': ['jolon', 'jolian', 'julion', 'jolin', 'haval jolion'],
            'tank 300': ['tank300', 'tank-300', 'tnk300', 'tnk 300'],
            'tank 500': ['tank500', 'tank-500', 'tnk500', 'tnk 500'],
            'poer': ['powr', 'por', 'gwm poer'],
            'cannon': ['canon', 'cannn'],
            
            # Kia models
            'picanto': ['pikanto', 'pekanto', 'piccanto', 'picnto', 'picantu'],
            'sportage': ['sportag', 'spoortage', 'sportaje', 'sprtage', 'sportege'],
            'sorento': ['sorrento', 'soranto', 'sornto'],
            'stonic': ['stonc', 'stonick', 'stonik'],
            'carnival': ['carnval', 'carnaval', 'carnivl'],
            'seltos': ['sltos', 'seltose'],
            
            # Toyota models
            'corolla': ['carola', 'crolla', 'corlla', 'corrola', 'corola'],
            'yaris': ['yares', 'yars', 'yaaris'],
            'fortuner': ['fortunr', 'fortner', 'fortuneer', 'fortnr'],
            'hilux': ['hylux', 'hilx', 'hi-lux'],
            'prado': ['pradoo', 'prdo'],
            'land cruiser': ['landcruiser', 'land-cruiser', 'lc', 'land cruzer'],
            'revo': ['revoo', 'rvo'],
            'camry': ['camri', 'camree'],
            
            # Honda models
            'civic': ['civec', 'civik', 'cvic', 'cvc'],
            'city': ['citi', 'cityy'],
            'accord': ['accrd', 'acord'],
            'br-v': ['brv', 'br v', 'b r v'],
            'hr-v': ['hrv', 'hr v', 'h r v'],
            'cr-v': ['crv', 'cr v', 'c r v'],
            'vezel': ['vezal', 'vesl'],
            
            # Suzuki models
            'alto': ['aalto', 'altu'],
            'swift': ['swft', 'swiift'],
            'cultus': ['kultus', 'clts', 'cults'],
            'wagon r': ['wagonr', 'wagon-r', 'wagn r', 'vxr'],
            'vitara': ['vitara', 'vitarra', 'vitra'],
            'jimny': ['jimni', 'jimney', 'jmny'],
            'bolan': ['bolan', 'boln'],
            'mehran': ['mehren', 'mhran'],
            
            # Hyundai models
            'tucson': ['tuscon', 'tucsn', 'tucsen'],
            'elantra': ['elantara', 'elentra', 'elntra'],
            'sonata': ['sonta', 'sonnata'],
            'santa fe': ['santafe', 'santa-fe', 'sntafe'],
            'creta': ['creta', 'crta'],
        }
        
        # Urdu/Roman Urdu automotive terms (Pakistani slang)
        self.URDU_AUTOMOTIVE_TERMS = [
            # Vehicle terms
            'gaadi', 'gadi', 'gari', 'gaari', 'gaaddi',  # car
            'motor', 'motaar', 'motar',  # motor/vehicle
            'sawari', 'sawwari',  # ride/vehicle
            
            # Money/Price terms
            'paisa', 'paise', 'paisay', 'pesa', 'pesay',  # money
            'qeemat', 'qimat', 'kimat', 'keemat',  # price
            'rate', 'reit',  # rate
            'lakh', 'lac', 'laakh',  # 100,000
            'crore', 'karor', 'crror',  # 10,000,000
            'rupay', 'rupees', 'rupiya', 'rupaiya',  # rupees
            # 'mehnga', 'mehenga', 'mehanga',  # expensive - too generic without car context
            # 'sasta', 'ssti',  # cheap - too generic without car context
            'kiraya', 'kiraaya',  # rent/fare
            'booking', 'buking',  # booking
            'down payment', 'downpayment', 'dp',  # down payment
            'qist', 'qast', 'installment',  # installment
            
            # Location terms
            'showroom', 'shoroom', 'shorum',
            'dealership', 'dealer', 'dealar',
            'service center', 'service centre', 'servicing',
            'workshop', 'wrkshop',
            
            # Action terms
            'khareedna', 'kharidna', 'khreedna',  # to buy
            'bechna', 'bechana',  # to sell
            'dekhna', 'dekho', 'dikhao', 'dikhana',  # to see/show
            'chalana', 'chalna',  # to drive
            'lena', 'lo', 'lelo',  # to take
            'dena', 'de do', 'dedo',  # to give
            
            # Quality/Condition terms
            'acha', 'achchha', 'achi', 'achhi',  # good
            'bura', 'buri', 'kharab',  # bad
            'naya', 'nayi', 'new',  # new
            'purana', 'purani', 'old',  # old
            'first hand', 'first owner',
            'second hand', 'used',
            
            # Parts (Urdu)
            'tyre', 'tire', 'tayer',
            'pati', 'patii',  # belt
            'tel', 'oil',  # oil
            'brake', 'break', 'braik',
            'gear', 'giar',
            'steering', 'steerin', 'stering',
            'bonnet', 'bonat',
            'dikki', 'dicky',  # trunk
            'silencer', 'silencer', 'silncer',
            'battery', 'batery', 'batri',
            
            # Common queries
            'kitna', 'kitni', 'kitne',  # how much/many
            'kab', 'kb',  # when
            'kahan', 'kha', 'khn',  # where
            'kaisa', 'kaisi', 'kaise',  # how/what like
            'konsa', 'konsi', 'kon',  # which
            'milega', 'milegi', 'milenge',  # will get
            'chahiye', 'chaiye', 'chaye',  # need/want
            'batao', 'btao', 'batayen',  # tell
            'available', 'availble', 'avlbl',
            
            # WhatsApp/Chat terms (Urdu context)
            'baat', 'baat cheet', 'baatcheet',  # conversation
            'jawab', 'jawwab', 'javab',  # answer/reply
            'sawal', 'sawaal',  # question
            'shikayat', 'shikayet', 'complaint',  # complaint
        ]


# Initialize pattern config
PATTERNS = PatternConfig()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def normalize_query(query: str) -> str:
    """
    Normalize query for consistent matching.
    - Lowercase
    - Remove extra whitespace
    - Basic punctuation normalization
    """
    q = query.lower().strip()
    # Collapse multiple spaces
    q = re.sub(r'\s+', ' ', q)
    # Remove trailing punctuation for cleaner matching
    q = re.sub(r'[\.\!\?]+$', '', q)
    return q


def build_typo_pattern(word: str, variants: List[str] = None) -> str:
    """Build regex pattern that matches word and all its typo variants."""
    all_forms = [re.escape(word)]
    if variants:
        all_forms.extend([re.escape(v) for v in variants])
    return r'\b(' + '|'.join(all_forms) + r')\b'


def get_all_brand_patterns() -> List[str]:
    """Generate regex patterns for all car brands including typos."""
    patterns = []
    for brand, variants in PATTERNS.CAR_BRANDS.items():
        patterns.append(build_typo_pattern(brand, variants))
    return patterns


def get_all_model_patterns() -> List[str]:
    """Generate regex patterns for all car models including typos."""
    patterns = []
    for model, variants in PATTERNS.CAR_MODELS.items():
        patterns.append(build_typo_pattern(model, variants))
    return patterns


# =============================================================================
# DOMAIN CLASSIFICATION - Main Function
# =============================================================================

def classify_query_domain_regex(
    question: str,
    company_id: str = "haval",
    mode: str = "auto"  # "auto", "pakwheels", "whatsapp"
) -> Optional[str]:
    """
    Fast regex-based domain classification for OBVIOUS cases.

    Returns:
        'in_domain' - Clearly about automotive/company topics
        'out_of_domain' - Clearly unrelated (with negative lookahead protection)
        'small_talk' - Greetings/thanks/chitchat
        None - Ambiguous, needs LLM

    Args:
        question: User query
        company_id: Company context (haval, kia, etc.)
        mode: Operating mode (pakwheels, whatsapp, auto)

    Coverage: ~80% of queries (based on typical usage)
    Savings: ~110 tokens per hit
    """
    # =========================================================================
    # CONFIGURATION CHECK
    # =========================================================================
    domain_config = REGEX_CONFIG.get("domain_classification", {})
    if not domain_config.get("enabled", True):
        # Domain classification disabled - always use LLM
        return None

    q_lower = normalize_query(question)
    original_lower = question.lower().strip()  # Keep for case-sensitive checks

    # =========================================================================
    # PHASE 1: SMALL TALK (Highest priority - most obvious)
    # =========================================================================

    # Check if small_talk classification is enabled
    if domain_config.get("small_talk", {}).get("enabled", True):
        small_talk_result = _check_small_talk(q_lower)
        if small_talk_result:
            return small_talk_result

    # =========================================================================
    # PHASE 2: EXPLICIT IN-DOMAIN CHECKS (Before out-of-domain to prevent FPs)
    # =========================================================================

    # Check if in_domain classification is enabled
    if domain_config.get("in_domain", {}).get("enabled", True):
        # Check for explicit automotive indicators
        if _is_explicit_automotive(q_lower, company_id, mode):
            return DomainClass.IN_DOMAIN.value

    # =========================================================================
    # PHASE 3: OUT OF DOMAIN (With safeguards)
    # =========================================================================

    # Check if out_of_domain classification is enabled
    if domain_config.get("out_of_domain", {}).get("enabled", True):
        # Only check out_of_domain if NO automotive indicators found
        if _is_clearly_out_of_domain(q_lower):
            return DomainClass.OUT_OF_DOMAIN.value

    # =========================================================================
    # PHASE 4: AMBIGUOUS - Let LLM decide
    # =========================================================================
    return None


def _check_small_talk(q_lower: str) -> Optional[str]:
    """Check for small talk patterns - greetings, thanks, etc."""
    
    small_talk_patterns = [
        # === GREETINGS ===
        # English greetings
        r'^(hi|hello|hey|hiya|howdy|greetings|hola)[\s\.\!\?]*$',
        r'^good\s*(morning|afternoon|evening|night|day)[\s\.\!\?]*$',
        r'^(yo|sup|whats up|what\'s up)[\s\.\!\?]*$',
        
        # Urdu/Arabic greetings
        r'^(salam|assalam|salaam|asalaam|asalam|as?salamu?\s*(o\s*)?alaikum|aoa|slm)[\s\.\!\?]*$',
        r'^(walaikum|w[a]?alaikum)[\s\.\!\?]*$',
        r'^(ji|jee|g|haan|han)[\s\.\!\?]*$',  # Urdu affirmatives
        r'^(adaab|aadab)[\s\.\!\?]*$',
        
        # === THANKS ===
        r'^(thanks?|thank\s*you|thx|ty|tysm|thnx|thanx)[\s\.\!\?]*$',
        r'^(thanks?|thank\s*you)\s*(so|very)?\s*(much|a lot)?[\s\.\!\?]*$',
        r'^(shukriya|shukria|meharbani|bohot\s*shukriya)[\s\.\!\?]*$',
        
        # === HOW ARE YOU ===
        r'^how\s*(are|r)\s*(you|u|ya)[\s\.\!\?]*$',
        r'^how\'?s\s*it\s*going[\s\.\!\?]*$',
        r'^how\s*(do\s*you\s*do|have\s*you\s*been)[\s\.\!\?]*$',
        r'^(kya|kia|kese|kaise|kaisa)\s*(ho|hai|haal|chal)[\s\.\!\?]*$',  # Urdu: how are you
        r'^(theek|thik|tek)\s*(ho|hai)?[\s\.\!\?]*$',  # Urdu: are you okay
        
        # === GOODBYE ===
        r'^(bye|goodbye|good\s*bye|see\s*(you|ya|u)|farewell|later|cya|bbye)[\s\.\!\?]*$',
        r'^(allah\s*hafiz|khuda\s*hafiz|allahhafiz|khudahafiz|take\s*care)[\s\.\!\?]*$',
        r'^(phir\s*milte\s*hain|milte\s*hain)[\s\.\!\?]*$',  # Urdu: see you later
        
        # === POLITE FILLERS ===
        r'^(ok|okay|k|oky|alright|sure|fine|cool|great|nice|good|perfect)[\s\.\!\?]*$',
        r'^(hmm+|umm+|ah+|oh+|acha+|achha+|haan|ji)[\s\.\!\?]*$',
        r'^(no\s*problem|np|nw|no\s*worries)[\s\.\!\?]*$',
        r'^(you\'?re\s*welcome|welcome|yw)[\s\.\!\?]*$',
        
        # === ACKNOWLEDGMENTS ===
        r'^(got\s*it|understood|i\s*see|makes\s*sense|noted)[\s\.\!\?]*$',
        r'^(samajh\s*gaya|samajh\s*gayi|samjha|pata\s*chal\s*gaya)[\s\.\!\?]*$',  # Urdu: understood
    ]
    
    for pattern in small_talk_patterns:
        if re.match(pattern, q_lower, re.IGNORECASE):
            return DomainClass.SMALL_TALK.value
    
    return None


def _is_explicit_automotive(q_lower: str, company_id: str, mode: str) -> bool:
    """
    Check for explicit automotive/platform indicators.
    Returns True if query is DEFINITELY about cars/dealership/platform.
    """
    
    # -------------------------------------------------------------------------
    # 1. CAR BRAND DETECTION (with typo tolerance)
    # -------------------------------------------------------------------------
    for pattern in get_all_brand_patterns():
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    # Add dynamic company_id check
    if company_id and re.search(rf'\b{re.escape(company_id.lower())}\b', q_lower):
        return True
    
    # -------------------------------------------------------------------------
    # 2. CAR MODEL DETECTION (with typo tolerance)
    # -------------------------------------------------------------------------
    for pattern in get_all_model_patterns():
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    # -------------------------------------------------------------------------
    # 3. URDU AUTOMOTIVE TERMS
    # -------------------------------------------------------------------------
    for term in PATTERNS.URDU_AUTOMOTIVE_TERMS:
        if re.search(rf'\b{re.escape(term)}\b', q_lower, re.IGNORECASE):
            return True
    
    # -------------------------------------------------------------------------
    # 4. EXPLICIT AUTOMOTIVE KEYWORDS
    # -------------------------------------------------------------------------
    automotive_keywords = [
        # Vehicle parts
        r'\b(engine|motor|transmission|gearbox|clutch|brake[s]?|suspension)\b',
        r'\b(shock\s*absorber|tire[s]?|tyre[s]?|wheel[s]?|axle|rim[s]?)\b',
        r'\b(radiator|battery|alternator|starter|carbur[e]?tor|exhaust)\b',
        r'\b(fuel\s*tank|oil\s*filter|air\s*filter|spark\s*plug|piston)\b',
        r'\b(windshield|windscreen|wiper[s]?|headlight[s]?|taillight[s]?)\b',
        r'\b(bumper|fender|hood|bonnet|trunk|boot|dikki|dicky)\b',
        r'\b(steering|dashboard|dash|speedometer|odometer)\b',
        r'\b(seat[s]?|airbag[s]?|seatbelt|belt[s]?)\b',
        
        # Vehicle features
        r'\b(sunroof|panoramic\s*roof|moonroof|cruise\s*control)\b',
        r'\b(abs|anti.?lock|airbag[s]?|traction\s*control|esc|esp)\b',
        r'\b(parking\s*sensor[s]?|rear\s*camera|reverse\s*camera|backup\s*cam)\b',
        r'\b(navigation|nav\s*system|gps|infotainment|touchscreen)\b',
        r'\b(keyless|push\s*start|remote\s*start|smart\s*key)\b',
        r'\b(bluetooth|carplay|android\s*auto|usb|aux)\b',
        r'\b(leather\s*seats?|heated\s*seats?|ventilated\s*seats?)\b',
        
        # Transmission/Powertrain
        r'\b(automatic|manual|cvt|dct|amt|imt|hybrid|electric|ev|phev)\b',
        r'\b(turbo|turbocharged|supercharged|aspirated|cc|litre|liter)\b',
        r'\b(horsepower|hp|bhp|torque|nm|power|acceleration)\b',
        r'\b(2wd|4wd|4x4|awd|fwd|rwd|all\s*wheel\s*drive)\b',
        
        # Vehicle types
        r'\b(sedan|suv|crossover|hatchback|pickup|truck|van|minivan)\b',
        r'\b(coupe|convertible|wagon|estate|mpv|cuv)\b',
        
        # Performance/Economy
        r'\b(mileage|fuel\s*economy|kmpl|km/?l|mpg|l/100km)\b',
        r'\b(top\s*speed|acceleration|0.?60|0.?100)\b',
        r'\b(ground\s*clearance|wheelbase|dimensions)\b',
        
        # Service/Ownership - REQUIRE automotive context to avoid false positives
        # Only match these if combined with car-related terms
        # r'\b(warranty|warranties|service|maintenance|repair|spare\s*parts?)\b',  # Too broad - moved below
        r'\b(car|vehicle|gadi|gaadi|motor)\s*(warranty|service|maintenance|repair)\b',
        r'\b(warranty|service|maintenance|repair)\s*(of|for|on)\s*(the\s*)?(car|vehicle|gadi|gaadi)\b',
        r'\b(dealership|dealer|showroom|test\s*drive)\b',
        r'\b(booking|booked|book|delivery|deliveries)\b',
        r'\b(registration|reg|number\s*plate)\b',  # Removed 'insurance' - too generic
        r'\b(resale|trade.?in|exchange)\s*(value|price)?\b',
        r'\b(emi|installment|down\s*payment|financing|loan|leasing)\s*(for\s*)?(car|vehicle|gadi)?\b',
        
        # Price queries with automotive context
        r'\b(on\s*road\s*price|ex.?showroom|otr|otd)\b',
        r'\b(base\s*model|top\s*model|variant[s]?|trim[s]?|version[s]?)\b',
        
        # Common issues/problems - REQUIRE automotive context
        # "problem/issue" alone is too generic (e.g., "any issues?")
        # Only match if combined with car terms
        r'\b(brake|engine|transmission|suspension|steering|tire|tyre)\s*(problem[s]?|issue[s]?|fault[s]?)\b',
        r'\b(problem[s]?|issue[s]?|complaint[s]?|defect[s]?|fault[s]?)\s*(with|in|on)\s*(the\s*)?(car|vehicle|engine|brake)\b',
        r'\b(breakdown|overheating|noise|vibration|leak|rust|dent)\b',
        r'\b(recall|tsb|technical\s*service\s*bulletin)\b',
    ]
    
    for pattern in automotive_keywords:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    # -------------------------------------------------------------------------
    # 5. PLATFORM-SPECIFIC TERMS
    # -------------------------------------------------------------------------
    platform_patterns = [
        r'\b(pakwheels?|pak\s*wheels?|pw)\b',
        r'\b(olx|carmudi|autotrader)\b',
        r'\b(whatsapp|whats\s*app|wa)\b',
        r'\b(lucid|lucid\s*owners?|lucidowners?)\b',
        r'\b(customer\s*service|support|helpline|contact)\b',
    ]
    
    for pattern in platform_patterns:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    # -------------------------------------------------------------------------
    # 6. WHATSAPP MODE SPECIFIC QUERIES
    # -------------------------------------------------------------------------
    whatsapp_patterns = [
        # Customer/conversation queries
        r'\b(show|get|pull|find)\s*(me\s*)?(the\s*)?(conversation|chat|messages?)\b',
        r'\b(conversation|chat|messages?)\s*(of|with|from)\s*\w+\b',
        r"\b\w+['\u2019]s\s*(conversation|chat|messages?|feedback|complaint)\b",
        r'\b(what\s*did|show\s*what)\s*\w+\s*(say|said|ask|asked|tell|told|write|wrote)\b',
        
        # Simple "show [Name] conversation" pattern (name before keyword)
        r'\bshow\s+[A-Za-z]+\s*(conversation|chat|messages?)\b',
        
        # Reporting/Analytics queries
        r'\b(queries|conversations?|messages?|chats?)\s*(reported|sent|received|on)\b',
        r'\b(on|dated?)\s*\d{1,2}(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
        r'\b(in|during|from|since)\s*(20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|last\s*(week|month|year))\b',
        # Time references - REQUIRE automotive/whatsapp context
        # Don't match standalone "yesterday" (e.g., "who won yesterday?")
        r'\b(queries|conversations?|messages?|chats?|customers?|bookings?|deliveries)\s+.*(yesterday|today|this\s*(week|month|year)|last\s*(week|month|year))\b',
        r'\b(yesterday|today|this\s*(week|month|year)|last\s*(week|month|year))\s*.*(queries|conversations?|messages?|chats?|customers?|bookings?|deliveries)\b',
        
        # Sentiment queries
        r'\b(angry|dissatisfied|satisfied|happy|unhappy|frustrated)\s*(customer[s]?|user[s]?)?\b',
        r'\b(customer|user)\s*(sentiment|feedback|satisfaction)\b',
        r'\b(positive|negative)\s*(feedback|reviews?|sentiment)\b',
        
        # Price/Quote queries - require "quoted/given/offered" context
        r'\b(prices?|quotes?|quotations?)\s*(being\s*)?(quoted|given|provided|offered)\b',
        r'\bwhat\s+(are|is)\s+(the\s*)?(prices?|costs?|rates?)\s+(being\s+)?(quoted|given|offered)\b',
        r'\b(prices?|rates?)\s+(quoted|being\s+quoted)\b',
        r'^what\s+(prices?|costs?|rates?)\s+(are\s+)?(being\s+)?(quoted|given)\b',
        r'\b(prices?|costs?|rates?)\s+(to|for)\s+(customers?|clients?)\b',
        
        # Report generation - REQUIRE clear whatsapp/customer context
        # Don't match generic "create a report" - only match WhatsApp reporting queries
        # Must mention customers, queries, conversations, or whatsapp explicitly
        r'\b(queries|conversations?|messages?|chats?|customers?|feedback)\s+.*\b(report|summary|presentation)\b',
        r'\b(report|summary|presentation)\s+.*\b(queries|conversations?|customers?|feedback)\b',
        r'\b(sales|marketing)\s*(team|manager).*\b(customer|query|conversation|whatsapp)\b',
    ]
    
    for pattern in whatsapp_patterns:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    # -------------------------------------------------------------------------
    # 7. FORUM MODE SPECIFIC QUERIES
    # -------------------------------------------------------------------------
    forum_patterns = [
        # Discussion queries
        r'\b(common|main|popular|trending)\s*(discussion[s]?|topic[s]?|issue[s]?|problem[s]?)\b',
        r'\b(discussion[s]?|post[s]?|thread[s]?|forum)\s*(on|about|in)\b',
        r'\bhow\s*do\s*(people|owners?|users?|customers?)\s*(compare|think|feel|rate|review)\b',
        r'\b(user|owner|customer)\s*(reviews?|opinions?|feedback|experiences?)\b',
        
        # Comparison queries
        r'\b(compare|comparison|vs|versus|better|best|which\s*one)\b',
        r'\b(difference[s]?\s*between|pros?\s*and\s*cons?)\b',
        
        # Review/Rating queries
        r'\b(reviews?|ratings?|rated)\s*(of|for|about)?\b',
        r'\b(real\s*world|actual|owner)\s*(experience[s]?|review[s]?|feedback)\b',
    ]
    
    for pattern in forum_patterns:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    # -------------------------------------------------------------------------
    # 8. PRICE QUERIES WITH CONTEXT
    # -------------------------------------------------------------------------
    # Only match price if combined with car-related term OR in clear automotive context
    # IMPORTANT: Avoid matching generic price queries like "price of bread"
    price_patterns = [
        # Price + car/vehicle term
        r'\b(price|cost|rate|kitna|kitni)\s+(of|for)?\s*(the\s*)?(car|gadi|gaadi|vehicle|model)\b',
        r'\b(car|gadi|gaadi|vehicle|model)\s*(price|cost|rate|kitna|kitni)\b',
        # Price + specific brand/model (these are always automotive)
        r'\b(price|cost|rate)\s+(of|for)?\s*(the\s*)?(haval|jolion|h6|tank|kia|toyota|honda|suzuki|picanto|sportage|corolla|civic)\b',
        r'\b(haval|jolion|h6|tank|kia|toyota|honda|suzuki|picanto|sportage|corolla|civic)\s*(ki|ka|ke)?\s*(price|cost|rate|qeemat|kimat)\b',
        # "how much" + car term
        r'\b(how\s*much|kitna|kitne)\s+(is|does|for)?\s*(the\s*)?(car|gadi|gaadi|vehicle)\b',
        r'\b(how\s*much|kitna|kitne)\s+(is|does|for)?\s*(the\s*)?(haval|jolion|h6|tank|picanto|sportage)\b',
    ]
    
    for pattern in price_patterns:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    return False


def _is_clearly_out_of_domain(q_lower: str) -> bool:
    """
    Check for CLEARLY out-of-domain queries.
    Uses NEGATIVE LOOKAHEADS to prevent false positives.
    Only returns True if absolutely certain it's not automotive-related.
    """
    
    # -------------------------------------------------------------------------
    # NEGATIVE LOOKAHEAD SAFEGUARDS
    # These terms, if present, prevent out_of_domain classification
    # -------------------------------------------------------------------------
    automotive_safeguard_pattern = (
        r'\b(car|vehicle|auto|motor|engine|transmission|brake|'
        r'tire|tyre|wheel|fuel|mileage|warranty|service|repair|'
        r'dealership|dealer|showroom|booking|delivery|'
        r'haval|gwm|kia|toyota|honda|suzuki|hyundai|nissan|'
        r'jolion|h6|tank|picanto|sportage|corolla|civic|'
        r'pakwheels|whatsapp|customer|gadi|gaadi|gaari)\b'
    )
    
    # If ANY automotive term is found, do NOT mark as out_of_domain
    if re.search(automotive_safeguard_pattern, q_lower, re.IGNORECASE):
        return False
    
    # -------------------------------------------------------------------------
    # OUT OF DOMAIN PATTERNS
    # -------------------------------------------------------------------------
    out_of_domain_patterns = [
        # === ACADEMIC/EDUCATIONAL ===
        r'\b(write|compose)\s*(an?\s*)?(essay|thesis|dissertation|paper|report)\s*(on|about)\s*(?!.*(car|vehicle|auto))',
        r'\b(help|assist)\s*(me\s*)?(with\s*)?(my\s*)?(homework|assignment|coursework)',
        r'\b(solve|calculate|compute)\s*(this\s*)?(math|algebra|calculus|equation)',
        r'\b(explain|describe)\s*(the\s*)?(theory|concept)\s*of\s*(?!.*(engine|motor))',
        
        # === ENTERTAINMENT (without automotive context) ===
        r'\b(what|which|recommend)\s*(movie|film|series|show|drama|anime)\s*(should|to|can)\s*i\s*watch',
        r'\b(who\s*won|result\s*of|score\s*of)\s*(the\s*)?(match|game|tournament|championship)',
        r'\b(football|cricket|basketball|tennis|hockey)\s*(score|match|game|player)',
        r'\b(download|stream|watch)\s*(movie|song|video|music)',
        
        # === COOKING/FOOD (without vehicle context) ===
        r'\b(recipe\s*for|how\s*to\s*cook|how\s*to\s*make|how\s*to\s*bake)\b(?!.*(car|vehicle))',
        r'\b(ingredient[s]?\s*for|cooking\s*time|baking\s*instructions)',
        r'\b(biryani|nihari|karahi|pulao|kebab)\s*(recipe|banane)',
        
        # === GENERAL KNOWLEDGE (non-automotive) ===
        r'\bwho\s*(is|was)\s*the\s*(president|prime\s*minister|king|queen)\s*of',
        r'\bwhat\s*is\s*the\s*(capital|population|area)\s*of',
        r'\b(history|geography|science)\s*of\s*(?!.*(car|auto|vehicle))',
        
        # === WEATHER (unless driving context) ===
        r'\b(what\'?s|what\s*is)\s*the\s*weather\s*(in|at|for)\b(?!.*(drive|driving|road))',
        r'\bwill\s*it\s*(rain|snow)\s*(today|tomorrow|this\s*week)\b(?!.*(drive|driving))',
        
        # === HEALTH/MEDICAL (unless vehicle injury) ===
        r'\b(symptoms?\s*of|treatment\s*for|medicine\s*for)\s*(cold|flu|fever|headache|diabetes)',
        r'\b(doctor|hospital|clinic)\s*(for|near|recommendation)',
        r'\b(health|medical|fitness)\s*(advice|tips|routine)',
        
        # === PROGRAMMING (unless automotive software) ===
        r'\b(python|javascript|java|c\+\+|html|css)\s*(code|program|function|error)',
        r'\b(debug|fix|solve)\s*(my|this|the)\s*(code|program|script|bug)',
        r'\b(how\s*to\s*code|learn\s*programming|coding\s*tutorial)',
        
        # === TRAVEL (unless road trip) ===
        r'\b(flight|airplane|train|railway)\s*(to|from|booking|ticket)',
        r'\b(hotel|resort|airbnb)\s*(in|at|near|booking)',
        r'\b(vacation|holiday)\s*(to|in)\s*(?!.*(road\s*trip|drive))',
        
        # === RELATIONSHIP/PERSONAL ===
        r'\b(relationship|dating|marriage)\s*(advice|tips|help)',
        r'\b(boyfriend|girlfriend|husband|wife)\s*(problem|issue)',
        
        # === PHILOSOPHICAL/SPIRITUAL (non-vehicle) ===
        r'\b(meaning\s*of\s*life|purpose\s*of\s*existence|afterlife)',
        r'\b(meditation|yoga|spirituality)\s*(tips|guide|how\s*to)',
    ]
    
    for pattern in out_of_domain_patterns:
        if re.search(pattern, q_lower, re.IGNORECASE):
            return True
    
    return False


# =============================================================================
# INTENT CLASSIFICATION - Main Function
# =============================================================================

def classify_query_intent_regex(
    question: str,
    has_history: bool = False
) -> Optional[str]:
    """
    Fast regex-based intent classification using CONTEXT-AWARE SIGNAL DETECTION.

    Returns:
        'META_OP' - Meta operations on previous content (summarize, translate, rephrase)
        'CONTEXT_DEPENDENT' - Follow-up question needing conversation history
        'STANDALONE' - Independent question, no context needed
        'TOPIC_SWITCH' - Clear pivot to new topic
        None - Ambiguous, needs LLM with context

    Args:
        question: User query
        has_history: Whether chat history exists (if False, must be STANDALONE)

    Strategy:
        Instead of simple pattern matching, we detect SIGNALS and apply PRIORITY RULES:
        1. Detect all signals present in the query
        2. Apply priority rules to resolve conflicts
        3. NEW_WORK signals override META_OP signals
        4. PREVIOUS_REFERENCE is REQUIRED for META_OP

    Coverage: ~70% of queries
    Savings: ~500 tokens per hit
    """
    # =========================================================================
    # CONFIGURATION CHECK
    # =========================================================================
    intent_config = REGEX_CONFIG.get("intent_classification", {})
    if not intent_config.get("enabled", True):
        # Intent classification disabled - always use LLM
        return None

    # If no history, it MUST be standalone
    if not has_history:
        return IntentClass.STANDALONE.value

    q_lower = normalize_query(question)

    # =========================================================================
    # SIGNAL DETECTION - Detect all signals present in query
    # =========================================================================
    signals = _detect_intent_signals(q_lower)
    
    # =========================================================================
    # PRIORITY-BASED CLASSIFICATION
    # =========================================================================

    # Priority 1: TOPIC_SWITCH - Explicit pivots always win
    if intent_config.get("topic_switch", {}).get("enabled", True):
        if signals['topic_switch']:
            return IntentClass.TOPIC_SWITCH.value

    # Priority 2: NEW_WORK overrides everything else
    # If asking for new work (go through X, search, analyze), it's STANDALONE
    if intent_config.get("standalone", {}).get("enabled", True):
        if signals['new_work'] and not signals['context_reference']:
            return IntentClass.STANDALONE.value

    # Priority 3: CONTEXT_DEPENDENT - Has context references (pronouns like his/her/their)
    # This takes priority over META_OP because "summarize his conversation" is about
    # a previously mentioned entity, not about the AI's previous response
    if intent_config.get("context_dependent", {}).get("enabled", True):
        if signals['context_reference']:
            return IntentClass.CONTEXT_DEPENDENT.value

    # Priority 4: META_OP - ONLY if references previous AND no new work AND no context ref
    # META_OP requires: meta_keyword + previous_reference + no new_work
    if intent_config.get("meta_op", {}).get("enabled", True):
        if signals['meta_keyword'] and signals['previous_reference'] and not signals['new_work']:
            return IntentClass.META_OP.value

    # Priority 5: STANDALONE - Clear independent queries
    if intent_config.get("standalone", {}).get("enabled", True):
        if signals['standalone_indicator']:
            return IntentClass.STANDALONE.value
    
    # =========================================================================
    # AMBIGUOUS - Needs LLM
    # =========================================================================
    return None


def _detect_intent_signals(q_lower: str) -> dict:
    """
    Detect all intent signals present in the query.
    Returns a dictionary of boolean flags for each signal type.
    
    This is the KEY IMPROVEMENT - we detect signals first, then apply rules.
    """
    signals = {
        'meta_keyword': False,          # summarize, translate, rephrase, etc.
        'previous_reference': False,    # the above, this, that, it, your response
        'new_work': False,              # go through X, search, find, analyze
        'context_reference': False,     # pronouns, references to earlier content
        'topic_switch': False,          # explicit topic changes
        'standalone_indicator': False,  # specific entities, dates, names
    }
    
    # -------------------------------------------------------------------------
    # META KEYWORDS (operations that COULD be meta-ops)
    # -------------------------------------------------------------------------
    meta_keywords = [
        r'\b(summarize|summary|sum\s*up)\b',
        r'\b(translate|convert)\b.*\b(to|into|in)\s+(urdu|english|hindi|arabic)\b',  # translate X to urdu
        r'\b(translate|convert)\s+(to|into|in)\b',  # translate to urdu (direct)
        r'\b(rephrase|reword|rewrite|paraphrase)\b',
        r'\b(shorten|lengthen|simplify|elaborate)\b',
        r'\b(format|reformat)\s*(as|into|in)\b',
        r'\b(bullet\s*points?|numbered\s*list|table\s*format)\b',
        r'\b(make|keep)\s*(it|this|that)?\s*(short|brief|concise|detailed|shorter|longer|simpler)\b',
        r'\b(in|under|within)\s*\d+\s*(words?|sentences?|lines?)\b',
    ]
    
    for pattern in meta_keywords:
        if re.search(pattern, q_lower, re.IGNORECASE):
            signals['meta_keyword'] = True
            break
    
    # -------------------------------------------------------------------------
    # PREVIOUS REFERENCE (references to previous AI response)
    # These are REQUIRED for META_OP classification
    # -------------------------------------------------------------------------
    previous_references = [
        # Explicit references to previous content
        r'\b(the\s+)?(above|previous|earlier|prior)\b',
        r'\b(this|that)\s+(response|answer|reply|text|content|information)\b',
        r'\b(what\s+)?(you\s+)?(just\s+)?(said|wrote|mentioned|provided|gave)\b',
        r'\b(your\s+)(response|answer|reply|output|result)\b',
        r'\b(the\s+)?(response|answer|reply)\s+(above|you\s+gave)\b',
        
        # "what you said/wrote" = AI's previous response
        r'\bwhat\s+you\s+(just\s+)?(said|wrote|mentioned)\b',
        
        # Pronouns that reference previous content in meta-op context
        # "translate THIS to urdu" - this = previous response
        r'\b(translate|summarize|rephrase|reword|convert|format)\s+(this|that|it)\b',
        r'\b(make|keep)\s+(it|this|that)\s+(shorter|longer|simpler|brief|concise)\b',
        r'\b(put|convert|change)\s+(it|this|that)\s+(in|into|as)\b',
        
        # Standalone pronouns at end suggesting reference
        r'\bsummarize\s+(the\s+)?(above|this|that)\b',
        r'\btranslate\s+(the\s+)?(above|this|that)\b',
        
        # Word count requests (implicitly about previous content)
        r'\b(in|under|within)\s*\d+\s*(words?|sentences?|lines?)\s*(please|pls)?\s*$',
        r'^\d+\s*(words?|sentences?)\s*(please|pls|max|only)?\s*$',
        
        # Formatting requests (implicitly about previous content)
        r'^(bullet\s*points?|numbered\s*list|table)\s*(please|pls|format)?\s*$',
        r'\b(as|in|into)\s+(bullet\s*points?|list|table)\s*(please|pls)?\s*$',
    ]
    
    for pattern in previous_references:
        if re.search(pattern, q_lower, re.IGNORECASE):
            signals['previous_reference'] = True
            break
    
    # -------------------------------------------------------------------------
    # NEW WORK INDICATORS (requests for new research/analysis)
    # These OVERRIDE meta_keyword signals
    # NOTE: Be careful not to match possessive references like "his conversation"
    # -------------------------------------------------------------------------
    
    # First check if there's a possessive pronoun pattern - if so, don't set new_work
    has_possessive_ref = bool(re.search(r'\b(his|her|their|its)\s+(conversation|chat|feedback|complaint)', q_lower, re.IGNORECASE))
    
    if not has_possessive_ref:
        new_work_indicators = [
            # Research/Search commands
            r'\b(go\s+through|look\s+(at|through|into)|check\s+(out|through))\b',
            r'\b(search|find|look\s*up|research|investigate|explore)\s+(the|for|in|on|about)?\b',
            r'\b(analyze|analyse|review|examine|study)\s+(the|this|that|all|my|our)?\s*\w+\b',
            
            # Data source references (indicates new work, not meta-op)
            r'\b(forum|database|data|records|logs|files|documents)\b',
            r'\b(pakwheels|whatsapp|system|platform|website)\s+(forum|data|records)?\b',
            
            # Action on external content (NOT on previous response)
            r'\b(read|scan|parse|extract|pull|fetch|get)\s+(from|the|all|data)\b',
            r'\b(compile|gather|collect|aggregate)\s+(the|all|data|information)\b',
            
            # Report generation from scratch (with data source mentioned)
            r'\b(create|generate|produce|prepare|make)\s+(a|the|my)?\s*(report|summary|analysis)\s+(on|about|from|of)\b',
            r'\b(write|draft)\s+(a|the|my)?\s*(report|summary|analysis|document)\s+(on|about|from)\b',
            
            # Specific entity queries with data source
            r'\b(customers?|users?|people)\s+(who|that|with)\b',
            r'\b(all|every|each)\s+(customer|user|query|complaint)\b',
        ]
        
        for pattern in new_work_indicators:
            if re.search(pattern, q_lower, re.IGNORECASE):
                signals['new_work'] = True
                break
    
    # -------------------------------------------------------------------------
    # CONTEXT REFERENCE (pronouns/references that need history)
    # NOTE: "what you said" = previous response (META_OP)
    #       "the one you mentioned" = specific entity (CONTEXT_DEPENDENT)
    # -------------------------------------------------------------------------
    context_references = [
        # Pronouns at start
        r'^(it|that|this|these|those)\s+',
        r'^(does|is|can|will|would|should|has|have)\s+(it|that|this)\b',
        r'^(what|how)\s+(about|is)\s+(it|that|this)\b',
        
        # Possessive pronouns (his/her/their conversation/chat/feedback)
        r'\b(his|her|their|its)\s+(conversation|chat|feedback|complaint|message|response)\b',
        r'\b(summarize|show|get|translate)\s+(his|her|their)\b',
        
        # Ordinal references
        r'\b(the\s+)?(first|second|third|last|next)\s+(one|point|item)\b',
        r'\b(point|item|number|#)\s*\d+\b',
        
        # Elaboration/more requests
        r'^(show\s+me\s+)?more\s*(please|pls|details?)?\s*$',
        r'^tell\s+me\s+more\b',
        r'^more\s+(details?|info|information)\s*$',
        r'^(elaborate|expand|explain)\s*(more|further)?\s*$',
        
        # Vague follow-ups
        r'^(and|also|plus|too)\b',
        r'^(what|how)\s+about\b(?!\s+(a\s+)?(different|another|new))',
        r'^(any|anything)\s+(else|other|more)\b',
        r'^(same|similar)\s+(in|for|thing)\b',
        
        # Reference to mentioned ENTITIES (not the response itself)
        # "the one you mentioned" - refers to an entity, not the response
        r'\b(the\s+)?(one|ones|customer|person|car|model)\s+(you\s+)?(mentioned|showed|listed)\b',
        # Exclude "what you said" which refers to the response (META_OP)
        # Only match "you mentioned [entity]" not "what you said"
        r'\b(you\s+)(mentioned|told\s+me\s+about)\s+\w+\b',
    ]
    
    for pattern in context_references:
        if re.search(pattern, q_lower, re.IGNORECASE):
            signals['context_reference'] = True
            break
    
    # -------------------------------------------------------------------------
    # TOPIC SWITCH (explicit pivots)
    # -------------------------------------------------------------------------
    topic_switches = [
        r'^(now|okay|ok)\s+(show|tell|give|let\'?s)\b',
        r'^(forget|never\s*mind|skip|leave)\s+(that|it|this|about)',
        r'^(let\'?s|can\s*we)\s*(talk|discuss|move|switch)\s*(to|about)',
        r'^(change|switch|move)\s*(the\s*)?(topic|subject)',
        r'^(instead|rather)\s*(,|\s)*(show|tell|give)',
        r'\bforget\s+\w+\s*,?\s*(what|how)\s+about\b',
        # Direct model/topic switches
        r'^(switch|change|move)\s+(to|about)\s+\w+',  # "switch to jolion"
    ]
    
    for pattern in topic_switches:
        if re.search(pattern, q_lower, re.IGNORECASE):
            signals['topic_switch'] = True
            break
    
    # -------------------------------------------------------------------------
    # STANDALONE INDICATORS (specific queries that don't need context)
    # -------------------------------------------------------------------------
    standalone_indicators = [
        # System query patterns (CRITICAL FIX - these should always be standalone)
        r'\b(show|get|display|list)\s+(latest|recent|last|all)?\s*(queries|query|cache|history)\b',
        r'\b(clear|delete|remove)\s+(cache|history|queries)\b',
        r'\b(cache\s+(stats|statistics|size|info))\b',
        r'\b(query\s+(history|log|statistics))\b',
        r'\b(latest\s+(queries|searches|requests))\b',
        r'^(stats|statistics|status)\s*(please|pls)?\s*$',

        # Time-specific queries
        r'\b(on|dated?)\s*\d{1,2}(st|nd|rd|th)?\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
        r'\b(yesterday|today|last\s*(week|month|year))\b',
        r'\b(in|during|from)\s*(20\d{2}|january|february|march)\b',

        # Statistical queries
        r'^(how\s+many|what\s+(is|are)\s+the\s+(number|count|total))\b',
        r'^(top\s+\d+|most\s+(common|popular)|list\s+all)\b',

        # Named entity queries
        r'^(show|get|find)\s+(me\s+)?(conversation|chat)\s+(of|with)\s+[A-Z]',
        r'\b[A-Z][a-z]+\'?s?\s+(conversation|chat|complaint|feedback)\b',
        r'^what\s+did\s+[A-Z][a-z]+\s+(say|ask|tell)\b',

        # Sentiment queries
        r'\b(angry|dissatisfied|satisfied|happy)\s+(customers?|users?)\b',

        # Location-specific
        r'\b(in|at)\s+(karachi|lahore|islamabad|rawalpindi)\s+(show|list|find)\b',

        # Brand/model specific with action
        r'^(what|show|list|find).{0,30}(haval|jolion|h6|picanto|sportage)\b',
    ]
    
    for pattern in standalone_indicators:
        if re.search(pattern, q_lower, re.IGNORECASE):
            signals['standalone_indicator'] = True
            break
    
    return signals



# =============================================================================
# LEGACY HELPER FUNCTIONS (kept for backwards compatibility, but not used)
# =============================================================================

# NOTE: The new signal-based approach in _detect_intent_signals replaces these

# =============================================================================
# COMBINED CLASSIFIER WITH LLM FALLBACK
# =============================================================================

def classify_with_regex_first(
    question: str,
    llm_classifier_func,
    classifier_type: str,
    *args,
    **kwargs
) -> Tuple[str, str]:
    """
    Try regex classification first, fall back to LLM if ambiguous.

    Args:
        question: User query
        llm_classifier_func: LLM classification function to fall back to
        classifier_type: "domain" or "intent"
        *args, **kwargs: Additional arguments for LLM classifier

    Returns:
        Tuple of (classification_result, source)
        source is either "regex" or "llm"

    Example:
        classification, source = classify_with_regex_first(
            question="Hello",
            llm_classifier_func=classify_query_domain_llm,
            classifier_type="domain",
            llm=llm,
            company_id="haval"
        )
        # Returns: ("small_talk", "regex") - instant, 0 tokens
    """
    # Try regex first
    if classifier_type == "domain":
        company_id = kwargs.get("company_id", "haval")
        mode = kwargs.get("mode", "auto")
        regex_result = classify_query_domain_regex(question, company_id, mode)
    elif classifier_type == "intent":
        has_history = kwargs.get("chat_history") is not None and len(kwargs.get("chat_history", [])) > 0
        regex_result = classify_query_intent_regex(question, has_history)
    else:
        raise ValueError(f"Unknown classifier_type: {classifier_type}")

    # If regex found a clear answer, use it (instant, 0 tokens)
    if regex_result is not None:
        # print(f"  [Regex Classifier] ⚡ FAST PATH: '{question[:50]}...' → {regex_result.upper()} (0 tokens)")
        return regex_result, "regex"

    # Otherwise, fall back to LLM (ambiguous case)
    # print(f"  [Regex Classifier] 🔄 AMBIGUOUS: '{question[:50]}...' → Falling back to LLM")
    llm_result = llm_classifier_func(*args, **kwargs)
    return llm_result, "llm"


# =============================================================================
# USAGE STATISTICS TRACKING
# =============================================================================

class RegexClassifierStats:
    """
    Track regex vs LLM usage for optimization.

    Usage:
        stats = RegexClassifierStats()

        # After each classification
        if source == "regex":
            stats.record_regex_hit(classifier_type, result)
        else:
            stats.record_llm_fallback(classifier_type, result)

        # Print report
        stats.print_report()
    """

    def __init__(self):
        self.regex_hits = {
            "domain": {"in_domain": 0, "out_of_domain": 0, "small_talk": 0},
            "intent": {"META_OP": 0, "STANDALONE": 0, "CONTEXT_DEPENDENT": 0, "TOPIC_SWITCH": 0}
        }
        self.llm_fallbacks = {"domain": 0, "intent": 0}

    def record_regex_hit(self, classifier_type: str, result: str = None):
        """Record successful regex classification (0 tokens)"""
        if classifier_type in self.regex_hits:
            if result and isinstance(self.regex_hits[classifier_type], dict):
                if result in self.regex_hits[classifier_type]:
                    self.regex_hits[classifier_type][result] += 1
                else:
                    self.regex_hits[classifier_type][result] = 1
            else:
                # Legacy support
                total = sum(self.regex_hits[classifier_type].values()) if isinstance(self.regex_hits[classifier_type], dict) else self.regex_hits[classifier_type]
                if isinstance(self.regex_hits[classifier_type], dict):
                    if result:
                        self.regex_hits[classifier_type][result] = self.regex_hits[classifier_type].get(result, 0) + 1

    def record_llm_fallback(self, classifier_type: str, result: str = None):
        """Record LLM fallback (110 or 500 tokens)"""
        if classifier_type in self.llm_fallbacks:
            self.llm_fallbacks[classifier_type] += 1

    def get_total_regex_hits(self, classifier_type: str) -> int:
        """Get total regex hits for a classifier type"""
        if classifier_type in self.regex_hits:
            if isinstance(self.regex_hits[classifier_type], dict):
                return sum(self.regex_hits[classifier_type].values())
            return self.regex_hits[classifier_type]
        return 0

    def get_hit_rate(self, classifier_type: str) -> float:
        """Get regex hit rate (0-1)"""
        regex_total = self.get_total_regex_hits(classifier_type)
        llm_total = self.llm_fallbacks.get(classifier_type, 0)
        total = regex_total + llm_total
        if total == 0:
            return 0.0
        return regex_total / total

    def get_tokens_saved(self) -> int:
        """Estimate total tokens saved by regex"""
        domain_savings = self.get_total_regex_hits("domain") * 110
        intent_savings = self.get_total_regex_hits("intent") * 500
        return domain_savings + intent_savings

    def print_report(self):
        """Print detailed usage statistics"""
        # print("\n" + "=" * 80)
        # print("                    REGEX CLASSIFIER STATISTICS")
        # print("=" * 80)

        for classifier_type in ["domain", "intent"]:
            regex_total = self.get_total_regex_hits(classifier_type)
            llm_fallbacks = self.llm_fallbacks.get(classifier_type, 0)
            total = regex_total + llm_fallbacks
            hit_rate = self.get_hit_rate(classifier_type)

            tokens_per_call = 110 if classifier_type == "domain" else 500
            tokens_saved = regex_total * tokens_per_call

            # print(f"\n{'─' * 40}")
            # print(f" {classifier_type.upper()} CLASSIFICATION")
            # print(f"{'─' * 40}")
            
            # Show breakdown by result type
            if isinstance(self.regex_hits[classifier_type], dict):
                # print(f" Regex Hits Breakdown:")
                for result, count in sorted(self.regex_hits[classifier_type].items()):
                    if count > 0:
                        pass
                        # print(f"   • {result}: {count}")
            
            # print(f"\n Summary:")
            # print(f"   Regex Hits:     {regex_total:>6} ({hit_rate * 100:>5.1f}%)")
            # print(f"   LLM Fallbacks:  {llm_fallbacks:>6} ({(1 - hit_rate) * 100:>5.1f}%)")
            # print(f"   Total:          {total:>6}")
            # print(f"   Tokens Saved:   {tokens_saved:>6} ({tokens_per_call}/call)")

        total_tokens_saved = self.get_tokens_saved()
        # Using Claude-3 Sonnet pricing: $0.003/1K input tokens
        estimated_cost_saved = (total_tokens_saved * 0.003 / 1000)

        # print(f"\n{'=' * 80}")
        # print(f" TOTAL TOKENS SAVED:    {total_tokens_saved:,}")
        # print(f" ESTIMATED COST SAVED:  ${estimated_cost_saved:.4f}")
        # print("=" * 80 + "\n")


# =============================================================================
# QUICK TEST FUNCTIONS
# =============================================================================

def test_domain_classification():
    """Quick test for domain classification"""
    test_cases = [
        # Small talk
        ("hello", "small_talk"),
        ("Assalam o Alaikum", "small_talk"),
        ("thanks", "small_talk"),
        ("AOA", "small_talk"),
        
        # In-domain - automotive
        ("what is the price of H6", "in_domain"),
        ("jolion ki qeemat", "in_domain"),
        ("havel ki gadi kaisi hai", "in_domain"),
        ("show me conversation of Ahmed", "in_domain"),
        ("queries reported on 22nd december", "in_domain"),
        ("are there any angry customers", "in_domain"),
        ("how do people compare haval with kia", "in_domain"),
        ("picanto brake issue", "in_domain"),
        
        # Out-of-domain
        ("write an essay on climate change", "out_of_domain"),
        ("recipe for biryani", "out_of_domain"),
        ("who is the president of USA", "out_of_domain"),
        
        # Typo tolerance
        ("jolon price", "in_domain"),  # jolion typo
        ("havl h6 features", "in_domain"),  # haval typo
        ("pikanto availability", "in_domain"),  # picanto typo
    ]
    
    # print("\n" + "=" * 60)
    # print("DOMAIN CLASSIFICATION TESTS")
    # print("=" * 60)
    
    passed = 0
    failed = 0
    
    for query, expected in test_cases:
        result = classify_query_domain_regex(query)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        # print(f"{status} '{query[:40]:<40}' → {str(result):<15} (expected: {expected})")
    
    # print(f"\nResults: {passed}/{passed+failed} passed")
    return passed, failed


def test_intent_classification():
    """Quick test for intent classification"""
    test_cases = [
        # META_OP - Must reference previous content explicitly
        ("summarize the above in 100 words", True, "META_OP"),
        ("translate this to urdu", True, "META_OP"),  # "this" references previous
        ("put it in bullet points", True, "META_OP"),  # "it" references previous
        ("make it shorter", True, "META_OP"),
        ("bullet points please", True, "META_OP"),  # Implicit reference
        
        # CONTEXT_DEPENDENT
        ("what about it", True, "CONTEXT_DEPENDENT"),
        ("show me more", True, "CONTEXT_DEPENDENT"),
        ("the one you mentioned", True, "CONTEXT_DEPENDENT"),
        ("his conversation", True, "CONTEXT_DEPENDENT"),
        ("summarize his feedback", True, "CONTEXT_DEPENDENT"),
        
        # TOPIC_SWITCH
        ("now show me the picanto", True, "TOPIC_SWITCH"),
        ("forget that, tell me about brakes", True, "TOPIC_SWITCH"),
        ("switch to jolion", True, "TOPIC_SWITCH"),
        
        # STANDALONE
        ("what is the price of H6 in Lahore", True, "STANDALONE"),
        ("queries reported on 22nd december", True, "STANDALONE"),
        ("show me conversation of Ahmed", True, "STANDALONE"),
        ("are there any angry customers", True, "STANDALONE"),
        
        # No history = always STANDALONE
        ("what about it", False, "STANDALONE"),  # No history
    ]
    
    # print("\n" + "=" * 60)
    # print("INTENT CLASSIFICATION TESTS")
    # print("=" * 60)
    
    passed = 0
    failed = 0
    
    for query, has_history, expected in test_cases:
        result = classify_query_intent_regex(query, has_history)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        hist_str = "[+hist]" if has_history else "[no hist]"
        # print(f"{status} '{query[:35]:<35}' {hist_str:<10} → {str(result):<20} (expected: {expected})")
    
    # print(f"\nResults: {passed}/{passed+failed} passed")
    return passed, failed


def run_all_tests():
    """Run all classification tests"""
    # print("\n" + "=" * 80)
    # print("                    REGEX CLASSIFIER TEST SUITE v2.0")
    # print("=" * 80)
    
    d_pass, d_fail = test_domain_classification()
    i_pass, i_fail = test_intent_classification()
    
    total_pass = d_pass + i_pass
    total_fail = d_fail + i_fail
    
    # print("\n" + "=" * 60)
    # print("FINAL RESULTS")
    # print("=" * 60)
    # print(f"Domain Classification: {d_pass}/{d_pass + d_fail} passed")
    # print(f"Intent Classification: {i_pass}/{i_pass + i_fail} passed")
    # print(f"{'─' * 40}")
    # print(f"Total: {total_pass}/{total_pass + total_fail} passed ({100 * total_pass / (total_pass + total_fail):.1f}%)")
    
    if total_fail > 0:
        pass
        # print("\n⚠️  Some tests failed. Review the patterns above.")
    else:
        pass
        # print("\n✅ All tests passed!")


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main functions
    'classify_query_domain_regex',
    'classify_query_intent_regex',
    'classify_with_regex_first',
    
    # Classes
    'RegexClassifierStats',
    'DomainClass',
    'IntentClass',
    'PatternConfig',
    
    # Utilities
    'normalize_query',
    'build_typo_pattern',
    'get_all_brand_patterns',
    'get_all_model_patterns',
    
    # Testing
    'run_all_tests',
    'test_domain_classification',
    'test_intent_classification',
]


# =============================================================================
# CLI ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Interactive mode: classify the provided query
        query = " ".join(sys.argv[1:])
        print(f"\nQuery: '{query}'")
        # print(f"Domain: {classify_query_domain_regex(query)}")
        # print(f"Intent (with history): {classify_query_intent_regex(query, has_history=True)}")
        # print(f"Intent (no history): {classify_query_intent_regex(query, has_history=False)}")
    else:
        # Run tests
        run_all_tests()