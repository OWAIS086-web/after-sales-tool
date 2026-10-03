import json
import time

from middleware.error_handling import handle_ai_errors
from utils.logger import ai_logger, log_ai_activity


class AIService:
    """Service layer for AI-related operations"""
    
    @staticmethod
    @handle_ai_errors
    def get_pipeline_status():
        """Get comprehensive AI pipeline status"""
        try:
            from ai.haval_pipeline import get_pipeline_status
            status = get_pipeline_status()
            
            ai_logger.info("Pipeline status requested")
            return status
            
        except Exception as e:
            ai_logger.error(f"Failed to get pipeline status: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "Pipeline status unavailable"
            }
    
    @staticmethod
    @handle_ai_errors
    def initialize_rag_engine():
        """Initialize RAG engine"""
        try:
            from ai.haval_pipeline import get_rag_engine
            
            start_time = time.time()
            rag_engine = get_rag_engine()
            duration = time.time() - start_time
            
            if rag_engine:
                ai_logger.info(f"RAG engine initialized successfully in {duration:.2f}s")
                log_ai_activity("RAG Engine Initialized", duration=duration)
                return True
            else:
                ai_logger.error("Failed to initialize RAG engine")
                return False
                
        except Exception as e:
            ai_logger.error(f"RAG engine initialization failed: {str(e)}")
            raise
    
    @staticmethod
    @handle_ai_errors
    def process_chat_query(question, mode, company_id, user_id=None, thinking_mode=False):
        """Process chat query through appropriate AI service"""
        
        start_time = time.time()
        
        try:
            if mode == "insights":
                result = AIService._process_insights_query(question, company_id)
            elif mode == "facebook_beta":
                result = AIService._process_facebook_query(question, company_id)
            elif mode == "finance":
                result = AIService._process_finance_query(question, company_id)
            elif mode in ["pakwheels", "whatsapp", "reddit", "lucid", "dealership", "facebook", "cross_platform"]:
                # All these modes use the RAG engine
                result = AIService._process_rag_query(question, mode, company_id, thinking_mode=thinking_mode)
            else:
                raise ValueError(f"Unknown mode: {mode}")
            
            duration = time.time() - start_time
            
            # Log AI activity
            log_ai_activity(
                f"Chat Query - {mode}",
                model=result.get('model_used', 'unknown'),
                tokens=result.get('tokens_used'),
                duration=duration
            )
            
            ai_logger.info(
                f"Chat query processed - Mode: {mode}, User: {user_id}, "
                f"Duration: {duration:.2f}s"
            )
            
            # Return just the answer string for chat controller compatibility
            return result.get('answer', 'Sorry, I could not process your query.')
            
        except Exception as e:
            ai_logger.error(f"Chat query failed - Mode: {mode}, Error: {str(e)}")
            raise
            raise
    
    @staticmethod
    def _process_insights_query(question, company_id):
        """Process insights query using OpenAI"""
        try:
            import app
            openai_client = app.get_openai_client()
            
            if not openai_client:
                raise Exception("OpenAI client not available")
            
            # Get company context
            from config import get_company_config
            try:
                company_config = get_company_config(company_id)
                company_name = company_config.full_name
            except:
                company_name = company_id.title()
            
            # Create insights prompt
            insights_prompt = f"""You are an AI assistant specialized in {company_name} automotive insights and analysis.

User Question: {question}

Provide a comprehensive, analytical response that includes:
1. Direct answer to the question
2. Market insights and trends
3. Competitive analysis if relevant
4. Recommendations or actionable insights

Keep the response informative, professional, and focused on {company_name} and the automotive industry in Pakistan."""

            start_time = time.time()
            response = openai_client.generate(insights_prompt, max_tokens=1000, temperature=0.7)
            duration = time.time() - start_time
            
            return {
                'answer': response.content,
                'model_used': 'openai',
                'tokens_used': len(insights_prompt.split()) + len(response.content.split()),
                'processing_time': duration,
                'source_count': 0
            }
            
        except Exception as e:
            ai_logger.error(f"Insights query failed: {str(e)}")
            raise
    
    @staticmethod
    def _process_rag_query(question, source, company_id, thinking_mode=False):
        """Process RAG query using Haval pipeline"""
        try:
            from ai.haval_pipeline import get_rag_engine
            
            rag_engine = get_rag_engine()
            if not rag_engine:
                raise Exception("RAG engine not available")
            
            # Convert cross_platform mode to None for multi-source retrieval
            rag_source = None if source == "cross_platform" else source
            
            start_time = time.time()
            answer = rag_engine.answer(
                question=question,
                source=rag_source,
                thinking_mode=thinking_mode
            )
            duration = time.time() - start_time
            
            return {
                'answer': answer,
                'platform_data': None,
                'model_used': 'rag_engine',
                'tokens_used': len(question.split()) + len(answer.split()),
                'processing_time': duration,
                'source_count': 0
            }
            
        except Exception as e:
            ai_logger.error(f"RAG query failed: {str(e)}")
            raise
    
    @staticmethod
    def _process_facebook_query(question, company_id):
        """Process Facebook Beta query using processed Facebook data with advanced filtering and insights"""
        try:
            import json
            import os
            import re
            from collections import Counter
            from datetime import datetime, timedelta

            from config.llm_config import get_llm_for_component
            
            start_time = time.time()
            
            # Load Facebook issues data
            facebook_file = os.path.join('data', 'facebook_issues.json')
            if not os.path.exists(facebook_file):
                raise Exception("Facebook data not found. Please process Facebook data first.")
            
            with open(facebook_file, 'r', encoding='utf-8') as f:
                facebook_data = json.load(f)
            
            ai_logger.info(f"Loaded {len(facebook_data)} Facebook issues for analysis")
            
            # Extract specific issues from content using pattern matching
            issue_patterns = {
                'head_unit': ['head unit', 'infotainment', 'screen', 'display', 'reboot', 'restart'],
                'cruise_control': ['cruise control', 'cruise', 'speed control'],
                'lane_assist': ['lane assist', 'lane departure', 'lane keep', 'lane warning'],
                'tpms': ['tpms', 'tire pressure', 'tyre pressure', 'pressure warning'],
                'ac_issues': ['ac', 'air conditioning', 'cooling', 'heating', 'climate'],
                'engine_issues': ['engine', 'motor', 'power', 'acceleration', 'rpm'],
                'brake_issues': ['brake', 'braking', 'abs', 'brake pedal'],
                'transmission': ['transmission', 'gear', 'shifting', 'cvt', 'gearbox'],
                'fuel_issues': ['fuel', 'mileage', 'consumption', 'average', 'efficiency'],
                'electrical': ['electrical', 'battery', 'charging', 'power', 'lights'],
                'suspension': ['suspension', 'shock', 'ride', 'comfort', 'bumpy'],
                'noise_issues': ['noise', 'sound', 'vibration', 'rattling', 'squeaking']
            }
            
            # Categorize issues and apply filters
            categorized_data = []
            issue_counts = Counter()
            date_filter = None
            message_type_filter = None
            specific_issue_filter = None
            
            # Parse query for filters
            query_lower = question.lower()
            
            # Date filters
            # Note: 'recent', 'latest', 'new' keywords now show ALL available data (no 3-day limit)
            # This ensures users can see complete history while still supporting specific date filters
            if any(word in query_lower for word in ['today']):
                date_filter = 'today'
            elif any(word in query_lower for word in ['week', 'weekly', 'last week']):
                date_filter = 'week'
            elif any(word in query_lower for word in ['month', 'monthly', 'last month']):
                date_filter = 'month'
            # 'recent', 'latest', 'new' keywords will use 'all' filter (no date restriction)
            
            # Message type filters
            if any(word in query_lower for word in ['complaint', 'complaints', 'complaining']):
                message_type_filter = 'complaint'
            elif any(word in query_lower for word in ['query', 'queries', 'question', 'questions']):
                message_type_filter = 'query'
            elif any(word in query_lower for word in ['issue', 'issues', 'problem', 'problems']):
                # Map "issues" and "problems" to "complaint" since that's what exists in the data
                message_type_filter = 'complaint'
            
            # Specific issue filters
            for issue_type, keywords in issue_patterns.items():
                if any(keyword in query_lower for keyword in keywords):
                    specific_issue_filter = issue_type
                    break
            
            # Apply filters and categorize
            now = datetime.now()
            for item in facebook_data:
                # Date filtering
                if date_filter:
                    try:
                        post_date = datetime.fromisoformat(item.get('timestamp', '').replace('Z', '+00:00'))
                        if date_filter == 'today' and (now - post_date).days > 1:
                            continue
                        elif date_filter == 'week' and (now - post_date).days > 7:
                            continue
                        elif date_filter == 'month' and (now - post_date).days > 30:
                            continue
                        # 'recent' and 'all' filters show all available data
                    except:
                        pass
                
                # Message type filtering
                if message_type_filter and item.get('message_type', '').lower() != message_type_filter:
                    continue
                
                # Content analysis for issue categorization
                content_lower = item.get('content', '').lower()
                detected_issues = []
                
                for issue_type, keywords in issue_patterns.items():
                    if any(keyword in content_lower for keyword in keywords):
                        detected_issues.append(issue_type)
                        issue_counts[issue_type] += 1
                
                # Specific issue filtering
                if specific_issue_filter and specific_issue_filter not in detected_issues:
                    continue
                
                # Add categorized item
                item_copy = item.copy()
                item_copy['detected_issues'] = detected_issues
                item_copy['primary_issue'] = detected_issues[0] if detected_issues else 'other'
                categorized_data.append(item_copy)
            
            # Limit results but ensure we have good coverage
            if len(categorized_data) > 30:
                # Prioritize: complaints first, then queries, then issues
                complaints = [item for item in categorized_data if item.get('message_type') == 'complaint']
                queries = [item for item in categorized_data if item.get('message_type') == 'query']
                issues = [item for item in categorized_data if item.get('message_type') == 'issue']
                
                relevant_data = complaints[:15] + queries[:10] + issues[:5]
            else:
                relevant_data = categorized_data
            
            ai_logger.info(f"Filtered to {len(relevant_data)} relevant Facebook posts")
            ai_logger.info(f"Applied filters - Date: {date_filter}, Type: {message_type_filter}, Issue: {specific_issue_filter}")
            
            # Generate comprehensive statistics
            total_posts = len(facebook_data)
            filtered_posts = len(relevant_data)
            complaints_count = len([item for item in relevant_data if item.get('message_type') == 'complaint'])
            queries_count = len([item for item in relevant_data if item.get('message_type') == 'query'])
            issues_count = len([item for item in relevant_data if item.get('message_type') == 'issue'])
            
            # Top issues analysis
            top_issues = issue_counts.most_common(10)
            
            # Build context for LLM
            context_parts = []
            for idx, item in enumerate(relevant_data, 1):
                message_type = item.get('message_type', 'unknown')
                emoji = "❗" if message_type == "complaint" else "❓" if message_type == "query" else "⚠️"
                
                detected_issues = item.get('detected_issues', [])
                issues_str = ', '.join(detected_issues) if detected_issues else 'general'
                
                # Format timestamp
                try:
                    post_date = datetime.fromisoformat(item.get('timestamp', '').replace('Z', '+00:00'))
                    formatted_date = post_date.strftime('%Y-%m-%d %H:%M')
                except:
                    formatted_date = item.get('timestamp', 'Unknown')
                
                context_parts.append(
                    f"[FB-{idx}] {emoji} **{item.get('customer_name', 'Unknown')}** ({message_type})\n"
                    f"   Content: {item.get('content', 'N/A')}\n"
                    f"   Issues: {issues_str}\n"
                    f"   Time: {formatted_date}\n"
                    f"   Source: Facebook Group\n"
                )
            
            context = "\n".join(context_parts)
            
            # Build comprehensive system prompt with insights
            system_prompt = f"""You are an AI assistant specializing in Facebook group analysis for Haval Pakistan Owners Group. You have access to comprehensive Facebook data and can provide detailed insights.

**FACEBOOK DATA ANALYSIS:**

**Overall Statistics:**
- Total Facebook posts in database: {total_posts}
- Posts matching current query: {filtered_posts}
- Complaints: {complaints_count}
- Queries: {queries_count} 
- Issues: {issues_count}

**Applied Filters:**
- Date Filter: {date_filter or 'None'}
- Message Type Filter: {message_type_filter or 'None'}
- Specific Issue Filter: {specific_issue_filter or 'None'}

**Top Issues Identified:**
{chr(10).join([f"- {issue.replace('_', ' ').title()}: {count} posts" for issue, count in top_issues[:5]])}

**Facebook Posts Context:**
{context}

**CRITICAL INSTRUCTIONS:**
1. **Facebook Data Authority**: You have comprehensive Facebook group data from Haval Pakistan Owners Group
2. **Issue Insights**: Provide detailed analysis of customer issues, complaints, and queries
3. **Statistical Analysis**: Include relevant statistics and trends from the data
4. **Specific Examples**: Reference actual Facebook posts using [FB-1], [FB-2] format
5. **Actionable Insights**: Provide recommendations based on the data patterns
6. **Never say "I don't have enough data"** - you have {total_posts} Facebook posts to analyze

**Response Structure:**
1. **Executive Summary** - Key findings from Facebook data
2. **Issue Analysis** - Detailed breakdown of problems/queries
3. **Statistics & Trends** - Data-driven insights
4. **Customer Impact** - How issues affect users
5. **Recommendations** - Suggested actions based on data
6. **References** - Cited Facebook posts

**References Format:**
---
### 📋 References (Facebook Group Posts)

**[FB-1]** 👤 Customer Name | 📘 Facebook Group | 🏷️ Message Type | 🕐 Date
💬 *"Post content here"*
🔍 **Issues**: Detected issue categories

**[FB-2]** 👤 Customer Name | 📘 Facebook Group | 🏷️ Message Type | 🕐 Date  
💬 *"Post content here"*
🔍 **Issues**: Detected issue categories

---

**Available Issue Categories:**
- Head Unit/Infotainment Issues
- Cruise Control Problems  
- Lane Assist Issues
- TPMS/Tire Pressure Issues
- AC/Climate Control Issues
- Engine/Performance Issues
- Brake System Issues
- Transmission Issues
- Fuel Efficiency Issues
- Electrical Issues
- Suspension Issues
- Noise/Vibration Issues

Answer the user's question with comprehensive Facebook group insights and data analysis."""
            
            # Get LLM for Facebook analysis with higher token limit for comprehensive analysis
            llm = get_llm_for_component("answer_generation_thinking")  # Use thinking mode for detailed analysis
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ]
            
            # Generate comprehensive response
            response = llm.generate(
                messages,
                max_tokens=4096,  # Higher limit for detailed analysis
                temperature=0.4   # Balanced creativity and accuracy
            )
            
            answer = response.content or "I couldn't analyze the Facebook data. Please try rephrasing your question."
            
            duration = time.time() - start_time
            
            return {
                'answer': answer,
                'platform_data': relevant_data,
                'model_used': 'facebook_insights',
                'tokens_used': len(question.split()) + len(answer.split()),
                'processing_time': duration,
                'source_count': len(relevant_data),
                'total_facebook_posts': total_posts,
                'applied_filters': {
                    'date_filter': date_filter,
                    'message_type_filter': message_type_filter,
                    'specific_issue_filter': specific_issue_filter
                },
                'statistics': {
                    'complaints': complaints_count,
                    'queries': queries_count,
                    'issues': issues_count,
                    'top_issues': dict(top_issues[:10])
                }
            }
            
        except Exception as e:
            ai_logger.error(f"Facebook query failed: {str(e)}")
            raise
    
    @staticmethod
    def _process_finance_query(question, company_id):
        """Process finance query using finance agents and AI"""
        try:
            from config import get_company_config
            from config.llm_config import get_llm_for_component
            
            start_time = time.time()
            
            # Get company context
            try:
                company_config = get_company_config(company_id)
                company_name = company_config.full_name
            except:
                company_name = company_id.title()
            
            # Create finance-focused prompt
            finance_prompt = f"""You are an AI assistant specialized in finance and dealership management for {company_name}.

User Question: {question}

Provide a comprehensive response that includes:
1. Direct answer to the finance/dealership question
2. Relevant financial metrics or insights
3. Best practices or recommendations
4. Any regulatory or compliance considerations if applicable

Focus on automotive finance, loans, payments, customer accounts, vehicle sales, and dealership operations.

Keep the response informative, professional, and finance-focused."""

            # Get LLM for finance analysis
            llm = get_llm_for_component("answer_generation")
            
            # Build messages for LLM
            messages = [
                {"role": "system", "content": finance_prompt},
                {"role": "user", "content": question}
            ]
            
            # Generate response
            response = llm.generate(
                messages,
                max_tokens=1500,
                temperature=0.3  # Lower temperature for more precise financial information
            )
            
            answer = response.content or "I couldn't process your finance query. Please try rephrasing your question."
            
            duration = time.time() - start_time
            
            return {
                'answer': answer,
                'model_used': 'finance_ai',
                'tokens_used': len(question.split()) + len(answer.split()),
                'processing_time': duration,
                'source_count': 0
            }
            
        except Exception as e:
            ai_logger.error(f"Finance query failed: {str(e)}")
            raise
    
    @staticmethod
    @handle_ai_errors
    def get_ai_statistics():
        """Get AI usage statistics"""
        try:
            # This would typically come from a database or metrics store
            # For now, return basic pipeline info
            status = AIService.get_pipeline_status()
            
            stats = {
                'pipeline_status': status.get('status', 'unknown'),
                'vector_store_ready': status.get('vector_store_ready', False),
                'rag_engine_ready': status.get('rag_engine_ready', False),
                'last_updated': status.get('last_updated', 'unknown')
            }
            
            return stats
            
        except Exception as e:
            ai_logger.error(f"Failed to get AI statistics: {str(e)}")
            return {
                'pipeline_status': 'error',
                'error': str(e)
            }
    
    @staticmethod
    @handle_ai_errors
    def classify_query_domain(question, company_id='haval'):
        """Classify query domain using AI"""
        try:
            import app
            from controllers.ai_analysis import classify_query_domain_whatsapp
            
            llm_client = app.get_llm_client()
            if not llm_client:
                # Fallback classification
                return AIService._fallback_classify_query(question)
            
            start_time = time.time()
            classification = classify_query_domain_whatsapp(question, llm_client)
            duration = time.time() - start_time
            
            log_ai_activity(
                "Query Classification",
                model="llm_client",
                duration=duration
            )
            
            return classification
            
        except Exception as e:
            ai_logger.error(f"Query classification failed: {str(e)}")
            return AIService._fallback_classify_query(question)
    
    @staticmethod
    def _fallback_classify_query(question):
        """Fallback query classification without AI"""
        question_lower = question.lower()
        
        # Simple keyword-based classification
        automotive_keywords = [
            'car', 'vehicle', 'haval', 'mg', 'kia', 'engine', 'fuel', 'mileage',
            'price', 'features', 'review', 'problem', 'maintenance', 'service'
        ]
        
        small_talk_keywords = [
            'hello', 'hi', 'thanks', 'thank you', 'bye', 'goodbye', 'how are you'
        ]
        
        if any(keyword in question_lower for keyword in small_talk_keywords):
            return 'small_talk'
        elif any(keyword in question_lower for keyword in automotive_keywords):
            return 'in_domain'
        else:
            return 'out_of_domain'