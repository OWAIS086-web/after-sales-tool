"""
Token Counter Utility
Calculates token usage for LLM and embedding APIs
"""

import tiktoken
from utils.logger import ai_logger


class TokenCounter:
    """Utility for counting tokens in text"""
    
    # Token encoding models
    _encodings = {}
    
    @staticmethod
    def get_encoding(model_name):
        """Get or create token encoding for a model"""
        if model_name not in TokenCounter._encodings:
            try:
                # Map model names to encoding names
                encoding_map = {
                    'grok-3-fast': 'cl100k_base',  
                    'grok-2': 'cl100k_base',
                    'grok': 'cl100k_base',
                    'gemini-2.5-flash': 'o200k_base',  
                    'gemini-1.5-pro': 'o200k_base',
                    'gemini-pro': 'cl100k_base',
                    'gpt-4o': 'o200k_base',
                    'gpt-4': 'cl100k_base',
                    'gpt-3.5-turbo': 'cl100k_base',
                }
                
                encoding_name = encoding_map.get(model_name, 'cl100k_base')
                TokenCounter._encodings[model_name] = tiktoken.get_encoding(encoding_name)
                
            except Exception as e:
                ai_logger.warning(f"Failed to load encoding for {model_name}: {str(e)}")
                # Fallback to cl100k_base
                TokenCounter._encodings[model_name] = tiktoken.get_encoding('cl100k_base')
        
        return TokenCounter._encodings[model_name]
    
    @staticmethod
    def count_tokens(text, model_name='gpt-3.5-turbo'):
        """
        Count tokens in text for a specific model
        
        Args:
            text: Text to count tokens for
            model_name: Model name for encoding
        
        Returns:
            Number of tokens
        """
        try:
            if not text:
                return 0
            
            encoding = TokenCounter.get_encoding(model_name)
            tokens = encoding.encode(str(text))
            return len(tokens)
            
        except Exception as e:
            ai_logger.error(f"Failed to count tokens: {str(e)}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            return len(str(text)) // 4
    
    @staticmethod
    def count_messages_tokens(messages, model_name='gpt-3.5-turbo'):
        """
        Count tokens in a list of messages (for chat APIs)
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_name: Model name for encoding
        
        Returns:
            Number of tokens
        """
        try:
            if not messages:
                return 0
            
            encoding = TokenCounter.get_encoding(model_name)
            
            # Count tokens in all messages
            total_tokens = 0
            
            # Add overhead for message formatting (typically 4 tokens per message)
            total_tokens += len(messages) * 4
            
            for message in messages:
                if isinstance(message, dict):
                    # Count role tokens (typically 1 token)
                    total_tokens += 1
                    
                    # Count content tokens
                    content = message.get('content', '')
                    if content:
                        total_tokens += len(encoding.encode(str(content)))
            
            return total_tokens
            
        except Exception as e:
            ai_logger.error(f"Failed to count message tokens: {str(e)}")
            # Fallback: rough estimate
            total_chars = sum(len(str(msg.get('content', ''))) for msg in messages)
            return total_chars // 4
    
    @staticmethod
    def estimate_cost(input_tokens, output_tokens, model_name='gpt-3.5-turbo'):
        """
        Estimate API cost based on token usage
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model_name: Model name for pricing
        
        Returns:
            Estimated cost in USD
        """
        # Pricing per 1M tokens (as of 2024)
        pricing = {
            'grok-3-fast': {'input': 0.50, 'output': 1.50},  # $0.50/$1.50 per 1M
            'grok-2': {'input': 0.50, 'output': 1.50},
            'grok': {'input': 0.50, 'output': 1.50},
            'gemini-2.5-flash': {'input': 0.075, 'output': 0.30},  # $0.075/$0.30 per 1M
            'gemini-1.5-pro': {'input': 1.50, 'output': 6.00},
            'gemini-pro': {'input': 0.50, 'output': 1.50},
            'gpt-4o': {'input': 2.50, 'output': 10.00},
            'gpt-4': {'input': 30.00, 'output': 60.00},
            'gpt-3.5-turbo': {'input': 0.50, 'output': 1.50},
            'embedding': {'input': 0.02, 'output': 0.0},  # $0.02 per 1M tokens
        }
        
        model_pricing = pricing.get(model_name, pricing.get('gpt-3.5-turbo'))
        
        input_cost = (input_tokens / 1_000_000) * model_pricing['input']
        output_cost = (output_tokens / 1_000_000) * model_pricing['output']
        
        return round(input_cost + output_cost, 6)
    
    @staticmethod
    def get_model_pricing(model_name):
        """
        Get pricing information for a model
        
        Args:
            model_name: Model name
        
        Returns:
            Dictionary with input and output pricing per 1M tokens
        """
        pricing = {
            'grok-3-fast': {'input': 0.50, 'output': 1.50},
            'grok-2': {'input': 0.50, 'output': 1.50},
            'grok': {'input': 0.50, 'output': 1.50},
            'gemini-2.5-flash': {'input': 0.075, 'output': 0.30},
            'gemini-1.5-pro': {'input': 1.50, 'output': 6.00},
            'gemini-pro': {'input': 0.50, 'output': 1.50},
            'gpt-4o': {'input': 2.50, 'output': 10.00},
            'gpt-4': {'input': 30.00, 'output': 60.00},
            'gpt-3.5-turbo': {'input': 0.50, 'output': 1.50},
            'embedding': {'input': 0.02, 'output': 0.0},
        }
        
        return pricing.get(model_name, {'input': 0.0, 'output': 0.0})
