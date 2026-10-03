"""
Embedding Token Tracker
Tracks token usage for embedding operations
"""

from utils.logger import ai_logger
from models.api_usage import APIUsage
from utils.token_counter import TokenCounter


class EmbeddingTracker:
    """Utility for tracking embedding token usage"""
    
    @staticmethod
    def track_embedding(texts, model_name='text-embedding-3-small', 
                       user_id=None, company_id='haval', operation='Embedding vectors'):
        """
        Track token usage for embedding operation
        
        Args:
            texts: List of texts or single text to embed
            model_name: Embedding model name
            user_id: User ID (optional)
            company_id: Company ID
            operation: Operation description
        """
        try:
            # Normalize to list
            if isinstance(texts, str):
                texts = [texts]
            
            # Count tokens
            total_tokens = 0
            for text in texts:
                tokens = TokenCounter.count_tokens(text, model_name)
                total_tokens += tokens
            
            # Estimate cost
            cost = TokenCounter.estimate_cost(total_tokens, 0, 'embedding')
            
            # Log usage
            APIUsage.log_usage(
                user_id=user_id,
                api_type='embedding',
                model_name=model_name,
                operation=operation,
                input_tokens=total_tokens,
                output_tokens=0,
                cost=cost,
                company_id=company_id
            )
            
            ai_logger.info(f"Embedding tracked: {total_tokens} tokens, cost: ${cost:.6f}")
            
        except Exception as e:
            ai_logger.error(f"Failed to track embedding usage: {str(e)}")
    
    @staticmethod
    def track_batch_embedding(texts_batch, model_name='text-embedding-3-small',
                             user_id=None, company_id='haval', operation='Batch embedding'):
        """
        Track token usage for batch embedding operation
        
        Args:
            texts_batch: List of text lists or single list of texts
            model_name: Embedding model name
            user_id: User ID (optional)
            company_id: Company ID
            operation: Operation description
        """
        try:
            # Flatten if nested
            all_texts = []
            if isinstance(texts_batch, list):
                for item in texts_batch:
                    if isinstance(item, list):
                        all_texts.extend(item)
                    else:
                        all_texts.append(item)
            else:
                all_texts = [texts_batch]
            
            # Count total tokens
            total_tokens = 0
            for text in all_texts:
                tokens = TokenCounter.count_tokens(str(text), model_name)
                total_tokens += tokens
            
            # Estimate cost
            cost = TokenCounter.estimate_cost(total_tokens, 0, 'embedding')
            
            # Log usage
            APIUsage.log_usage(
                user_id=user_id,
                api_type='embedding',
                model_name=model_name,
                operation=operation,
                input_tokens=total_tokens,
                output_tokens=0,
                cost=cost,
                company_id=company_id
            )
            
            ai_logger.info(f"Batch embedding tracked: {len(all_texts)} texts, {total_tokens} tokens, cost: ${cost:.6f}")
            
        except Exception as e:
            ai_logger.error(f"Failed to track batch embedding usage: {str(e)}")
