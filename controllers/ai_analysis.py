"""
AI Analysis Controller - Handles intelligent query analysis and user-specific insights
"""

import json
import re
from typing import Dict, List, Optional

from flask import jsonify, request
from flask_login import current_user, login_required

from models import get_db_connection
from utils.logger import ai_logger, log_function_call


def extract_structured_data(answer: str, platform_data: Optional[List[Dict]], mode: str) -> Dict:
    """
    Extract structured data from chatbot answer including:
    - References (WhatsApp messages, PakWheels posts, Reddit posts with username, timestamp)
    - Charts (already in markdown format)
    - Recommendations/suggestions
    - Tables
    """
    from datetime import datetime
    
    structured = {
        "mode": mode,  # Include mode for reference filtering
        "references": [],
        "charts": [],
        "tables": [],
        "recommendations": [],
        "followups": []
    }
    
    # Extract references directly from RAG engine citation format
    # Pattern: **[1]** 👤 username | 📅 date | 🔗 source [| 📞 phone]
    #          💬 *"snippet"*
    #          🔗 [View Source](url)
    
    citations = []
    
    if "📋 References" in answer:
        # Find the references section
        ref_start = answer.find("📋 References")
        ref_section = answer[ref_start:]
        
        # Split into individual citation blocks
        citation_blocks = re.split(r'\*\*\[(\d+)\]\*\*', ref_section)[1:]
        
        # Process pairs: [number, content]
        for i in range(0, len(citation_blocks), 2):
            if i + 1 < len(citation_blocks):
                ref_num = citation_blocks[i]
                content = citation_blocks[i + 1]
                
                # Parse the content for metadata
                lines = content.strip().split('\n')
                if len(lines) >= 2:
                    # First line: 👤 username | 📅 date | 🔗 source [| 📞 phone]
                    header_line = lines[0].strip()
                    
                    # Extract username, date, source, phone
                    parts = [p.strip() for p in header_line.split('|')]
                    username = parts[0].replace('👤', '').strip() if len(parts) > 0 else 'Unknown'
                    date = parts[1].replace('📅', '').strip() if len(parts) > 1 else 'N/A'
                    source = parts[2].replace('🔗', '').strip() if len(parts) > 2 else 'Unknown'
                    phone = parts[3].replace('📞', '').strip() if len(parts) > 3 else ''
                    
                    # Second line: 💬 *"message"*
                    message_line = lines[1].strip() if len(lines) > 1 else ''
                    message = re.sub(r'💬\s*\*"([^"]+)"\*', r'\1', message_line)
                    
                    # Third line (optional): 🔗 [View Source](url)
                    url = ''
                    if len(lines) > 2:
                        url_match = re.search(r'🔗\s*\[View Source\]\(([^)]+)\)', lines[2])
                        if url_match:
                            url = url_match.group(1)
                    
                    citations.append((ref_num, username, date, source, phone, message, url))
    
    # ai_logger.debug(f"Found {len(citations)} citations using robust parsing")
    
    for citation in citations:
        ref_num, username, date, source, phone, snippet, url = citation
        # ai_logger.debug(f"Processing citation {ref_num}: source='{source}', phone='{phone}', url='{url}'")
        
        # Determine reference type based on source - Check both source text and URL
        source_lower = source.lower()
        is_whatsapp = 'whatsapp' in source_lower or 'wa' in source_lower or phone.strip()
        is_reddit = 'reddit' in source_lower
        is_lucid = 'lucid' in source_lower
        is_pakwheels = 'pakwheels' in source_lower or 'pakwheel' in source_lower
        
        # Also check URL for source type if source text is unclear
        if url:
            url_lower = url.lower()
            if 'reddit.com' in url_lower:
                is_reddit = True
                is_pakwheels = False
                is_lucid = False
            elif 'lucidowners.com' in url_lower:
                is_lucid = True
                is_reddit = False
                is_pakwheels = False
            elif 'pakwheels.com' in url_lower:
                is_pakwheels = True
                is_reddit = False
                is_lucid = False
        
        if is_whatsapp:
            # For WhatsApp references, only include phone number if it's valid
            phone_number = phone.strip() if phone and phone.strip() and phone.strip() != "N/A" else None
            ref_data = {
                "type": "whatsapp",
                "mode": "whatsapp",  # Add mode for filtering
                "id": f"WA-{ref_num}",
                "number": int(ref_num),
                "username": username.strip(),
                "timestamp": date.strip(),
                "message": snippet.strip(),
                "message_type": "Message",
                "source": "WhatsApp"
            }
            # Only add phone fields if we have a valid phone number
            if phone_number:
                ref_data["contact"] = phone_number
                ref_data["phone_number"] = phone_number
            # Only add URL if it exists
            if url and url.strip():
                ref_data["url"] = url.strip()
            structured["references"].append(ref_data)
        elif is_lucid:
            # Lucid Forum reference
            post_number = None
            post_url = url.strip() if url else None
            
            if post_url:
                # Try to extract post number from URL
                post_number_match = re.search(r'/(\d+)/?$', post_url)
                if post_number_match:
                    post_number = post_number_match.group(1)
            
            # If no post number found, use reference number as fallback
            if not post_number:
                post_number = ref_num
            
            ref_data = {
                "type": "lucid",
                "mode": "lucid",  # Add mode for filtering
                "number": int(ref_num),
                "id": post_number,
                "username": username.strip(),
                "date": date.strip(),
                "message": snippet.strip(),
                "post_number": post_number,
                "source": "Lucid Forum"
            }
            
            # Always add URL for Lucid references
            if post_url:
                ref_data["url"] = post_url
            else:
                # Use Lucid base URL if no specific URL provided
                ref_data["url"] = "https://lucidowners.com"
            
            structured["references"].append(ref_data)
        else:
            # PakWheels or Reddit reference
            # Extract post number from URL if available
            post_number = None
            post_url = url.strip() if url else None
            
            if post_url:
                # Try to extract post number from URL
                post_number_match = re.search(r'/(\d+)/?$', post_url)
                if post_number_match:
                    post_number = post_number_match.group(1)
            
            # If no post number found, use reference number as fallback
            if not post_number:
                post_number = ref_num
            
            # Determine reference type based on source
            if is_reddit:
                ref_type = "reddit"
                # For Reddit, only use URL if it's a valid Reddit URL
                if not post_url or 'reddit.com' not in post_url:
                    post_url = None
            else:
                # Default to PakWheels
                ref_type = "pakwheels"
                # For PakWheels, construct URL if not provided
                if not post_url or 'pakwheels.com' not in post_url:
                    # Construct a PakWheels URL using the post number
                    post_url = f"https://www.pakwheels.com/forums/t/haval-h6-dedicated-discussion-owner-fan-club-thread/2198325/{post_number}"
            
            # ai_logger.debug(f"{source.title()} reference {ref_num}: post_number={post_number}, url={post_url}, type={ref_type}")
            
            ref_data = {
                "type": ref_type,
                "mode": ref_type,  # Add mode for filtering
                "number": int(ref_num),
                "id": post_number,
                "username": username.strip(),
                "date": date.strip(),
                "message": snippet.strip(),
                "post_number": post_number,
                "source": source.strip()
            }
            
            # Always add URL for PakWheels references
            if post_url:
                ref_data["url"] = post_url
            
            structured["references"].append(ref_data)
    
    # Extract chart definitions from markdown code blocks
    chart_pattern = r'```chart\s*\n([\s\S]*?)```'
    charts = re.findall(chart_pattern, answer)
    for chart_code in charts:
        try:
            lines = chart_code.strip().split('\n')
            chart_data = {}
            chart_type = 'bar'
            chart_title = 'Chart'
            
            for line in lines:
                line = line.strip()
                if line.startswith('type:'):
                    chart_type = line.split(':', 1)[1].strip()
                elif line.startswith('title:'):
                    chart_title = line.split(':', 1)[1].strip()
                elif line.startswith('data:'):
                    data_str = line.split(':', 1)[1].strip()
                    chart_data = json.loads(data_str)
            
            if chart_data:
                structured["charts"].append({
                    "type": chart_type,
                    "title": chart_title,
                    "data": chart_data
                })
        except Exception:
            continue
    
    # Extract tables from markdown
    table_pattern = r'\|(.+)\|\n\|[-\s|]+\|\n((?:\|.+\|\n?)+)'
    tables = re.findall(table_pattern, answer)
    for header, rows in tables:
        try:
            headers = [h.strip() for h in header.split('|') if h.strip()]
            table_rows = []
            for row in rows.strip().split('\n'):
                if row.strip():
                    cells = [c.strip() for c in row.split('|') if c.strip()]
                    if len(cells) == len(headers):
                        table_rows.append(cells)
            
            if headers and table_rows:
                structured["tables"].append({
                    "headers": headers,
                    "rows": table_rows
                })
        except Exception:
            continue
    
    # Don't generate any default recommendations
    structured["recommendations"] = []
    
    # Don't generate follow-up questions
    structured["followups"] = []
    
    return structured


