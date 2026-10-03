"""
Message filtering utility to remove bot-generated content and keep only meaningful human messages
"""

import re


class MessageFilter:
    """Filter out automated bot messages and keep only meaningful human messages"""
    
    # Bot greeting patterns
    BOT_GREETINGS = [
        r'^(hello|hi|hey|greetings|welcome|thanks for contacting)',
        r'^(thank you for|thanks for|appreciate)',
        r'^(how can i|how may i|how can we|what can i)',
        r'^(please|kindly|we appreciate)',
    ]
    
    # IVR/Menu options
    IVR_MENUS = [
        r'(press|select|choose|option|menu|dial)',
        r'(1\.|2\.|3\.|4\.|5\.|6\.|7\.|8\.|9\.)',
        r'(for.*press|for.*select|for.*option)',
        r'(to.*press|to.*select|to.*dial)',
    ]
    
    # Scripted questions
    SCRIPTED_QUESTIONS = [
        r'(how are you|how are you doing|how\'s everything)',
        r'(is there anything else|anything else i can|can i help)',
        r'(do you have|do you need|would you like)',
        r'(please provide|please share|please tell)',
        r'(can you please|could you please|would you please)',
    ]
    
    # Generic help prompts
    GENERIC_HELP = [
        r'(we are here to help|happy to help|glad to assist)',
        r'(feel free to|don\'t hesitate to|don\'t worry)',
        r'(our team|our staff|our support)',
        r'(available 24|open 24|always available)',
        r'(thank you for your patience|appreciate your patience)',
    ]
    
    # Document requests (bot asking for info)
    DOCUMENT_REQUESTS = [
        r'(please provide|please share|please send|please upload)',
        r'(order number|reference number|ticket number|case number)',
        r'(date of|time of|details of)',
        r'(can you provide|could you share|would you send)',
    ]
    
    # Repeated prompts
    REPEATED_PROMPTS = [
        r'(is there anything else|anything else|any other)',
        r'(have a great day|have a good day|goodbye)',
        r'(thank you|thanks|appreciate)',
        r'(see you|talk soon|bye)',
    ]
    
    # Generic templates
    GENERIC_TEMPLATES = [
        r'(we understand|we realize|we know)',
        r'(we will|we shall|we can)',
        r'(best regards|kind regards|warm regards)',
        r'(sincerely|yours truly|respectfully)',
    ]
    
    @staticmethod
    def is_bot_message(message: str) -> bool:
        """
        Check if a message is likely from a bot/automated system
        Returns True if message is bot-generated, False if it's human
        """
        if not message or len(message.strip()) < 5:
            return True  # Too short, likely bot
        
        message_lower = message.lower().strip()
        
        # Check against all bot patterns
        all_patterns = (
            MessageFilter.BOT_GREETINGS +
            MessageFilter.IVR_MENUS +
            MessageFilter.SCRIPTED_QUESTIONS +
            MessageFilter.GENERIC_HELP +
            MessageFilter.DOCUMENT_REQUESTS +
            MessageFilter.REPEATED_PROMPTS +
            MessageFilter.GENERIC_TEMPLATES
        )
        
        # Count how many bot patterns match
        matches = 0
        for pattern in all_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                matches += 1
        
        # If multiple patterns match, it's likely a bot message
        if matches >= 2:
            return True
        
        # Check for very common bot phrases
        if any(phrase in message_lower for phrase in [
            'hello', 'hi there', 'thank you', 'how can i help',
            'please provide', 'is there anything else', 'have a great day',
            'best regards', 'kind regards', 'sincerely'
        ]):
            return True
        
        return False
    
    @staticmethod
    def is_meaningful_message(message: str) -> bool:
        """
        Check if a message contains meaningful human content
        Returns True if message has actionable/informational value
        """
        if not message or len(message.strip()) < 5:
            return False
        
        message_lower = message.lower().strip()
        
        # Keywords indicating meaningful content
        meaningful_keywords = [
            'price', 'cost', 'payment', 'delivery', 'shipping',
            'problem', 'issue', 'complaint', 'broken', 'damaged',
            'not working', 'error', 'bug', 'feature', 'quality',
            'service', 'support', 'help', 'question', 'how',
            'when', 'where', 'what', 'why', 'which',
            'order', 'purchase', 'buy', 'sell', 'exchange',
            'refund', 'return', 'warranty', 'guarantee',
            'address', 'location', 'contact', 'phone', 'email',
            'available', 'stock', 'inventory', 'discount', 'offer',
            'specification', 'spec', 'model', 'version', 'color',
            'size', 'weight', 'dimension', 'material', 'brand'
        ]
        
        # Check if message contains meaningful keywords
        keyword_count = sum(1 for keyword in meaningful_keywords if keyword in message_lower)
        
        if keyword_count >= 1:
            return True
        
        # Check if message is a question (contains question mark)
        if '?' in message:
            return True
        
        # Check if message has specific details (numbers, dates, etc.)
        if re.search(r'\d+', message):  # Contains numbers
            return True
        
        # Check message length - longer messages are usually more meaningful
        if len(message.strip()) > 50:
            return True
        
        return False
    
    @staticmethod
    def filter_messages(messages: list) -> list:
        """
        Filter a list of messages to remove bot content and keep only meaningful human messages
        
        Args:
            messages: List of message strings
            
        Returns:
            Filtered list of meaningful human messages
        """
        filtered = []
        
        for message in messages:
            # Skip if it's a bot message
            if MessageFilter.is_bot_message(message):
                continue
            
            # Keep if it's meaningful
            if MessageFilter.is_meaningful_message(message):
                filtered.append(message)
        
        return filtered
