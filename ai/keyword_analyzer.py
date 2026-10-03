"""
Comprehensive Keyword Analyzer for WhatsApp and Reddit Messages
Provides detailed keyword matching, categorization, and scoring
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


@dataclass
class KeywordMatch:
    """Represents a matched keyword with context"""
    keyword: str
    category: str
    position: int
    context: str


class ComprehensiveKeywordAnalyzer:
    """Advanced keyword analysis system for message classification"""
    
    @staticmethod
    def run_batch_severity_analysis(company_id: str = 'haval', source: str = 'pakwheels', batch_size: int = 100) -> Dict[str, int]:
        """
        Run batch keyword severity analysis on unanalyzed messages.
        
        Args:
            company_id: Company identifier
            source: Data source ('pakwheels', 'whatsapp', 'reddit')
            batch_size: Number of messages to process
            
        Returns:
            Dictionary with analysis statistics
        """
        from tqdm import tqdm

        from models.database import get_db_connection
        
        stats = {
            'total_analyzed': 0,
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'errors': 0
        }
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            if source == 'pakwheels':
                # Find posts without severity analysis
                cur.execute("""
                    SELECT id, cooked_text FROM posts
                    WHERE company_id = ?
                    AND (severity IS NULL OR severity = '')
                    AND category NOT LIKE '%Reddit%'
                    LIMIT ?
                """, (company_id, batch_size))
            elif source == 'whatsapp':
                # Find WhatsApp messages without severity
                cur.execute("""
                    SELECT id, message FROM whatsapp_messages
                    WHERE company_id = ?
                    AND (severity IS NULL OR severity = '')
                    LIMIT ?
                """, (company_id, batch_size))
            elif source == 'reddit':
                # Find Reddit posts without severity
                cur.execute("""
                    SELECT id, cooked_text FROM posts
                    WHERE company_id = ?
                    AND (severity IS NULL OR severity = '')
                    AND category LIKE '%Reddit%'
                    LIMIT ?
                """, (company_id, batch_size))
            else:
                return stats
            
            messages = cur.fetchall()
            
            if not messages:
                print(f"[KeywordAnalyzer] No unanalyzed {source} messages found")
                return stats
            
            print(f"[KeywordAnalyzer] Analyzing {len(messages)} {source} messages for severity...")
            
            for msg_id, text in tqdm(messages, desc=f"Analyzing {source}"):
                try:
                    # Analyze message
                    analysis = ComprehensiveKeywordAnalyzer.analyze_message(text or '')
                    severity = analysis.get('severity', 'low')
                    
                    # Update database
                    if source == 'pakwheels' or source == 'reddit':
                        cur.execute("""
                            UPDATE posts
                            SET severity = ?
                            WHERE id = ?
                        """, (severity, msg_id))
                    elif source == 'whatsapp':
                        cur.execute("""
                            UPDATE whatsapp_messages
                            SET severity = ?
                            WHERE id = ?
                        """, (severity, msg_id))
                    
                    # Update stats
                    stats['total_analyzed'] += 1
                    stats[severity] = stats.get(severity, 0) + 1
                    
                except Exception as e:
                    print(f"[KeywordAnalyzer] Error analyzing message {msg_id}: {e}")
                    stats['errors'] += 1
            
            conn.commit()
            print(f"[KeywordAnalyzer] Severity analysis complete: {stats}")
            
        except Exception as e:
            print(f"[KeywordAnalyzer] Batch analysis failed: {e}")
        finally:
            conn.close()
        
        return stats
    
    # Automotive-specific complaint keywords (comprehensive list)
    AUTOMOTIVE_KEYWORDS = {
        # Engine & Performance
        'engine': ['engine', 'motor', 'combustion', 'cylinder', 'piston'],
        'noise': ['noise', 'sound', 'knocking', 'rattling', 'squeaking', 'grinding', 'ticking', 'clunking'],
        'vibration': ['vibration', 'shake', 'shaking', 'vibrate', 'trembling', 'judder'],
        'overheating': ['overheat', 'overheating', 'hot', 'temperature', 'temp gauge', 'coolant'],
        'power_loss': ['power loss', 'low power', 'sluggish', 'acceleration', 'pickup', 'lag'],
        'fuel': ['fuel', 'petrol', 'diesel', 'gas', 'mileage', 'consumption', 'economy'],
        'smoke': ['smoke', 'fumes', 'exhaust', 'emission'],
        'oil': ['oil leak', 'oil consumption', 'engine oil', 'oil pressure', 'burning oil'],
        
        # Transmission & Drivetrain
        'transmission': ['transmission', 'gearbox', 'gear', 'shifting', 'clutch', 'dct', 'cvt', 'automatic'],
        'gear_issues': ['gear stuck', 'hard shift', 'slipping', 'jerk', 'delay', 'won\'t shift'],
        
        # Brakes & Safety
        'brakes': ['brake', 'braking', 'abs', 'brake pad', 'disc', 'rotor', 'pedal'],
        'brake_issues': ['brake failure', 'soft pedal', 'hard pedal', 'no brakes', 'brake noise'],
        
        # Suspension & Steering
        'suspension': ['suspension', 'shock', 'strut', 'spring', 'damper', 'absorber'],
        'steering': ['steering', 'wheel', 'alignment', 'pulling', 'loose', 'stiff', 'hard to turn'],
        
        # Electrical
        'battery': ['battery', 'dead battery', 'battery drain', 'won\'t start', 'self'],
        'electrical': ['electrical', 'wiring', 'fuse', 'relay', 'short circuit', 'sensor'],
        'lights': ['headlight', 'taillight', 'drl', 'fog light', 'indicator', 'bulb'],
        'electronics': ['infotainment', 'screen', 'display', 'touchscreen', 'android auto', 'carplay'],
        
        # AC & Climate
        'ac': ['ac', 'air conditioning', 'cooling', 'compressor', 'refrigerant', 'blower'],
        'heating': ['heater', 'heating', 'hot air', 'climate control'],
        
        # Body & Interior
        'rust': ['rust', 'corrosion', 'oxidation', 'paint bubble'],
        'leak': ['leak', 'leaking', 'water', 'moisture', 'wet'],
        'rattle': ['rattle', 'rattling', 'dashboard rattle', 'door rattle'],
        'quality': ['build quality', 'poor quality', 'cheap', 'plastic'],
        
        # Service & Delivery
        'delivery': ['delivery', 'late delivery', 'delayed', 'waiting', 'timeline'],
        'service': ['service center', 'dealership', 'mechanic', 'technician', 'repair'],
        'parts': ['spare parts', 'parts', 'unavailable', 'no stock'],
        'warranty': ['warranty', 'claim', 'coverage', 'guarantee']
    }
    
    # Severity indicators
    CRITICAL_KEYWORDS = [
        'danger', 'dangerous', 'unsafe', 'accident', 'crash', 'fire', 'explosion',
        'total loss', 'complete failure', 'can\'t drive', 'won\'t start', 'dead',
        'emergency', 'urgent', 'immediately', 'safety hazard'
    ]
    
    HIGH_SEVERITY_KEYWORDS = [
        'broke', 'broken', 'failed', 'failure', 'stopped working', 'not working',
        'malfunction', 'damaged', 'severe', 'serious', 'major', 'terrible'
    ]
    
    MEDIUM_SEVERITY_KEYWORDS = [
        'problem', 'issue', 'trouble', 'concern', 'worry', 'annoying',
        'frustrating', 'disappointed', 'unhappy', 'not satisfied'
    ]
    
    # Sentiment indicators
    NEGATIVE_SENTIMENT = [
        'worst', 'horrible', 'terrible', 'awful', 'pathetic', 'useless',
        'garbage', 'trash', 'junk', 'waste', 'regret', 'mistake', 'scam'
    ]
    
    POSITIVE_SENTIMENT = [
        'good', 'great', 'excellent', 'amazing', 'wonderful', 'perfect',
        'love', 'happy', 'satisfied', 'recommend', 'best'
    ]
    
    # Car model keywords (common in Pakistani market)
    CAR_MODELS = {
        'haval': ['h6', 'jolion', 'h9', 'h2', 'haval'],
        'kia': ['sportage', 'sorento', 'stonic', 'picanto', 'rio', 'cerato', 'carnival'],
        'mg': ['hs', 'zs', 'mg5', 'rx5'],
        'toyota': ['corolla', 'yaris', 'fortuner', 'hilux', 'prado', 'land cruiser'],
        'honda': ['civic', 'city', 'accord', 'brv', 'hrv', 'vezel'],
        'hyundai': ['tucson', 'santa fe', 'elantra', 'sonata', 'ioniq'],
        'changan': ['alsvin', 'karvaan', 'oshan', 'hunter'],
        'proton': ['x70', 'saga', 'x50'],
        'suzuki': ['swift', 'cultus', 'wagon r', 'alto', 'jimny', 'vitara']
    }
    
    @classmethod
    def analyze_message(cls, text: str) -> Dict:
        """
        Comprehensive analysis of a message for keywords
        
        Args:
            text: Message text to analyze
            
        Returns:
            Dictionary with detailed analysis results
        """
        if not text:
            return cls._empty_result()
        
        text_lower = text.lower()
        
        # Find all keyword matches
        automotive_matches = cls._find_automotive_keywords(text_lower)
        severity = cls._calculate_severity(text_lower)
        sentiment = cls._detect_sentiment(text_lower)
        car_models = cls._extract_car_models(text_lower)
        matched_keywords = cls._extract_matched_keywords(text_lower)
        
        # Calculate scores
        automotive_score = len(automotive_matches)
        complaint_likelihood = cls._calculate_complaint_likelihood(
            automotive_score, severity, sentiment, matched_keywords
        )
        
        return {
            'automotive_matches': automotive_matches,
            'automotive_score': automotive_score,
            'severity': severity,
            'sentiment': sentiment,
            'car_models': car_models,
            'matched_keywords': matched_keywords,
            'complaint_likelihood': complaint_likelihood,
            'is_likely_complaint': complaint_likelihood > 0.5,
            'has_automotive_context': automotive_score > 0
        }
    
    @classmethod
    def _find_automotive_keywords(cls, text: str) -> Dict[str, List[str]]:
        """Find automotive-related keywords in text"""
        matches = {}
        
        for category, keywords in cls.AUTOMOTIVE_KEYWORDS.items():
            found = []
            for keyword in keywords:
                # Use word boundary matching for accuracy
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text):
                    found.append(keyword)
            
            if found:
                matches[category] = found
        
        return matches
    
    @classmethod
    def _calculate_severity(cls, text: str) -> str:
        """Determine severity level based on keywords"""
        if any(keyword in text for keyword in cls.CRITICAL_KEYWORDS):
            return 'critical'
        elif any(keyword in text for keyword in cls.HIGH_SEVERITY_KEYWORDS):
            return 'high'
        elif any(keyword in text for keyword in cls.MEDIUM_SEVERITY_KEYWORDS):
            return 'medium'
        else:
            return 'low'
    
    @classmethod
    def _detect_sentiment(cls, text: str) -> str:
        """Detect sentiment from text"""
        negative_count = sum(1 for kw in cls.NEGATIVE_SENTIMENT if kw in text)
        positive_count = sum(1 for kw in cls.POSITIVE_SENTIMENT if kw in text)
        
        if negative_count > positive_count:
            return 'negative'
        elif positive_count > negative_count:
            return 'positive'
        else:
            return 'neutral'
    
    @classmethod
    def _extract_car_models(cls, text: str) -> List[str]:
        """Extract mentioned car models"""
        found_models = []
        
        for brand, models in cls.CAR_MODELS.items():
            for model in models:
                pattern = r'\b' + re.escape(model) + r'\b'
                if re.search(pattern, text):
                    found_models.append(model.upper())
        
        return list(set(found_models))  # Remove duplicates
    
    @classmethod
    def _extract_matched_keywords(cls, text: str) -> List[str]:
        """Extract all matched keywords for highlighting"""
        keywords = []
        
        # Combine all keyword lists
        all_keywords = []
        for kw_list in cls.AUTOMOTIVE_KEYWORDS.values():
            all_keywords.extend(kw_list)
        all_keywords.extend(cls.CRITICAL_KEYWORDS)
        all_keywords.extend(cls.HIGH_SEVERITY_KEYWORDS)
        all_keywords.extend(cls.MEDIUM_SEVERITY_KEYWORDS)
        
        # Find matches
        for keyword in all_keywords:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text):
                keywords.append(keyword)
        
        return list(set(keywords))  # Remove duplicates
    
    @classmethod
    def _calculate_complaint_likelihood(cls, auto_score: int, severity: str, 
                                       sentiment: str, keywords: List[str]) -> float:
        """Calculate likelihood that this is a genuine complaint (0-1)"""
        score = 0.0
        
        # Automotive context (0-0.4)
        score += min(auto_score * 0.1, 0.4)
        
        # Severity (0-0.3)
        severity_weights = {'critical': 0.3, 'high': 0.2, 'medium': 0.15, 'low': 0.05}
        score += severity_weights.get(severity, 0)
        
        # Sentiment (0-0.2)
        if sentiment == 'negative':
            score += 0.2
        elif sentiment == 'neutral':
            score += 0.1
        
        # Keyword density (0-0.1)
        if len(keywords) > 5:
            score += 0.1
        elif len(keywords) > 2:
            score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    @classmethod
    def _empty_result(cls) -> Dict:
        """Return empty analysis result"""
        return {
            'automotive_matches': {},
            'automotive_score': 0,
            'severity': 'low',
            'sentiment': 'neutral',
            'car_models': [],
            'matched_keywords': [],
            'complaint_likelihood': 0.0,
            'is_likely_complaint': False,
            'has_automotive_context': False
        }
    
    @classmethod
    def highlight_keywords(cls, text: str, keywords: List[str]) -> str:
        """
        Add HTML highlighting to matched keywords
        
        Args:
            text: Original text
            keywords: List of keywords to highlight
            
        Returns:
            HTML string with highlighted keywords
        """
        if not keywords:
            return text
        
        # Sort keywords by length (longest first) to avoid partial matches
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        
        result = text
        for keyword in sorted_keywords:
            # Case-insensitive replacement with highlighting
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)
            result = pattern.sub(
                lambda m: f'<span class="keyword-highlight">{m.group(0)}</span>',
                result
            )
        
        return result
    
    @classmethod
    def get_category_badge_html(cls, category: str, count: int) -> str:
        """Generate HTML badge for keyword category"""
        category_labels = {
            'engine': '🔧 Engine',
            'transmission': '⚙️ Transmission',
            'brakes': '🛑 Brakes',
            'electrical': '⚡ Electrical',
            'ac': '❄️ AC/Climate',
            'service': '🔨 Service',
            'delivery': '🚚 Delivery'
        }
        
        label = category_labels.get(category, category.title())
        return f'<span class="category-badge category-{category}" title="{count} matches">{label} ({count})</span>'