@log_function_call(ai_logger)
def ai_analyze_query(query, cur):
    """AI-powered query analysis with intelligent responses.

    This is a fallback function used when the main RAG pipeline is not ready.
    It uses the LLM directly to provide helpful responses about automotive topics.
    """
    query_lower = query.lower()

    # Check if this is a "top issues" query
    if any(keyword in query_lower for keyword in ['top 5 issue', 'top issue', 'most common issue', 'top problem', 'top complaint']):
        ai_logger.info(f"Analyzing top issues for query: {query}")

        # Get top issues from database
        try:
            # Query to get top issues from all messages/posts
            cur.execute("""
                SELECT
                    LOWER(SUBSTR(message, 1, 50)) as issue_snippet,
                    COUNT(*) as count
                FROM (
                    SELECT message FROM group_messages
                    UNION ALL
                    SELECT content as message FROM chat
                )
                WHERE message IS NOT NULL AND LENGTH(message) > 10
                GROUP BY LOWER(SUBSTR(message, 1, 50))
                ORDER BY count DESC
                LIMIT 5
            """)

            top_issues = cur.fetchall()

            if top_issues:
                issues_text = "\n".join([f"- {issue[0]}: {issue[1]} occurrences" for issue in top_issues])
                response = f"""**Top 5 Issues Analysis:**

{issues_text}

These are the most frequently mentioned issues in your data. Would you like more details about any specific issue?"""
                return response
        except Exception as e:
            ai_logger.error(f"Error analyzing top issues: {str(e)}")

    # Use LLM to generate a response for the query
    try:
        from config.llm_config import get_llm_for_component

        llm = get_llm_for_component("answer_generation")

        system_prompt = """You are an automotive customer insights assistant for Haval vehicles in Pakistan.
The main data pipeline is currently processing, so you don't have access to specific customer conversations right now.
However, you can still help with:
- General information about Haval vehicles (H6, Jolion, etc.)
- Common automotive topics and terminology
- Suggestions for what types of questions to ask once the system is fully ready

Be helpful and concise. If the question requires specific customer data that you don't have access to,
politely explain that the system is still processing and suggest they try again shortly."""

        user_prompt = f"User question: {query}"

        response = llm.chat(
            system_prompt=system_prompt,
            user_message=user_prompt
        )

        if response:
            ai_logger.info(f"LLM fallback response generated for query: {query[:50]}...")
            return response

    except Exception as e:
        ai_logger.error(f"Error generating LLM fallback response: {str(e)}")

    # Final fallback if LLM also fails
    return (
        "The insight engine is currently processing data. "
        "Please wait a moment and try your question again, or check the pipeline status in settings. "
        f"Your question was: {query}"
    )
