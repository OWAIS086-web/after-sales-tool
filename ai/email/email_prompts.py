"""
Email Prompt Templates
Langchain prompt templates for email-specific queries
"""

from langchain.prompts import (ChatPromptTemplate, HumanMessagePromptTemplate,
                               PromptTemplate, SystemMessagePromptTemplate)

# System prompts for different email query types
SYSTEM_PROMPTS = {
    'general': """You are an intelligent email assistant with access to a user's indexed emails. 
Your role is to help users find information, answer questions, and provide insights based on their email history.

Guidelines:
- Be professional and helpful
- Cite specific emails when referencing information
- If information is not in the emails, clearly state that
- Summarize long information concisely
- Focus on accuracy over speculation""",

    'complaint': """You are a customer service analyst reviewing email complaints and issues.
Your role is to identify, categorize, and prioritize customer complaints from emails.

Guidelines:
- Identify the nature and severity of complaints
- Look for patterns across multiple complaints
- Suggest prioritization based on urgency
- Recommend appropriate actions
- Be empathetic and solution-focused""",

    'automotive': """You are an automotive industry analyst with expertise in vehicle complaints,
service issues, and customer feedback. You help dealerships and manufacturers understand customer concerns.

Guidelines:
- Identify vehicle models and specific issues mentioned
- Categorize problems (engine, transmission, electrical, etc.)
- Assess severity and safety implications
- Look for recurring issues across multiple emails
- Provide actionable insights""",

    'summary': """You are an executive assistant who helps busy professionals quickly understand
their email communications.

Guidelines:
- Provide concise, structured summaries
- Highlight action items and deadlines
- Identify important messages that need attention
- Group related emails by topic
- Use bullet points for clarity""",

    'search': """You are a search assistant helping users find specific information in their emails.

Guidelines:
- Extract precise information related to the query
- Quote relevant parts of emails
- Provide context when necessary
- If multiple emails contain information, compare and synthesize
- Indicate confidence level in findings"""

}


# Human prompt templates
def get_email_query_prompt(query_type: str = 'general') -> ChatPromptTemplate:
    """
    Get chat prompt template for email queries
    
    Args:
        query_type: Type of query (general, complaint, automotive, summary, search)
        
    Returns:
        ChatPromptTemplate instance
    """
    system_prompt = SYSTEM_PROMPTS.get(query_type, SYSTEM_PROMPTS['general'])
    
    system_message = SystemMessagePromptTemplate.from_template(system_prompt)
    
    human_template = """Email Context:
{context}

User Question: {query}

Please provide a helpful response based on the email context above."""
    
    human_message = HumanMessagePromptTemplate.from_template(human_template)
    
    return ChatPromptTemplate.from_messages([system_message, human_message])


# Simple prompt templates for different scenarios
SIMPLE_PROMPTS = {
    'email_search': PromptTemplate(
        input_variables=["context", "query"],
        template="""Based on the following emails, answer this question: {query}

Emails:
{context}

Answer (cite specific emails when possible):"""
    ),
    
    'complaint_analysis': PromptTemplate(
        input_variables=["context", "query"],
        template="""Analyze these customer emails for complaints and issues:

{context}

Question: {query}

Analysis:
1. Type of complaints:
2. Severity level:
3. Common patterns:
4. Recommended actions:"""
    ),
    
    'automotive_analysis': PromptTemplate(
        input_variables=["context", "query"],
        template="""Analyze these automotive customer emails:

{context}

Question: {query}

Analysis:
- Vehicle models mentioned:
- Issues reported:
- Category (engine/transmission/electrical/etc):
- Severity:
- Recommendations:"""
    ),
    
    'email_summary': PromptTemplate(
        input_variables=["context"],
        template="""Summarize the following emails:

{context}

Summary:
• Main Topics:
• Key Action Items:
• Important Dates:
• Notable Senders:
• Priority Level:"""
    ),
    
    'sender_analysis': PromptTemplate(
        input_variables=["context", "sender"],
        template="""Analyze emails from {sender}:

{context}

Summary:
- Number of emails:
- Main topics discussed:
- Tone/sentiment:
- Action items:
- Overall relationship status:"""
    ),
    
    'time_range_summary': PromptTemplate(
        input_variables=["context", "time_range"],
        template="""Summarize emails from {time_range}:

{context}

Summary:
- Total emails analyzed:
- Key topics:
- Important decisions made:
- Pending action items:
- Notable trends:"""
    )
}


# Few-shot examples for better LLM performance
FEW_SHOT_EXAMPLES = [
    {
        'query': 'What complaints have we received about Haval H6?',
        'context': """Email 1:
Subject: Engine Problem - Haval H6
From: john@example.com
My Haval H6 2023 has been experiencing engine overheating issues.

Email 2:
Subject: H6 Transmission Issue
From: sarah@example.com
The transmission in my Haval H6 is making strange noises.""",
        'answer': """Based on the emails, there are two main complaints about Haval H6:

1. **Engine Overheating** (Email from john@example.com)
   - Vehicle: Haval H6 2023
   - Issue: Engine overheating
   - Severity: High (engine-related)

2. **Transmission Noise** (Email from sarah@example.com)
   - Vehicle: Haval H6
   - Issue: Strange noises from transmission
   - Severity: Medium-High (requires inspection)

**Recommendation**: Both issues require immediate technical attention. Engine overheating is critical and should be prioritized."""
    },
    {
        'query': 'Summarize emails from customer Mike Johnson',
        'context': """Email 1:
Subject: Service Appointment Request
From: mike.johnson@email.com
I'd like to schedule a service appointment for my vehicle next week.

Email 2:
Subject: Follow-up on Service
From: mike.johnson@email.com
Thank you for the service. The car is running much better now.""",
        'answer': """**Email Summary - Mike Johnson:**

• **Total Emails**: 2
• **Main Topics**: Service appointment and follow-up
• **Interaction**: 
  - Requested service appointment
  - Provided positive feedback after service
• **Sentiment**: Positive, satisfied customer
• **Status**: Service completed successfully
• **Action Items**: None (issue resolved)"""
    }
]


def format_email_for_context(email_data: dict) -> str:
    """
    Format email data for LLM context
    
    Args:
        email_data: Dictionary with email metadata and content
        
    Returns:
        Formatted string
    """
    return f"""Email:
Subject: {email_data.get('subject', 'No Subject')}
From: {email_data.get('sender', 'Unknown')}
To: {email_data.get('to', 'Unknown')}
Date: {email_data.get('date', 'Unknown')}

{email_data.get('body', 'No content')}
---"""


def get_prompt_for_query_type(query: str) -> str:
    """
    Determine appropriate prompt type based on query content
    
    Args:
        query: User query string
        
    Returns:
        Query type identifier
    """
    query_lower = query.lower()
    
    # Complaint-related keywords
    if any(word in query_lower for word in ['complaint', 'issue', 'problem', 'error', 'bug', 'broken', 'not working']):
        return 'complaint'
    
    # Automotive-related keywords
    if any(word in query_lower for word in ['vehicle', 'car', 'engine', 'transmission', 'brake', 'haval', 'kia', 'model']):
        return 'automotive'
    
    # Summary-related keywords
    if any(word in query_lower for word in ['summarize', 'summary', 'overview', 'list all']):
        return 'summary'
    
    # Search-related keywords
    if any(word in query_lower for word in ['find', 'search', 'look for', 'show me', 'what did']):
        return 'search'
    
    # Default to general
    return 'general'
