
import secrets
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import jsonify, render_template, request, session
from flask_login import current_user, login_required

from controllers.ai_analysis import extract_structured_data
from models.chat import save_user_chat_history
from utils.logger import (ai_logger, chat_logger, log_ai_activity, log_error,
                          log_function_call, log_user_action)

# Pakistan timezone
PAKISTAN_TZ = ZoneInfo("Asia/Karachi")


import json
from datetime import datetime
from decimal import Decimal


def safe_json_serialize(obj):
    """Safely serialize objects to JSON, handling non-serializable types"""
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, '__dict__'):
        # Convert objects with __dict__ to dictionaries
        return {k: safe_json_serialize(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_json_serialize(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    else:
        # For any other type, convert to string safely
        return str(obj)

def extract_text_from_llm_response(response):
    """Extract text from LLMResponse object or return as string"""
    if hasattr(response, 'content'):
        return response.content
    elif hasattr(response, 'text'):
        return response.text
    elif not isinstance(response, str):
        return str(response)
    return response


@log_function_call(chat_logger)
def chatbot():
    """Chatbot interface - advanced AI copilot chatbot"""
    from config import get_company_config
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    from models.datasource_permissions import DataSourcePermissions

    try:
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.full_name
        company_display = company_config.name
        selected_company = current_user.company_id
        chat_logger.info(f"Chatbot interface accessed by user {current_user.username} for company {company_name}")
    except Exception as e:
        company_config = None
        company_name = current_user.company_id.title()
        company_display = current_user.company_id.title()
        selected_company = current_user.company_id
        log_error(e, f"Failed to get company config for {current_user.company_id}")

    # Get user permissions for data sources using new system
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    
    chat_logger.info(f"Chatbot: User {current_user.username} permissions: {user_permissions}")

    # Check if user is admin
    is_admin = is_admin_user(current_user)

    # Get full config for data sources
    config = get_config()

    # DEBUG: Log what we're sending to template
    chat_logger.warning(f"DEBUG chatbot: user_id={current_user.id}, username={current_user.username}, email={current_user.email if hasattr(current_user, 'email') else 'NO EMAIL'}, permissions={user_permissions}, is_admin={is_admin}")

    log_user_action("Chatbot Access", current_user.id, f"Interface: Basic, Company: {company_name}")

    return render_template("chatbot_advanced.html",
                         company_name=company_name,
                         company_display=company_display,
                         user_company=current_user.company_id,
                         selected_company=selected_company,
                         company_config=company_config,
                         user_permissions=user_permissions,
                         config=config,
                         user=current_user,
                         is_admin=is_admin)


@log_function_call(chat_logger)
def chatbot_advanced():
    """Advanced AI copilot chatbot interface"""
    from config import get_company_config
    from config.config_loader import get_config
    from scheduler.decorators import is_admin_user
    from models.datasource_permissions import DataSourcePermissions

    try:
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.full_name
        company_display = company_config.name  # Fix: use name instead of display_name
        selected_company = current_user.company_id  # Add selected_company for template
        chat_logger.info(f"Advanced chatbot interface accessed by user {current_user.username} for company {company_name}")
    except Exception as e:
        company_config = None  # Set to None when config fails to load
        company_name = current_user.company_id.title()
        company_display = current_user.company_id.title()
        selected_company = current_user.company_id
        log_error(e, f"Failed to get company config for {current_user.company_id}")

    # Get user permissions for data sources using new system
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    
    chat_logger.info(f"Chatbot Advanced: User {current_user.username} permissions: {user_permissions}")

    # Check if user is admin
    is_admin = is_admin_user(current_user)

    # DEBUG: Log what we're sending to template
    chat_logger.warning(f"DEBUG chatbot_advanced: user_id={current_user.id}, username={current_user.username}, email={current_user.email if hasattr(current_user, 'email') else 'NO EMAIL'}, permissions={user_permissions}, is_admin={is_admin}")

    # Get full config for data sources
    config = get_config()

    log_user_action("Chatbot Access", current_user.id, f"Interface: Advanced, Company: {company_name}")

    return render_template("chatbot_advanced.html",
                         company_name=company_name,
                         company_display=company_display,
                         user_company=current_user.company_id,
                         selected_company=selected_company,  # Add selected_company
                         company_config=company_config,      # Add company_config
                         user_permissions=user_permissions,  # Add user permissions
                         config=config,                      # Add config for data sources
                         user=current_user,
                         is_admin=is_admin)


@log_function_call(chat_logger, log_args=False)  # Don't log full query content
def chatbot_query_stream():
    """Process chatbot queries with streaming responses"""
    import json

    from flask import Response
    
    try:
        # Check if user is authenticated
        if not current_user.is_authenticated:
            def auth_error():
                yield f"data: {json.dumps({'content': 'Please log in to use the chatbot.', 'done': True, 'error': 'authentication_required'})}\n\n"
            return Response(auth_error(), mimetype='text/event-stream')

        data = request.get_json(force=True) or {}
        query = (data.get("query") or "").strip()
        mode = (data.get("mode") or "pakwheels").strip().lower()
        thinking_mode = bool(data.get("thinking", False))

        print(f"[Chat] ===== RECEIVED REQUEST =====")
        print(f"[Chat] Mode from request: '{mode}'")
        print(f"[Chat] Query: {query[:100] if query else 'empty'}...")
        
        chat_logger.info(f"Streaming chat query from user {current_user.username}: mode={mode}, thinking={thinking_mode}, thinking_type={type(thinking_mode)}")

        # Check if user has permission for this data source
        from models.datasource_permissions import DataSourcePermissions
        if not DataSourcePermissions.is_source_enabled(current_user.id, mode):
            chat_logger.warning(f"Permission denied: user={current_user.username}, mode={mode}")

            def permission_denied():
                yield f"data: {json.dumps({{'content': '⛔ You do not have access to {mode.upper()}. Please contact your administrator.', 'done': True, 'error': 'permission_denied'}})}\n\n"

            return Response(permission_denied(), mimetype='text/event-stream')

        if not query:
            def empty_response():
                if mode == "insights":
                    yield f"data: {json.dumps({'content': 'Hello! How can I help you today?', 'done': True})}\n\n"
                else:
                    yield f"data: {json.dumps({'content': 'Please ask something about your vehicle, concerns, or the available data.', 'done': True})}\n\n"
            return Response(empty_response(), mimetype='text/event-stream')
        
        # Get user's company
        user_company = current_user.company_id or 'haval'
        
        # Get session ID from payload or Flask session
        session_id = data.get("session_id") or session.get('chat_session_id')
        if not session_id:
            session_id = secrets.token_hex(16)
            session['chat_session_id'] = session_id
        
        def generate_response():
            try:
                # Handle Insights mode with streaming
                if mode == "insights":
                    import app
                    openai_client = app.get_openai_client()
                    if not openai_client:
                        yield f"data: {json.dumps({'content': 'Insights mode is not available.', 'done': True})}\n\n"
                        return
                    
                    try:
                        from models.chat import get_user_chat_history
                        history = get_user_chat_history(current_user.id, mode, session_id)
                        
                        messages = [{"role": "system", "content": "You are ChatGPT, a helpful AI assistant."}]
                        
                        if history:
                            for msg in history[-20:]:
                                if msg.get('role') in ['user', 'assistant']:
                                    content = msg['content'].strip()
                                    if content:
                                        messages.append({"role": msg['role'], "content": content})
                        
                        messages.append({"role": "user", "content": query})
                        
                        # Check if this is a GrokClient or actual OpenAI client
                        if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
                            # This is an actual OpenAI client with streaming support
                            response = openai_client.chat.completions.create(
                                model="gpt-4o",
                                messages=messages,
                                max_tokens=2000,
                                temperature=0.7,
                                stream=True
                            )
                            
                            full_answer = ""
                            for chunk in response:
                                if chunk.choices[0].delta.content:
                                    content = chunk.choices[0].delta.content
                                    full_answer += content
                                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
                        else:
                            # This is a GrokClient, use generate method and simulate streaming
                            prompt_parts = []
                            for msg in messages:
                                if msg['role'] == 'system':
                                    prompt_parts.append(f"System: {msg['content']}")
                                elif msg['role'] == 'user':
                                    prompt_parts.append(f"User: {msg['content']}")
                                elif msg['role'] == 'assistant':
                                    prompt_parts.append(f"Assistant: {msg['content']}")
                            
                            prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
                            llm_response = openai_client.generate(
                                prompt, 
                                max_tokens=2000, 
                                temperature=0.7,
                                user_id=current_user.id,
                                company_id=current_user.company_id,
                                operation='LLM text generation'
                            )
                            full_answer = extract_text_from_llm_response(llm_response)
                            
                            # Simulate streaming by sending words in chunks
                            words = full_answer.split()
                            chunk_size = 8
                            for i in range(0, len(words), chunk_size):
                                chunk = " ".join(words[i:i+chunk_size])
                                if i + chunk_size < len(words):
                                    chunk += " "
                                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                        
                        structured_data = extract_structured_data(full_answer, None, mode)
                        save_user_chat_history(current_user.id, session_id, mode, query, full_answer, structured_data)
                        
                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"
                        
                    except Exception as e:
                        log_error(e, f"OpenAI streaming error")
                        yield f"data: {json.dumps({'content': 'Sorry, there was an error.', 'done': True})}\n\n"
                
                elif mode == "dealership":
                    # DMS (Dealership Management System) Mode - Production-grade Text-to-SQL RAG pipeline
                    try:
                        from config import get_company_config
                        from config.llm_config import get_llm_for_component

                        # Get company configuration
                        company_config = get_company_config(user_company)

                        # Verify DMS is available for this company
                        if not company_config.has_dms:
                            yield f"data: {json.dumps({'content': 'Dealership database is not available for your company. Please contact support.', 'done': True})}\n\n"
                            return

                        # ⭐ SKIP DOMAIN CLASSIFICATION FOR DEALERSHIP MODE
                        # When user explicitly selects "Dealership" mode, ALL queries go to DMS pipeline
                        # DMS pipeline's intent_classifier_dms.py handles meta-operations automatically
                        chat_logger.info(f"✓ Dealership mode selected - sending query directly to DMS pipeline (no domain check)")
                        chat_logger.info(f"✓ Intent classification will be handled by DMS intent_classifier_dms.py")

                        # STEP 2: LOAD CHAT HISTORY FOR FOLLOW-UP SUPPORT
                        from models.chat import get_user_chat_history
                        history = get_user_chat_history(current_user.id, mode, session_id, limit=4)

                        # Convert to DMS pipeline format
                        chat_history = []
                        if history:
                            for msg in history:
                                chat_history.append({
                                    "role": msg.get('role', 'user'),
                                    "content": msg.get('content', '')
                                })
                            chat_logger.info(f"✓ Loaded {len(chat_history)} messages for follow-up support")
                        else:
                            chat_logger.info(f"No chat history found (new session)")

                        # STEP 3: INITIALIZE PIPELINE BASED ON DMS TYPE
                        # Different companies use different DMS systems:
                        # - "production": Real DMS with Tier 0/1/2/3 (ai/dms_engine) - e.g., Haval
                        # - "dummy": Dummy dealership database (ai/dealership_engine) - e.g., Kia
                        dms_type = company_config.dms_type or "production"

                        if dms_type == "production":
                            # Production DMS Pipeline (Haval - SazgarDMSDW)
                            # Use centralized cache manager to prevent model reload
                            chat_logger.info("=" * 80)
                            chat_logger.info("[PIPELINE MANAGER] Importing pipeline_manager...")

                            from ai.pipeline_manager import \
                                get_pipeline_manager

                            chat_logger.info("[PIPELINE MANAGER] Getting manager instance...")
                            pipeline_manager = get_pipeline_manager()

                            chat_logger.info(f"[PIPELINE MANAGER] Requesting DMS pipeline for company={current_user.company_id}, dealer={company_config.dms_dealer_id}")

                            # Get or create cached pipeline (prevents model reload!)
                            dms_pipeline = pipeline_manager.get_dms_pipeline(
                                company_id=current_user.company_id,
                                db_path=company_config.dms_db_path,
                                dealer_id=company_config.dms_dealer_id,
                                db_config=company_config.dms_db_config,  # MSSQL/SQLite config
                                dms_data_source=getattr(company_config, 'dms_data_source', 'mssql'),  # sqlite or mssql pipeline
                                enable_tier0=True,  # Enable Tier 0 hardcoded templates
                                enable_tier1=True,
                                enable_tier2=True,
                                enable_tier3=True,
                                enable_semantic_cache=True,  # Enable semantic caching
                                enable_follow_ups=True,       # Enable follow-up support
                                verbose=False                 # Disable verbose logging
                            )

                            # STEP 4: EXECUTE QUERY through 4-tier pipeline (Tier 0/1/2/3)
                            chat_logger.info(f"Production DMS query from {current_user.username}: {query[:100]}")

                            ai_start_time = time.time()
                            result = dms_pipeline.query(
                                user_query=query,
                                chat_history=chat_history if chat_history else None,  # ⭐ Pass chat history
                                session_id=session_id,  # ⭐ Pass session ID for caching
                                execute=True,
                                format_results=True
                            )
                            ai_duration = time.time() - ai_start_time
                            log_ai_activity(f"DMS Query ({mode})", "DMS Pipeline", None, ai_duration)

                            # Get natural language answer
                            if result.success:
                                answer = result.natural_answer
                                metadata = {
                                    'tier_used': result.tier_used,
                                    'execution_time': result.execution_time,
                                    'sql': result.sql,
                                    'server_time': round(ai_duration, 1)
                                }
                            else:
                                answer = f"Sorry, I couldn't process your query. {result.error_message}"
                                metadata = {}

                        elif dms_type == "dummy":
                            # Dummy Dealership Pipeline (Kia - dealership_kia.db)
                            # Use centralized cache manager for consistency
                            from ai.dealership_engine.dealership_pipeline import \
                                DealershipPipeline
                            from ai.pipeline_manager import \
                                get_pipeline_manager

                            pipeline_manager = get_pipeline_manager()

                            # Get or create cached dummy pipeline
                            dealership_pipeline = pipeline_manager.get_custom_pipeline(
                                pipeline_type="dummy_dealership",
                                company_id=current_user.company_id,
                                config={"db_path": company_config.dms_db_path},
                                factory_func=lambda cfg: DealershipPipeline(db_path=cfg["db_path"])
                            )

                            # STEP 4: EXECUTE QUERY through dummy dealership pipeline
                            chat_logger.info(f"Dummy dealership query from {current_user.username}: {query[:100]}")

                            answer = dealership_pipeline.answer(
                                question=query,
                                chat_history=chat_history if chat_history else None
                            )

                            # Dummy pipeline returns string directly, no metadata
                            metadata = {}

                        else:
                            answer = f"Unknown DMS type: {dms_type}. Please contact support."
                            metadata = {}

                        # STEP 4: STREAM ANSWER TO USER
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                        # STEP 5: SAVE TO CHAT HISTORY
                        structured_data = extract_structured_data(answer, None, mode)
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                        # metadata already set in pipeline-specific blocks above
                        # Extract server_time if present in metadata
                        server_time = metadata.get('server_time') if metadata else None
                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': structured_data, 'metadata': metadata, 'server_time': server_time})}\n\n"

                    except Exception as e:
                        chat_logger.error(f"DMS pipeline error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, dealership query failed. Please try rephrasing your question or contact support.', 'done': True})}\n\n"

                elif mode == "finance":
                    # Finance Mode - Finance/DMS query processing with agents
                    try:
                        from ai.finance.domain_classifier import \
                            FinanceDomainClassifier
                        from ai.finance.format_detector import \
                            FinanceFormatDetector
                        from ai.finance.query_reformulator import \
                            FinanceQueryReformulator
                        from config.llm_config import get_llm_for_component
                        from services.ai_service import AIService

                        chat_logger.info(f"Finance query from {current_user.username}: {query[:100]}")

                        # STEP 1: Domain Classification
                        llm_client = get_llm_for_component('finance_domain_classifier')
                        domain_classifier = FinanceDomainClassifier(llm_client=llm_client)
                        domain_result = domain_classifier.classify(query)

                        if not domain_result['is_in_domain']:
                            # Out-of-domain query - check if it's small talk or completely unrelated
                            domain_type = domain_result.get('domain', 'out_of_domain')
                            
                            if domain_type == 'small_talk':
                                # Handle greetings politely
                                answer = "Hello! I can help you with finance database queries about customers, loans, accounts, transactions, and vehicle financing. What would you like to know?"
                            else:
                                # Out-of-domain topic
                                answer = "OUT_OF_DOMAIN - This question is not related to the finance database. I can only answer questions about customers, loans, accounts, transactions, investments, and credit cards. Please ask a finance-related question."
                            
                            yield f"data: {json.dumps({'content': answer, 'done': True})}\n\n"
                            save_user_chat_history(current_user.id, session_id, mode, query, answer)
                            return

                        # STEP 2: Query Reformulation
                        reformulator = FinanceQueryReformulator(llm_client=llm_client)
                        reformulation_result = reformulator.reformulate(query)
                        reformulated_query = reformulation_result['reformulated_query']
                        
                        if reformulation_result['changed']:
                            chat_logger.info(f"Query reformulated: {query} -> {reformulated_query}")

                        # STEP 3: Format Detection
                        format_detector = FinanceFormatDetector(llm_client=llm_client)
                        format_result = format_detector.detect(reformulated_query)
                        chat_logger.info(f"Format detected: {format_result['query_type']} -> {format_result['response_format']}")

                        # STEP 4: Process query with finance system
                        # Use Finance Pipeline for database queries
                        try:
                            from ai.finance.finance_pipeline import \
                                get_finance_pipeline

                            # Get finance pipeline (uses config.yaml for DB path)
                            finance_pipeline = get_finance_pipeline()
                            
                            # Execute query through SQL agent
                            result = finance_pipeline.query(query, reformulated_query)
                            
                            if result['success']:
                                answer = result['answer']
                                sql_query = result['sql']
                            else:
                                answer = result['answer']  # Error message
                                sql_query = None
                                
                        except Exception as pipeline_error:
                            chat_logger.error(f"Finance pipeline error: {pipeline_error}")
                            # Fallback to AI service if pipeline fails
                            answer = AIService.process_chat_query(reformulated_query, mode, user_company)
                            sql_query = None

                        # Add metadata about processing
                        processing_info = f"\n\n*Processed as {format_result['query_type']} query (confidence: {domain_result['confidence']:.0%})*"
                        if sql_query:
                            processing_info += f"\n*SQL: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}*"
                        answer += processing_info

                        # Stream answer in chunks
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                        # Save to chat history
                        save_user_chat_history(current_user.id, session_id, mode, query, answer)
                        structured_data = extract_structured_data(answer, None, mode)

                        # Add agent metadata
                        metadata = {
                            'domain': domain_result['domain'],
                            'confidence': domain_result['confidence'],
                            'query_type': format_result['query_type'],
                            'response_format': format_result['response_format'],
                            'reformulated': reformulation_result['changed']
                        }

                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data), 'metadata': metadata})}\n\n"

                    except Exception as e:
                        chat_logger.error(f"Finance mode error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, finance query failed. Please try rephrasing your question.', 'done': True})}\n\n"

                elif mode == "supplychain":
                    # Supply Chain Mode - Supply chain query processing with agents
                    try:
                        from ai.SupplyChain.domain_classifier import \
                            SupplyChainDomainClassifier
                        from ai.SupplyChain.format_detector import \
                            SupplyChainFormatDetector
                        from ai.SupplyChain.query_reformulator import \
                            SupplyChainQueryReformulator
                        from config.llm_config import get_llm_for_component
                        from services.ai_service import AIService

                        chat_logger.info(f"Supply Chain query from {current_user.username}: {query[:100]}")

                        # STEP 1: Domain Classification
                        llm_client = get_llm_for_component('supplychain_domain_classifier')
                        domain_classifier = SupplyChainDomainClassifier(llm_client=llm_client)
                        domain_result = domain_classifier.classify(query)

                        if not domain_result['is_in_domain']:
                            # Out-of-domain query - check if it's small talk or completely unrelated
                            domain_type = domain_result.get('domain', 'out_of_domain')
                            
                            if domain_type == 'small_talk':
                                # Handle greetings politely
                                answer = "Hello! I can help you with supply chain queries about suppliers, parts, purchase orders, inventory, and shipments. What would you like to know?"
                            else:
                                # Out-of-domain topic
                                answer = "OUT_OF_DOMAIN - This question is not related to the supply chain database. I can only answer questions about suppliers, parts, purchase orders, inventory, and shipments. Please ask a supply chain-related question."
                            
                            yield f"data: {json.dumps({'content': answer, 'done': True})}\n\n"
                            save_user_chat_history(current_user.id, session_id, mode, query, answer)
                            return

                        # STEP 2: Query Reformulation
                        reformulator = SupplyChainQueryReformulator(llm_client=llm_client)
                        reformulation_result = reformulator.reformulate(query)
                        reformulated_query = reformulation_result.get('reformulated_query') or query

                        if reformulation_result.get('is_changed'):
                            chat_logger.info(f"Query reformulated: {query} -> {reformulated_query}")

                        # STEP 3: Format Detection
                        format_detector = SupplyChainFormatDetector(llm_client=llm_client)
                        format_result = format_detector.detect(reformulated_query)
                        chat_logger.info(f"Format detected: {format_result['query_type']} -> {format_result['response_format']}")

                        # STEP 4: Process query with supply chain system
                        # Use Supply Chain Pipeline for database queries
                        try:
                            from ai.SupplyChain.supplychain_pipeline import \
                                get_supplychain_pipeline

                            # Get supply chain pipeline (uses config.yaml for DB path)
                            supplychain_pipeline = get_supplychain_pipeline()
                            
                            # Execute query through SQL agent
                            result = supplychain_pipeline.query(query, reformulated_query)
                            
                            if result['success']:
                                answer = result['answer']
                                sql_query = result['sql']
                            else:
                                answer = result['answer']  # Error message
                                sql_query = None
                                
                        except Exception as pipeline_error:
                            chat_logger.error(f"Supply Chain pipeline error: {pipeline_error}")
                            # Fallback to AI service if pipeline fails
                            answer = AIService.process_chat_query(reformulated_query, mode, user_company)
                            sql_query = None

                        # Add metadata about processing
                        processing_info = f"\n\n*Processed as {format_result['query_type']} query (confidence: {domain_result['confidence']:.0%})*"
                        if sql_query:
                            processing_info += f"\n*SQL: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}*"
                        answer += processing_info

                        # Stream answer in chunks
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                        # Save to chat history
                        save_user_chat_history(current_user.id, session_id, mode, query, answer)
                        structured_data = extract_structured_data(answer, None, mode)

                        # Add agent metadata
                        metadata = {
                            'domain': domain_result['domain'],
                            'confidence': domain_result['confidence'],
                            'query_type': format_result['query_type'],
                            'response_format': format_result['response_format'],
                            'reformulated': reformulation_result.get('is_changed', False)
                        }

                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data), 'metadata': metadata})}\n\n"

                    except Exception as e:
                        chat_logger.error(f"Supply Chain mode error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, supply chain query failed. Please try rephrasing your question.', 'done': True})}\n\n"

                elif mode == "facebook_beta":
                    # Facebook Beta Mode - Process Facebook group data with advanced filtering
                    try:
                        from services.ai_service import AIService

                        # Get answer from AI service Facebook query processor
                        chat_logger.info(f"Facebook Beta query from {current_user.username}: {query[:100]}")
                        answer = AIService.process_chat_query(query, mode, user_company)

                        # Stream answer in chunks
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                        # Save to chat history
                        structured_data = extract_structured_data(answer, None, mode)
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"

                    except Exception as e:
                        chat_logger.error(f"Facebook Beta processing error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, Facebook Beta query failed. Please try rephrasing your question.', 'done': True})}\n\n"
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                        # Save to chat history
                        structured_data = extract_structured_data(answer, None, mode)
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"

                    except Exception as e:
                        chat_logger.error(f"Dealership pipeline error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, dealership query failed. Please try rephrasing your question.', 'done': True})}\n\n"

                elif mode == "facebook_beta":
                    # Facebook Beta Mode - Process Facebook group data with advanced filtering
                    try:
                        from services.ai_service import AIService

                        # Get answer from AI service Facebook query processor
                        chat_logger.info(f"Facebook Beta query from {current_user.username}: {query[:100]}")
                        answer = AIService.process_chat_query(query, mode, user_company)

                        # Stream answer in chunks
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                        # Save to chat history
                        structured_data = extract_structured_data(answer, None, mode)
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"

                    except Exception as e:
                        chat_logger.error(f"Facebook Beta processing error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, Facebook Beta query failed. Please try rephrasing your question.', 'done': True})}\n\n"

                elif mode == "email":
                    # Email Mode - Query emails using RAG with Gmail OAuth
                    print(f"[Chat] ======== ENTERING EMAIL MODE ========")
                    print(f"[Chat] Query: {query[:100]}")
                    try:
                        import os

                        from flask import session

                        from ai.email.email_rag_handler import EmailRAGHandler
                        from ai.email.email_vector_store import \
                            EmailVectorStore
                        from ai.email.gmail_oauth_service import \
                            GmailOAuthService
                        
                        chat_logger.info(f"Email query from {current_user.username}: {query[:100]}")
                        ai_start_time = time.time()
                        
                        # Check if user is authenticated with Gmail
                        client_id = os.getenv('GOOGLE_CLIENT_ID')
                        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
                        
                        if not client_id or not client_secret:
                            yield f"data: {json.dumps({'content': 'Gmail OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env', 'done': True})}\n\n"
                            return
                        
                        # Get vector store
                        vector_store = EmailVectorStore()
                        
                        # Check if there are any indexed emails
                        stats = vector_store.get_stats()
                        print(f"[Email Mode] Vector store stats: {stats}")
                        
                        if stats.get('total_indexed', 0) == 0:
                            no_email_msg = 'No emails indexed yet. Please click "Sync Emails" button in the Email panel to index your emails first.'
                            yield f"data: {json.dumps({'content': no_email_msg, 'done': True})}\n\n"
                            return
                        
                        # Initialize RAG handler
                        api_key = os.getenv('XAI_API_KEY')
                        llm_provider = 'grok'
                        
                        if not api_key:
                            api_key = os.getenv('OPENAI_API_KEY')
                            llm_provider = 'openai'
                        
                        if not api_key:
                            api_key = os.getenv('GOOGLE_API_KEY')
                            llm_provider = 'gemini'
                        
                        if not api_key:
                            yield f"data: {json.dumps({'content': 'No LLM API key configured. Please set XAI_API_KEY or OPENAI_API_KEY in .env', 'done': True})}\n\n"
                            return
                        
                        rag_handler = EmailRAGHandler(
                            vector_store=vector_store,
                            llm_provider=llm_provider,
                            api_key=api_key
                        )
                        
                        # Query emails
                        result = rag_handler.query(query, n_results=5)
                        ai_duration = time.time() - ai_start_time
                        
                        if not result.get('success', False):
                            error_msg = f"Error querying emails: {result.get('error', 'Unknown error')}"
                            yield f"data: {json.dumps({'content': error_msg, 'done': True})}\n\n"
                            return
                        
                        answer = result.get('answer', 'No answer generated.')
                        sources = result.get('sources', [])
                        
                        # Build email sources for display (pass through all fields from RAG handler)
                        email_references = []
                        for idx, source in enumerate(sources):
                            email_id = source.get('email_id', '')
                            thread_id = source.get('thread_id', '')
                            gmail_link = source.get('gmail_link', '') or (f"https://mail.google.com/mail/u/0/#inbox/{thread_id}" if thread_id else "")
                            
                            email_references.append({
                                'id': f'email_{idx}',
                                'type': 'email',
                                'source': 'email',
                                'title': source.get('title', 'No Subject'),
                                'subject': source.get('title', 'No Subject'),  # Alias for frontend
                                'sender': source.get('sender', 'Unknown'),
                                'sender_name': source.get('sender_name', source.get('sender', 'Unknown').split('<')[0].strip() if '<' in source.get('sender', '') else source.get('sender', 'Unknown')),
                                'sender_email': source.get('sender_email', ''),
                                'date': source.get('date', 'Unknown'),
                                'time': source.get('time', ''),
                                'snippet': source.get('snippet', ''),
                                'body': source.get('body', ''),  # Full email content for "View Email"
                                'email_id': email_id,
                                'thread_id': thread_id,
                                'gmail_link': gmail_link,  # Direct link to open in Gmail
                                'platform': 'Gmail',
                                'relevance_score': source.get('relevance_score', 0)
                            })
                        
                        # Stream answer in chunks
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                        
                        # Build structured data with email references
                        structured_data = {
                            'references': email_references,
                            'mode': 'email',
                            'source_count': len(sources)
                        }
                        
                        # Save to chat history
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
                        
                        # Log AI activity
                        log_ai_activity("Email Query", "Email RAG", None, ai_duration)
                        
                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data), 'server_time': round(ai_duration, 1)})}\n\n"
                    
                    except Exception as e:
                        chat_logger.error(f"Email mode error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        yield f"data: {json.dumps({'content': f'Sorry, email query failed: {str(e)}', 'done': True})}\n\n"

                else:
                    # RAG-based modes (PakWheels, WhatsApp)
                    print(f"[Chat] ======== ENTERING RAG MODE (not email) ========")
                    print(f"[Chat] Mode received: '{mode}'")
                    print(f"[Chat] Query: {query[:100]}")
                    try:
                        from ai.haval_pipeline import get_rag_engine
                        rag = get_rag_engine(company_id=user_company)

                        if rag is None:
                            yield f"data: {json.dumps({'content': 'The AI system is not ready.', 'done': True})}\n\n"
                            return

                        from models.chat import get_user_chat_history
                        history = get_user_chat_history(current_user.id, mode, session_id)
                        if len(history) == 0:
                            history = None

                        # Track RAG engine processing time
                        ai_start_time = time.time()
                        # Convert cross_platform mode to None for multi-source retrieval
                        source_param = None if mode == "cross_platform" else mode
                        answer = rag.answer(query, history=history, thinking_mode=thinking_mode, source=source_param, session_id=session_id, user_id=current_user.id)
                        ai_duration = time.time() - ai_start_time

                        # Extract structured data FIRST (before removing references)
                        structured_data = extract_structured_data(answer, None, mode)

                        # Clean answer for display (remove references section only, keep charts)
                        import re
                        clean_answer = re.sub(r'---\s*\n### 📋 References[\s\S]*?---', '', answer)
                        clean_answer = re.sub(r'📋 References[\s\S]*$', '', clean_answer)
                        clean_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_answer).strip()

                        # Stream cleaned answer in chunks
                        words = clean_answer.split()
                        chunk_size = 10  # Larger chunks for faster streaming
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                            # No delay for maximum speed

                        # Save original answer to chat history (with references for context)
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                        # Send final message with server-side timing (in seconds, 1 decimal place)
                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data), 'server_time': round(ai_duration, 1)})}\n\n"

                    except Exception as e:
                        log_error(e, f"RAG streaming error")
                        yield f"data: {json.dumps({'content': 'Sorry, there was an error.', 'done': True})}\n\n"
                    
            except Exception as e:
                log_error(e, f"Streaming error")
                yield f"data: {json.dumps({'content': 'Sorry, I encountered an error.', 'done': True})}\n\n"
        
        return Response(generate_response(), mimetype='text/event-stream')
        
    except Exception as e:
        log_error(e, f"Request processing error")
        def error_response():
            yield f"data: {json.dumps({'content': 'Sorry, I could not generate a response.', 'done': True})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')


@log_function_call(chat_logger, log_args=False)  # Don't log full query content
def chatbot_query_fast():
    """Super fast chatbot query with minimal processing and immediate streaming"""
    import json

    from flask import Response
    
    try:
        data = request.get_json(force=True) or {}
        query = (data.get("query") or "").strip()
        mode = (data.get("mode") or "pakwheels").strip().lower()
        thinking_mode = False  # Force non-thinking mode for speed
        
        chat_logger.info(f"Fast chat query from user {current_user.username}: mode={mode}")
        
        if not query:
            def empty_response():
                if mode == "insights":
                    yield f"data: {json.dumps({'content': 'Hello! How can I help you today?', 'done': True})}\n\n"
                else:
                    yield f"data: {json.dumps({'content': 'Please ask something about your vehicle, concerns, or the available data.', 'done': True})}\n\n"
            return Response(empty_response(), mimetype='text/event-stream')
        
        # Get user's company
        user_company = current_user.company_id or 'haval'
        
        # Get session ID from payload or Flask session
        session_id = data.get("session_id") or session.get('chat_session_id')
        if not session_id:
            session_id = secrets.token_hex(16)
            session['chat_session_id'] = session_id
        
        def generate_fast_response():
            try:
                start_time = time.time()
                
                # Handle Insights mode with streaming
                if mode == "insights":
                    import app
                    openai_client = app.get_openai_client()
                    if not openai_client:
                        yield f"data: {json.dumps({'content': 'Insights mode is not available. OpenAI integration is required.', 'done': True})}\n\n"
                        return
                    
                    try:
                        # Minimal history for speed (only last 4 messages)
                        from models.chat import get_user_chat_history
                        history = get_user_chat_history(current_user.id, mode, session_id, limit=4)
                        
                        # Build minimal messages for speed
                        messages = [
                            {"role": "system", "content": "You are a helpful AI assistant. Provide clear, concise responses."}
                        ]
                        
                        if history:
                            for msg in history[-4:]:  # Only last 4 messages for speed
                                if msg.get('role') in ['user', 'assistant']:
                                    content = msg['content'].strip()
                                    if content:
                                        messages.append({"role": msg['role'], "content": content})
                        
                        messages.append({"role": "user", "content": query})
                        
                        # Check if this is a GrokClient or actual OpenAI client
                        if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
                            # This is an actual OpenAI client with streaming support
                            response = openai_client.chat.completions.create(
                                model="gpt-4o-mini",  # Use faster mini model
                                messages=messages,
                                max_tokens=1000,  # Reduced for speed
                                temperature=0.3,  # Lower for faster, more focused responses
                                stream=True
                            )
                            
                            full_answer = ""
                            for chunk in response:
                                if chunk.choices[0].delta.content:
                                    content = chunk.choices[0].delta.content
                                    full_answer += content
                                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
                        else:
                            # This is a GrokClient, use generate method and simulate streaming
                            prompt_parts = []
                            for msg in messages:
                                if msg['role'] == 'system':
                                    prompt_parts.append(f"System: {msg['content']}")
                                elif msg['role'] == 'user':
                                    prompt_parts.append(f"User: {msg['content']}")
                                elif msg['role'] == 'assistant':
                                    prompt_parts.append(f"Assistant: {msg['content']}")
                            
                            prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
                            llm_response = openai_client.generate(
                                prompt, 
                                max_tokens=1000, 
                                temperature=0.3,
                                user_id=current_user.id,
                                company_id=current_user.company_id,
                                operation='LLM text generation'
                            )
                            full_answer = extract_text_from_llm_response(llm_response)
                            
                            # Simulate streaming by sending words in chunks
                            words = full_answer.split()
                            chunk_size = 8
                            for i in range(0, len(words), chunk_size):
                                chunk = " ".join(words[i:i+chunk_size])
                                if i + chunk_size < len(words):
                                    chunk += " "
                                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                        
                        # Save to chat history (async to not block response)
                        try:
                            structured_data = extract_structured_data(full_answer, None, mode)
                            save_user_chat_history(current_user.id, session_id, mode, query, full_answer, structured_data)
                        except:
                            pass  # Don't let saving block the response
                        
                        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                        
                    except Exception as e:
                        log_error(e, f"Fast OpenAI streaming error for user {current_user.username}")
                        yield f"data: {json.dumps({'content': 'Sorry, there was an error. Please try again.', 'done': True})}\n\n"
                
                else:
                    # RAG-based modes with speed optimizations
                    try:
                        # Quick status check without detailed validation
                        from ai.haval_pipeline import get_rag_engine
                        rag = get_rag_engine(company_id=user_company)
                        
                        if rag is None:
                            yield f"data: {json.dumps({'content': 'The AI system is not ready yet. Please try again in a moment.', 'done': True})}\n\n"
                            return
                        
                        # Minimal history for speed
                        from models.chat import get_user_chat_history
                        history = get_user_chat_history(current_user.id, mode, session_id, limit=4)
                        if len(history) == 0:
                            history = None
                        
                        # Use RAG engine with speed optimizations
                        ai_start_time = time.time()

                        # Convert cross_platform mode to None for multi-source retrieval
                        source_param = None if mode == "cross_platform" else mode
                        # Force non-thinking mode and minimal processing
                        answer = rag.answer(query, history=history, thinking_mode=False, source=source_param, session_id=session_id, user_id=current_user.id)
                        
                        # Stream the answer in chunks for immediate feedback
                        words = answer.split()
                        chunk_size = 8  # Larger chunks for faster streaming
                        
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                            # No delay for maximum speed
                        
                        # Save to chat history (async to not block response)
                        try:
                            structured_data = extract_structured_data(answer, None, mode)
                            save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
                        except:
                            pass  # Don't let saving block the response
                        
                        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"
                        
                    except Exception as e:
                        log_error(e, f"Fast RAG error for user {current_user.username}")
                        yield f"data: {json.dumps({'content': 'Sorry, there was an error processing your request.', 'done': True})}\n\n"
                    
            except Exception as e:
                log_error(e, f"Fast streaming error for user {current_user.username}")
                yield f"data: {json.dumps({'content': 'Sorry, I encountered an error.', 'done': True})}\n\n"
        
        return Response(generate_fast_response(), mimetype='text/event-stream')
        
    except Exception as e:
        log_error(e, f"Fast request processing error for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        def error_response():
            yield f"data: {json.dumps({'content': 'Sorry, I could not generate a response.', 'done': True})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')
    """Process chatbot queries with streaming responses for super fast experience"""
    import json

    from flask import Response
    
    try:
        data = request.get_json(force=True) or {}
        query = (data.get("query") or "").strip()
        mode = (data.get("mode") or "pakwheels").strip().lower()
        thinking_mode = bool(data.get("thinking", False))
        
        chat_logger.info(f"Streaming chat query from user {current_user.username}: mode={mode}, thinking={thinking_mode}")
        
        if not query:
            def empty_response():
                if mode == "insights":
                    yield f"data: {json.dumps({'content': 'Hello! How can I help you today?', 'done': True})}\n\n"
                else:
                    yield f"data: {json.dumps({'content': 'Please ask something about your vehicle, concerns, or the available data.', 'done': True})}\n\n"
            return Response(empty_response(), mimetype='text/event-stream')
        
        # Get user's company
        user_company = current_user.company_id or 'haval'
        
        # Get session ID from payload or Flask session
        session_id = data.get("session_id") or session.get('chat_session_id')
        if not session_id:
            session_id = secrets.token_hex(16)
            session['chat_session_id'] = session_id
        
        def generate_response():
            try:
                start_time = time.time()
                
                # Handle Insights mode with streaming
                if mode == "insights":
                    import app
                    openai_client = app.get_openai_client()
                    if not openai_client:
                        yield f"data: {json.dumps({'content': 'Insights mode is not available. OpenAI integration is required.', 'done': True})}\n\n"
                        return
                    
                    try:
                        # Get chat history
                        from models.chat import get_user_chat_history
                        history = get_user_chat_history(current_user.id, mode, session_id)
                        
                        # Build messages
                        messages = [
                            {"role": "system", "content": "You are ChatGPT, a helpful AI assistant created by OpenAI. Provide clear, informative, and conversational responses. Be helpful, harmless, and honest."}
                        ]
                        
                        if history:
                            recent_history = history[-20:]
                            for msg in recent_history:
                                if msg.get('role') in ['user', 'assistant']:
                                    content = msg['content'].strip()
                                    if content:
                                        messages.append({"role": msg['role'], "content": content})
                        
                        messages.append({"role": "user", "content": query})
                        
                        # Check if this is a GrokClient or actual OpenAI client
                        ai_start_time = time.time()
                        if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
                            # This is an actual OpenAI client with streaming support
                            response = openai_client.chat.completions.create(
                                model="gpt-4o",
                                messages=messages,
                                max_tokens=2000,
                                temperature=0.7,
                                stream=True  # Enable streaming
                            )
                            
                            full_answer = ""
                            for chunk in response:
                                if chunk.choices[0].delta.content:
                                    content = chunk.choices[0].delta.content
                                    full_answer += content
                                    yield f"data: {json.dumps({'content': content, 'done': False})}\n\n"
                        else:
                            # This is a GrokClient, use generate method and simulate streaming
                            prompt_parts = []
                            for msg in messages:
                                if msg['role'] == 'system':
                                    prompt_parts.append(f"System: {msg['content']}")
                                elif msg['role'] == 'user':
                                    prompt_parts.append(f"User: {msg['content']}")
                                elif msg['role'] == 'assistant':
                                    prompt_parts.append(f"Assistant: {msg['content']}")
                            
                            prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
                            llm_response = openai_client.generate(
                                prompt, 
                                max_tokens=2000, 
                                temperature=0.7,
                                user_id=current_user.id,
                                company_id=current_user.company_id,
                                operation='LLM text generation'
                            )
                            full_answer = extract_text_from_llm_response(llm_response)
                            
                            # Simulate streaming by sending words in chunks
                            words = full_answer.split()
                            chunk_size = 8
                            for i in range(0, len(words), chunk_size):
                                chunk = " ".join(words[i:i+chunk_size])
                                if i + chunk_size < len(words):
                                    chunk += " "
                                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                        
                        ai_duration = time.time() - ai_start_time
                        
                        # Extract structured data
                        structured_data = extract_structured_data(full_answer, None, mode)
                        
                        # Save to chat history
                        save_user_chat_history(current_user.id, session_id, mode, query, full_answer, structured_data)
                        
                        log_ai_activity("Insights Query", "OpenAI", None, ai_duration)
                        
                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"
                        
                    except Exception as e:
                        log_error(e, f"OpenAI streaming error for user {current_user.username}")
                        yield f"data: {json.dumps({'content': 'Sorry, the Insights mode encountered an error. Please try again.', 'done': True})}\n\n"
                
                elif mode == "cross_platform":
                    # Cross-Platform mode - query all sources using multi-source RAG
                    try:
                        from ai.haval_pipeline import (get_pipeline_status,
                                                       get_rag_engine)
                        from config import get_company_config

                        # Check if pipeline is ready
                        status = get_pipeline_status()
                        if status.get("status") != "ready":
                            status_msg = status.get("status", "unknown")
                            yield f"data: {json.dumps({'content': f'The insight engine is still processing (status: {status_msg}). Please wait until ready.', 'done': True})}\n\n"
                            return
                        
                        # Get RAG engine
                        rag = get_rag_engine(company_id=user_company)
                        if rag is None:
                            yield f"data: {json.dumps({'content': 'Cross-platform search is not available yet.', 'done': True})}\n\n"
                            return
                        
                        # Debug: Check what stores are available
                        print(f"[Chat] Cross-Platform Mode - Available stores: {list(rag.vector_stores.keys())}")
                        
                        # Execute multi-source query (source=None enables multi-source mode)
                        ai_start_time = time.time()
                        answer = rag.answer(
                            question=query,
                            history=chat_history,
                            thinking_mode=thinking_mode,
                            source=None,  # Multi-source mode - queries ALL sources
                            session_id=session_id,
                            user_id=current_user.id
                        )
                        
                        # Stream the answer
                        words = answer.split()
                        chunk_size = 10
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                        
                        ai_duration = time.time() - ai_start_time
                        
                        # Extract sources from answer (if citations are included)
                        sources = []
                        if "## 📚 References" in answer or "## References" in answer:
                            # Parse citations if available
                            sources = ["Multi-source: PakWheels, WhatsApp, Reddit"]
                        
                        # Format structured data
                        structured_data = {
                            "sources": sources,
                            "platform_count": len([s for s in rag.vector_stores.values() if s and hasattr(s, 'blocks_by_id') and len(s.blocks_by_id) > 0])
                        }
                        
                        # Save to chat history
                        save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
                        
                        yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"
                        
                    except Exception as e:
                        log_error(e, f"Cross-platform streaming error for user {current_user.username}")
                        yield f"data: {json.dumps({'content': 'Sorry, the cross-platform search encountered an error. Please try again.', 'done': True})}\n\n"
                
                else:
                    # RAG-based modes with optimized processing
                    try:
                        from ai.haval_pipeline import (get_pipeline_status,
                                                       get_rag_engine)
                        status = get_pipeline_status()
                    except Exception as e:
                        yield f"data: {json.dumps({'content': 'The AI system is not available. Please try again later.', 'done': True})}\n\n"
                        return
                        
                    if status.get("status") != "ready":
                        status_msg = status.get("status", "unknown")
                        yield f"data: {json.dumps({'content': f'The insight engine is still processing (status: {status_msg}). Please wait until ready.', 'done': True})}\n\n"
                        return
                    
                    # Get company config and RAG engine
                    from config import get_company_config
                    company_config = get_company_config(user_company)
                    
                    # Validate source availability
                    if mode == "whatsapp" and not company_config.has_whatsapp:
                        company_name = company_config.name
                        yield f"data: {json.dumps({'content': f'WhatsApp data is not available for {company_name}. Please select PakWheels or Insights mode.', 'done': True})}\n\n"
                        return
                    elif mode == "pakwheels" and not company_config.has_pakwheels:
                        company_name = company_config.name
                        yield f"data: {json.dumps({'content': f'PakWheels data is not available for {company_name}. Please select a different data source.', 'done': True})}\n\n"
                        return
                    elif mode == "reddit" and (not hasattr(company_config, 'has_reddit') or not getattr(company_config, 'has_reddit', True)):
                        company_name = company_config.name
                        yield f"data: {json.dumps({'content': f'Reddit data is not available for {company_name}. Please select a different data source.', 'done': True})}\n\n"
                        return
                    elif mode == "lucid" and (not hasattr(company_config, 'has_lucid') or not getattr(company_config, 'has_lucid', False)):
                        company_name = company_config.name
                        yield f"data: {json.dumps({'content': f'Lucid Forum data is not available for {company_name}. Please select a different data source.', 'done': True})}\n\n"
                        return
                    
                    try:
                        rag = get_rag_engine(company_id=user_company)
                    except Exception as e:
                        yield f"data: {json.dumps({'content': f'The {company_config.name} insight engine is not available yet.', 'done': True})}\n\n"
                        return
                        
                    if rag is None:
                        yield f"data: {json.dumps({'content': f'The {company_config.name} insight engine is not available yet.', 'done': True})}\n\n"
                        return
                    
                    # Get chat history
                    from models.chat import get_user_chat_history
                    history = get_user_chat_history(current_user.id, mode, session_id)
                    if len(history) == 0:
                        history = None
                    
                    # Use RAG engine with streaming if available
                    ai_start_time = time.time()
                    
                    # Convert cross_platform mode to None for multi-source retrieval
                    source_param = None if mode == "cross_platform" else mode
                    
                    # Check if RAG engine supports streaming
                    if hasattr(rag, 'answer_stream'):
                        # Stream from RAG engine
                        full_answer = ""
                        for chunk in rag.answer_stream(query, history=history, thinking_mode=thinking_mode, source=source_param, session_id=session_id):
                            full_answer += chunk
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                    else:
                        # Fallback to regular answer but send immediately
                        answer = rag.answer(query, history=history, thinking_mode=thinking_mode, source=source_param, session_id=session_id, user_id=current_user.id)
                        full_answer = answer
                        
                        # Send answer in chunks for perceived streaming
                        words = answer.split()
                        chunk_size = 10  # Larger chunks for faster streaming
                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i+chunk_size])
                            if i + chunk_size < len(words):
                                chunk += " "
                            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
                            # No delay for maximum speed
                    
                    ai_duration = time.time() - ai_start_time
                    
                    # Clean up any placeholder patterns and object artifacts
                    import re
                    full_answer = re.sub(r'CHART_PLACEHOLDER_\d+', '', full_answer)
                    full_answer = re.sub(r'__CHART_PLACEHOLDER_\d+__', '', full_answer)
                    full_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', full_answer).strip()
                    
                    # Extract structured data FIRST (before removing references)
                    structured_data = extract_structured_data(full_answer, None, mode)
                    
                    # NOW remove references section from the main content since we send them separately as structured data
                    clean_answer = re.sub(r'---\s*\n### 📋 References[\s\S]*?---', '', full_answer)
                    clean_answer = re.sub(r'📋 References[\s\S]*$', '', clean_answer)
                    clean_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_answer).strip()
                    
                    # Save the original answer to chat history (with references for context)
                    save_user_chat_history(current_user.id, session_id, mode, query, full_answer, structured_data)
                    
                    yield f"data: {json.dumps({'content': '', 'done': True, 'structured': safe_json_serialize(structured_data)})}\n\n"
                    
            except Exception as e:
                log_error(e, f"Streaming error for user {current_user.username}")
                yield f"data: {json.dumps({'content': 'Sorry, I encountered an error while processing your request.', 'done': True})}\n\n"
        
        return Response(generate_response(), mimetype='text/event-stream')
        
    except Exception as e:
        log_error(e, f"Request processing error for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        def error_response():
            yield f"data: {json.dumps({'content': 'Sorry, I could not generate a response.', 'done': True})}\n\n"
        return Response(error_response(), mimetype='text/event-stream')


@log_function_call(chat_logger, log_args=False)  # Don't log full query content
def chatbot_query():
    """Process chatbot queries with the RAG engine (legacy non-streaming endpoint)"""
    
    try:
        data = request.get_json(force=True) or {}
        query = (data.get("query") or "").strip()
        mode = (data.get("mode") or "pakwheels").strip().lower()
        thinking_mode = bool(data.get("thinking", False))
        
        chat_logger.info(f"Chat query from user {current_user.username}: mode={mode}, thinking={thinking_mode}, query_length={len(query)}")
        
        if not query:
            if mode == "insights":
                return jsonify({"answer": "Hello! How can I help you today?"})
            else:
                return jsonify({
                    "answer": "Please ask something about your vehicle, concerns, or the available data."
                })
        
        # Get user's company
        user_company = current_user.company_id or 'haval'
        
        # Get session ID from payload or Flask session
        session_id = data.get("session_id") or session.get('chat_session_id')
        if not session_id:
            session_id = secrets.token_hex(16)
            session['chat_session_id'] = session_id
        
        start_time = time.time()
        
        try:
            # Handle Insights mode first (doesn't need RAG engine)
            if mode == "insights":
                chat_logger.info(f"Processing Insights query for user {current_user.username}")
                
                # Use OpenAI for insights mode
                import app
                openai_client = app.get_openai_client()
                if not openai_client:
                    return jsonify({
                        "answer": "Insights mode is not available. OpenAI integration is required."
                    })
                
                try:
                    # Get user-specific chat history for the mode
                    from models.chat import get_user_chat_history
                    history = get_user_chat_history(current_user.id, mode, session_id)
                    if len(history) == 0:
                        history = None
                    
                    # Build conversation history for ChatGPT-like experience
                    messages = [
                        {"role": "system", "content": "You are ChatGPT, a helpful AI assistant created by OpenAI. Provide clear, informative, and conversational responses. Be helpful, harmless, and honest. You can discuss a wide range of topics and help with various tasks."}
                    ]
                    
                    # Add conversation history (last 10 exchanges to stay within token limits)
                    if history:
                        recent_history = history[-20:]  # Last 20 messages (10 exchanges)
                        for msg in recent_history:
                            if msg.get('role') in ['user', 'assistant']:
                                # Clean the content from any placeholder patterns
                                content = msg['content']
                                import re
                                content = re.sub(r'CHART_PLACEHOLDER_\d+', '', content)
                                content = re.sub(r'__CHART_PLACEHOLDER_\d+__', '', content)
                                content = content.strip()
                                
                                if content:  # Only add non-empty messages
                                    messages.append({
                                        "role": msg['role'],
                                        "content": content
                                    })
                    
                    # Add current user message
                    messages.append({"role": "user", "content": query})
                    
                    ai_start_time = time.time()
                    
                    # Check if this is a GrokClient or actual OpenAI client
                    if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
                        # This is an actual OpenAI client
                        response = openai_client.chat.completions.create(
                            model="gpt-4o",  # Use latest GPT-4 model
                            messages=messages,
                            max_tokens=2000,
                            temperature=0.7,
                            presence_penalty=0.1,
                            frequency_penalty=0.1
                        )
                        answer = response.choices[0].message.content
                    else:
                        # This is a GrokClient or similar - it can handle messages array directly
                        llm_response = openai_client.generate(messages, max_tokens=2000, temperature=0.7)
                        # Extract text from LLMResponse object
                        answer = extract_text_from_llm_response(llm_response)
                    
                    ai_duration = time.time() - ai_start_time
                    
                    # Aggressive cleanup of any placeholder patterns
                    import re
                    answer = re.sub(r'CHART_PLACEHOLDER_\d+', '', answer)
                    answer = re.sub(r'__CHART_PLACEHOLDER_\d+__', '', answer)
                    answer = re.sub(r'\bCHART_PLACEHOLDER_\d+\b', '', answer)
                    answer = re.sub(r'CHART_PLACEHOLDER_\d+\s*', '', answer)
                    answer = re.sub(r'\s*CHART_PLACEHOLDER_\d+', '', answer)
                    answer = re.sub(r'\n\s*CHART_PLACEHOLDER_\d+\s*\n', '\n', answer)
                    answer = re.sub(r'^CHART_PLACEHOLDER_\d+\s*\n', '', answer, flags=re.MULTILINE)
                    answer = re.sub(r'\n\s*\n\s*\n', '\n\n', answer).strip()
                    
                    # Extract structured data FIRST (before removing references)
                    structured_data = extract_structured_data(answer, None, mode)
                    
                    # NOW remove references section from the main content since we send them separately as structured data
                    clean_answer = re.sub(r'---\s*\n### 📋 References[\s\S]*?---', '', answer)
                    clean_answer = re.sub(r'📋 References[\s\S]*$', '', clean_answer)
                    clean_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_answer).strip()
                    
                    # Save original answer to chat history (with references for context)
                    save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
                    
                    log_ai_activity("Insights Query", "OpenAI", None, ai_duration)
                    chat_logger.info(f"Insights query processed for user {current_user.username}: {ai_duration:.2f}s")
                    
                    return jsonify({
                        "answer": clean_answer,
                        "structured": safe_json_serialize(structured_data)
                    })
                    
                except Exception as e:
                    log_error(e, f"OpenAI Insights error for user {current_user.username}")
                    return jsonify({
                        "answer": "Sorry, the Insights mode encountered an error. Please try again."
                    })

            elif mode == "dealership":
                # DMS (Dealership Management System) Mode - Production-grade Text-to-SQL RAG pipeline
                chat_logger.info(f"Processing DMS query for user {current_user.username}")

                try:
                    from config import get_company_config
                    from config.llm_config import get_llm_for_component

                    # Get company configuration
                    company_config = get_company_config(user_company)

                    # Verify DMS is available for this company
                    if not company_config.has_dms:
                        return jsonify({
                            "answer": "Dealership database is not available for your company. Please contact support."
                        })

                    # ⭐ SKIP DOMAIN CLASSIFICATION FOR DEALERSHIP MODE
                    # When user explicitly selects "Dealership" mode, ALL queries go to DMS pipeline
                    # DMS pipeline's intent_classifier_dms.py handles meta-operations automatically
                    chat_logger.info(f"✓ Dealership mode selected - sending query directly to DMS pipeline (no domain check)")
                    chat_logger.info(f"✓ Intent classification will be handled by DMS intent_classifier_dms.py")

                    # STEP 1: LOAD CHAT HISTORY FOR FOLLOW-UP SUPPORT
                    from models.chat import get_user_chat_history
                    history = get_user_chat_history(current_user.id, mode, session_id, limit=4)

                    # Convert to DMS pipeline format
                    chat_history = []
                    if history:
                        for msg in history:
                            chat_history.append({
                                "role": msg.get('role', 'user'),
                                "content": msg.get('content', '')
                            })
                        chat_logger.info(f"✓ Loaded {len(chat_history)} messages for follow-up support")
                    else:
                        chat_logger.info(f"No chat history found (new session)")

                    # STEP 2: INITIALIZE PIPELINE BASED ON DMS TYPE
                    # Different companies use different DMS systems:
                    # - "production": Real DMS with Tier 0/1/2/3 (ai/dms_engine) - e.g., Haval
                    # - "dummy": Dummy dealership database (ai/dealership_engine) - e.g., Kia
                    dms_type = company_config.dms_type or "production"
                    ai_start_time = time.time()

                    if dms_type == "production":
                        # Production DMS Pipeline (Haval - SazgarDMSDW)
                        # Use centralized cache manager to prevent model reload
                        chat_logger.info("=" * 80)
                        chat_logger.info("[PIPELINE MANAGER - LEGACY] Importing pipeline_manager...")

                        from ai.pipeline_manager import get_pipeline_manager

                        chat_logger.info("[PIPELINE MANAGER - LEGACY] Getting manager instance...")
                        pipeline_manager = get_pipeline_manager()

                        chat_logger.info(f"[PIPELINE MANAGER - LEGACY] Requesting DMS pipeline for company={current_user.company_id}, dealer={company_config.dms_dealer_id}")

                        # Get or create cached pipeline (prevents model reload!)
                        dms_pipeline = pipeline_manager.get_dms_pipeline(
                            company_id=current_user.company_id,
                            db_path=company_config.dms_db_path,
                            dealer_id=company_config.dms_dealer_id,
                            db_config=company_config.dms_db_config,  # MSSQL/SQLite config
                            dms_data_source=getattr(company_config, 'dms_data_source', 'mssql'),  # sqlite or mssql pipeline
                            enable_tier0=True,
                            enable_tier1=True,
                            enable_tier2=True,
                            enable_tier3=True,
                            enable_semantic_cache=True,
                            enable_follow_ups=True,
                            verbose=False
                        )

                        # STEP 3: EXECUTE QUERY through 4-tier pipeline (Tier 0/1/2/3)
                        result = dms_pipeline.query(
                            user_query=query,
                            chat_history=chat_history if chat_history else None,  # ⭐ Pass chat history
                            session_id=session_id,  # ⭐ Pass session ID for caching
                            execute=True,
                            format_results=True
                        )
                        ai_duration = time.time() - ai_start_time

                        # Get natural language answer
                        if result.success:
                            answer = result.natural_answer
                            tier_info = f"Tier {result.tier_used}"
                            metadata = {
                                "tier_used": result.tier_used,
                                "execution_time": result.execution_time,
                                "sql": result.sql,
                                "server_time": round(ai_duration, 1)
                            }
                        else:
                            answer = f"Sorry, I couldn't process your query. {result.error_message}"
                            tier_info = "N/A"
                            metadata = {"server_time": round(ai_duration, 1)}

                    elif dms_type == "dummy":
                        # Dummy Dealership Pipeline (Kia - dealership_kia.db)
                        from ai.dealership_engine.dealership_pipeline import \
                            DealershipPipeline

                        chat_logger.info(f"Initializing dummy dealership pipeline for {company_config.name}...")

                        dealership_pipeline = DealershipPipeline(db_path=company_config.dms_db_path)

                        # STEP 3: EXECUTE QUERY through dummy dealership pipeline
                        answer = dealership_pipeline.answer(
                            question=query,
                            chat_history=chat_history if chat_history else None
                        )
                        ai_duration = time.time() - ai_start_time

                        # Dummy pipeline returns string directly, no metadata
                        tier_info = "Dummy Dealership"
                        metadata = {}

                    else:
                        answer = f"Unknown DMS type: {dms_type}. Please contact support."
                        ai_duration = time.time() - ai_start_time
                        tier_info = "Unknown"
                        metadata = {}

                    # STEP 4: SAVE TO HISTORY
                    structured_data = extract_structured_data(answer, None, mode)
                    save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                    log_ai_activity("DMS Query", f"DMS Pipeline ({tier_info})", None, ai_duration)
                    chat_logger.info(f"DMS query processed for user {current_user.username}: {ai_duration:.2f}s (Tier: {tier_info})")

                    return jsonify({
                        "answer": answer,
                        "structured": structured_data,
                        "metadata": metadata,
                        "server_time": round(ai_duration, 1)
                    })

                except Exception as e:
                    log_error(e, f"DMS pipeline error for user {current_user.username}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        "answer": "Sorry, dealership query failed. Please try rephrasing your question or contact support."
                    })

            elif mode == "finance":
                # Finance Mode - Finance/DMS query processing with agents
                chat_logger.info(f"Processing Finance query for user {current_user.username}")

                try:
                    from ai.finance.domain_classifier import \
                        FinanceDomainClassifier
                    from ai.finance.format_detector import \
                        FinanceFormatDetector
                    from ai.finance.query_reformulator import \
                        FinanceQueryReformulator
                    from config.llm_config import get_llm_for_component
                    from services.ai_service import AIService

                    # STEP 1: Domain Classification
                    llm_client = get_llm_for_component('finance_domain_classifier')
                    domain_classifier = FinanceDomainClassifier(llm_client=llm_client)
                    domain_result = domain_classifier.classify(query)

                    if not domain_result['is_in_domain']:
                        # Out-of-domain query - check if it's small talk or completely unrelated
                        domain_type = domain_result.get('domain', 'out_of_domain')
                        
                        if domain_type == 'small_talk':
                            # Handle greetings politely
                            answer = "Hello! I can help you with finance database queries about customers, loans, accounts, transactions, and vehicle financing. What would you like to know?"
                        else:
                            # Out-of-domain topic
                            answer = "OUT_OF_DOMAIN - This question is not related to the finance database. I can only answer questions about customers, loans, accounts, transactions, investments, and credit cards. Please ask a finance-related question."
                        
                        save_user_chat_history(current_user.id, session_id, mode, query, answer)
                        return jsonify({"answer": answer})

                    # STEP 2: Query Reformulation
                    reformulator = FinanceQueryReformulator(llm_client=llm_client)
                    reformulation_result = reformulator.reformulate(query)
                    reformulated_query = reformulation_result['reformulated_query']
                    
                    if reformulation_result['changed']:
                        chat_logger.info(f"Query reformulated: {query} -> {reformulated_query}")

                    # STEP 3: Format Detection
                    format_detector = FinanceFormatDetector(llm_client=llm_client)
                    format_result = format_detector.detect(reformulated_query)
                    chat_logger.info(f"Format detected: {format_result['query_type']} -> {format_result['response_format']}")

                    # STEP 4: Process query with finance system
                    ai_start_time = time.time()
                    
                    # Use Finance Pipeline for database queries
                    try:
                        from ai.finance.finance_pipeline import \
                            get_finance_pipeline

                        # Get finance pipeline (uses config.yaml for DB path)
                        finance_pipeline = get_finance_pipeline()
                        
                        # Execute query through SQL agent
                        result = finance_pipeline.query(query, reformulated_query)
                        
                        if result['success']:
                            answer = result['answer']
                            sql_query = result['sql']
                        else:
                            answer = result['answer']  # Error message
                            sql_query = None
                            
                    except Exception as pipeline_error:
                        chat_logger.error(f"Finance pipeline error: {pipeline_error}")
                        # Fallback to AI service if pipeline fails
                        answer = AIService.process_chat_query(reformulated_query, mode, user_company)
                        sql_query = None
                    
                    ai_duration = time.time() - ai_start_time

                    # Add metadata about processing
                    processing_info = f"\n\n*Query Type: {format_result['query_type'].title()} | Confidence: {domain_result['confidence']:.0%}*"
                    if sql_query:
                        processing_info += f"\n*SQL: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}*"
                    
                    # Handle None answer to prevent TypeError
                    if answer is None:
                        answer = "Sorry, I couldn't process your query. Please try again."
                    answer += processing_info

                    # Save to chat history
                    save_user_chat_history(current_user.id, session_id, mode, query, answer)
                    structured_data = extract_structured_data(answer, None, mode)

                    # Add agent metadata
                    metadata = {
                        'domain': domain_result['domain'],
                        'confidence': domain_result['confidence'],
                        'query_type': format_result['query_type'],
                        'response_format': format_result['response_format'],
                        'reformulated': reformulation_result['changed']
                    }

                    log_ai_activity("Finance Query", "Finance AI", None, ai_duration)
                    chat_logger.info(f"Finance query processed for user {current_user.username}: {ai_duration:.2f}s")

                    return jsonify({
                        "answer": answer,
                        "structured": safe_json_serialize(structured_data),
                        "metadata": metadata
                    })

                except Exception as e:
                    log_error(e, f"Finance mode error for user {current_user.username}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        "answer": "Sorry, finance query failed. Please try rephrasing your question."
                    })

            elif mode == "supplychain":
                # Supply Chain Mode - Supply chain query processing with agents
                chat_logger.info(f"Processing Supply Chain query for user {current_user.username}")

                try:
                    from ai.SupplyChain.domain_classifier import \
                        SupplyChainDomainClassifier
                    from ai.SupplyChain.format_detector import \
                        SupplyChainFormatDetector
                    from ai.SupplyChain.query_reformulator import \
                        SupplyChainQueryReformulator
                    from config.llm_config import get_llm_for_component
                    from services.ai_service import AIService

                    # STEP 1: Domain Classification
                    llm_client = get_llm_for_component('supplychain_domain_classifier')
                    domain_classifier = SupplyChainDomainClassifier(llm_client=llm_client)
                    domain_result = domain_classifier.classify(query)

                    if not domain_result['is_in_domain']:
                        # Out-of-domain query - check if it's small talk or completely unrelated
                        domain_type = domain_result.get('domain', 'out_of_domain')

                        if domain_type == 'small_talk':
                            # Handle greetings politely
                            answer = "Hello! I can help you with supply chain queries about suppliers, parts, purchase orders, inventory, and shipments. What would you like to know?"
                        else:
                            # Out-of-domain topic
                            answer = "OUT_OF_DOMAIN - This question is not related to the supply chain database. I can only answer questions about suppliers, parts, purchase orders, inventory, and shipments. Please ask a supply chain-related question."

                        save_user_chat_history(current_user.id, session_id, mode, query, answer)
                        return jsonify({"answer": answer})

                    # STEP 2: Query Reformulation
                    reformulator = SupplyChainQueryReformulator(llm_client=llm_client)
                    reformulation_result = reformulator.reformulate(query)
                    reformulated_query = reformulation_result.get('reformulated_query') or query

                    if reformulation_result.get('is_changed'):
                        chat_logger.info(f"Query reformulated: {query} -> {reformulated_query}")

                    # STEP 3: Format Detection
                    format_detector = SupplyChainFormatDetector(llm_client=llm_client)
                    format_result = format_detector.detect(reformulated_query)
                    chat_logger.info(f"Format detected: {format_result['query_type']} -> {format_result['response_format']}")

                    # STEP 4: Process query with supply chain system
                    ai_start_time = time.time()

                    try:
                        from ai.SupplyChain.supplychain_pipeline import \
                            get_supplychain_pipeline

                        # Get supply chain pipeline (uses config.yaml for DB path)
                        supplychain_pipeline = get_supplychain_pipeline()

                        # Execute query through SQL agent
                        result = supplychain_pipeline.query(query, reformulated_query)

                        if result['success']:
                            answer = result['answer']
                            sql_query = result['sql']
                        else:
                            answer = result['answer']  # Error message
                            sql_query = None

                    except Exception as pipeline_error:
                        chat_logger.error(f"Supply Chain pipeline error: {pipeline_error}")
                        # Fallback to AI service if pipeline fails
                        answer = AIService.process_chat_query(reformulated_query, mode, user_company)
                        sql_query = None

                    ai_duration = time.time() - ai_start_time

                    # Add metadata about processing
                    processing_info = f"\n\n*Query Type: {format_result['query_type'].title()} | Confidence: {domain_result['confidence']:.0%}*"
                    if sql_query:
                        processing_info += f"\n*SQL: {sql_query[:100]}{'...' if len(sql_query) > 100 else ''}*"

                    # Handle None answer to prevent TypeError
                    if answer is None:
                        answer = "Sorry, I couldn't process your query. Please try again."
                    answer += processing_info

                    # Save to chat history
                    save_user_chat_history(current_user.id, session_id, mode, query, answer)
                    structured_data = extract_structured_data(answer, None, mode)

                    # Add agent metadata
                    metadata = {
                        'domain': domain_result['domain'],
                        'confidence': domain_result['confidence'],
                        'query_type': format_result['query_type'],
                        'response_format': format_result['response_format'],
                        'reformulated': reformulation_result.get('is_changed', False)
                    }

                    log_ai_activity("Supply Chain Query", "Supply Chain AI", None, ai_duration)
                    chat_logger.info(f"Supply Chain query processed for user {current_user.username}: {ai_duration:.2f}s")

                    return jsonify({
                        "answer": answer,
                        "structured": safe_json_serialize(structured_data),
                        "metadata": metadata
                    })

                except Exception as e:
                    log_error(e, f"Supply Chain mode error for user {current_user.username}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        "answer": "Sorry, supply chain query failed. Please try rephrasing your question."
                    })

            elif mode == "facebook_beta":
                # Facebook Beta Mode - Process Facebook group data with advanced filtering
                chat_logger.info(f"Processing Facebook Beta query for user {current_user.username}")

                try:
                    from services.ai_service import AIService

                    # Get answer from AI service Facebook query processor
                    ai_start_time = time.time()
                    answer = AIService.process_chat_query(query, mode, user_company)
                    ai_duration = time.time() - ai_start_time

                    # Save to chat history
                    structured_data = extract_structured_data(answer, None, mode)
                    save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)

                    log_ai_activity("Facebook_Beta Query", "AI Service", None, ai_duration)
                    chat_logger.info(f"Facebook Beta query processed for user {current_user.username}: {ai_duration:.2f}s")

                    return jsonify({
                        "answer": answer,
                        "structured": safe_json_serialize(structured_data)
                    })

                except Exception as e:
                    log_error(e, f"Facebook Beta processing error for user {current_user.username}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        "answer": "Sorry, Facebook Beta query failed. Please try rephrasing your question."
                    })

            # For RAG-based modes (PakWheels and WhatsApp), check pipeline status
            try:
                from ai.haval_pipeline import get_pipeline_status
                status = get_pipeline_status()
            except Exception as e:
                chat_logger.error(f"Error getting pipeline status: {e}")
                status = {"status": "error", "error": str(e)}
                
            if status.get("status") != "ready":
                # Try AI analysis as fallback for non-ready pipeline
                try:
                    from controllers.ai_analysis import ai_analyze_query
                    from models import get_db_connection
                    
                    conn = get_db_connection()
                    cur = conn.cursor()
                    
                    # Use AI analysis for intelligent responses
                    answer = ai_analyze_query(query, cur)
                    conn.close()
                    
                    # Save to chat history
                    structured_data = extract_structured_data(answer, None, mode)
                    save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
                    
                    processing_time = time.time() - start_time
                    chat_logger.info(f"AI Analysis fallback used for user {current_user.username}: {processing_time:.2f}s")
                    
                    return jsonify({
                        "answer": answer,
                        "structured": {"references": [], "charts": [], "tables": [], "recommendations": []}
                    })
                    
                except Exception as fallback_error:
                    chat_logger.error(f"AI Analysis fallback failed: {fallback_error}")
                    # If pipeline is not ready and fallback fails, provide helpful message
                    import app
                    llm_client = app.get_llm_client()
                    if llm_client is None:
                        return jsonify({
                            "answer": (
                                "The AI system is not fully configured. Please ensure you have set up your API keys in the .env file:\n\n"
                                "1. XAI_API_KEY (for Grok) or GEMINI_API_KEY (for Gemini)\n"
                                "2. OPENAI_API_KEY (for Insights mode)\n\n"
                                "After adding the keys, restart the application."
                            )
                        })
                    else:
                        return jsonify({
                            "answer": (
                                f"The insight engine is still processing (current status: {status.get('status', 'unknown')}). "
                                "Please wait until it shows as ready, or try asking a general question in Insights mode."
                            )
                        })
            
            # Check if LLM client is available
            import app
            llm_client = app.get_llm_client()
            if llm_client is None:
                return jsonify({
                    "answer": (
                        "The AI system is not properly configured. Please check your API keys in the .env file and restart the application."
                    )
                })
            
            # EMAIL MODE - Handle separately with Gmail RAG
            if mode == "email":
                print(f"[Chat - Non-Streaming] ======== ENTERING EMAIL MODE ========")
                print(f"[Chat - Non-Streaming] Query: {query[:100]}")
                try:
                    import os

                    from ai.email.email_rag_handler import EmailRAGHandler
                    from ai.email.email_vector_store import EmailVectorStore

                    # Check if Gmail OAuth is configured
                    client_id = os.getenv('GOOGLE_CLIENT_ID')
                    client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
                    
                    if not client_id or not client_secret:
                        return jsonify({
                            "answer": "Gmail OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
                        })
                    
                    # Get vector store
                    vector_store = EmailVectorStore()
                    
                    # Check if there are any indexed emails
                    stats = vector_store.get_stats()
                    print(f"[Chat - Non-Streaming] Email Vector Store stats: {stats}")
                    
                    if stats.get('total_indexed', 0) == 0:
                        return jsonify({
                            "answer": "No emails indexed yet. Please click 'Sync Emails' button in the Email panel to index your emails first."
                        })
                    
                    # Get LLM API key
                    api_key = os.getenv('XAI_API_KEY')
                    llm_provider = 'grok'
                    
                    if not api_key:
                        api_key = os.getenv('OPENAI_API_KEY')
                        llm_provider = 'openai'
                    
                    if not api_key:
                        api_key = os.getenv('GOOGLE_API_KEY')
                        llm_provider = 'gemini'
                    
                    if not api_key:
                        return jsonify({
                            "answer": "No LLM API key configured. Please set XAI_API_KEY or OPENAI_API_KEY in .env"
                        })
                    
                    # Initialize RAG handler
                    rag_handler = EmailRAGHandler(
                        vector_store=vector_store,
                        llm_provider=llm_provider,
                        api_key=api_key
                    )
                    
                    # Query emails
                    ai_start_time = time.time()
                    result = rag_handler.query(query, n_results=5)
                    ai_duration = time.time() - ai_start_time
                    
                    if not result.get('success', False):
                        return jsonify({
                            "answer": f"Error querying emails: {result.get('error', 'Unknown error')}"
                        })
                    
                    answer = result.get('answer', 'No answer generated.')
                    sources = result.get('sources', [])
                    
                    # Build email references for display
                    email_references = []
                    for idx, source in enumerate(sources):
                        email_references.append({
                            'id': f'email_{idx}',
                            'type': 'email',
                            'source': 'email',
                            'title': source.get('title', 'No Subject'),
                            'subject': source.get('title', 'No Subject'),
                            'sender': source.get('sender', 'Unknown'),
                            'sender_name': source.get('sender_name', source.get('sender', 'Unknown').split('<')[0].strip() if '<' in source.get('sender', '') else source.get('sender', 'Unknown')),
                            'sender_email': source.get('sender_email', ''),
                            'date': source.get('date', 'Unknown'),
                            'time': source.get('time', ''),
                            'snippet': source.get('snippet', ''),
                            'body': source.get('body', ''),
                            'email_id': source.get('email_id', ''),
                            'thread_id': source.get('thread_id', ''),
                            'platform': 'Gmail',
                            'relevance_score': source.get('relevance_score', 0)
                        })
                    
                    # Build structured data
                    structured_data = {
                        'references': email_references,
                        'mode': 'email',
                        'source_count': len(sources)
                    }
                    
                    # Save to chat history
                    save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
                    
                    # Log activity
                    log_ai_activity("Email Query", "Email RAG", None, ai_duration)
                    chat_logger.info(f"Email query processed for user {current_user.username}: {ai_duration:.2f}s")
                    
                    return jsonify({
                        "answer": answer,
                        "server_time": round(ai_duration, 1),
                        "structured": safe_json_serialize(structured_data)
                    })
                    
                except Exception as e:
                    chat_logger.error(f"Email mode error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        "answer": f"Sorry, email query failed: {str(e)}"
                    })
            
            # Get user-specific chat history for the mode
            from models.chat import get_user_chat_history
            history = get_user_chat_history(current_user.id, mode, session_id)
            if len(history) == 0:
                history = None
            
            # Get company-specific RAG engine
            from config import get_company_config
            company_config = get_company_config(user_company)
            
            # Log which company is being queried
            chat_logger.info(f"Query for company: {company_config.full_name} (company_id: {user_company})")
            
            # Validate that the requested source is available for this company
            if mode == "whatsapp" and not company_config.has_whatsapp:
                return jsonify({
                    "answer": f"WhatsApp data is not available for {company_config.name}. "
                             f"Please select PakWheels or Insights mode."
                })
            elif mode == "pakwheels" and not company_config.has_pakwheels:
                return jsonify({
                    "answer": f"PakWheels data is not available for {company_config.name}. "
                             f"Please select a different data source."
                })
            elif mode == "reddit" and (not hasattr(company_config, 'has_reddit') or not getattr(company_config, 'has_reddit', True)):
                return jsonify({
                    "answer": f"Reddit data is not available for {company_config.name}. "
                             f"Please select a different data source."
                })
            elif mode == "lucid" and (not hasattr(company_config, 'has_lucid') or not getattr(company_config, 'has_lucid', False)):
                return jsonify({
                    "answer": f"Lucid Forum data is not available for {company_config.name}. "
                             f"Please select a different data source."
                })
            
            # Use company-specific RAG engine
            try:
                from ai.haval_pipeline import get_rag_engine
                rag = get_rag_engine(company_id=user_company)
            except Exception as e:
                chat_logger.error(f"Error getting RAG engine: {e}")
                rag = None
                
            if rag is None:
                return jsonify({
                    "answer": f"The {company_config.name} insight engine is not available yet. "
                             f"Please try scraping {company_config.name} data first."
                })
            
            # Pass thinking_mode and source to RAG engine for filtering and formatting
            ai_start_time = time.time()
            # Convert cross_platform mode to None for multi-source retrieval
            source_param = None if mode == "cross_platform" else mode
            answer = rag.answer(query, history=history, thinking_mode=thinking_mode, source=source_param, session_id=session_id, user_id=current_user.id)
            ai_duration = time.time() - ai_start_time
            
            # Aggressive cleanup of any CHART_PLACEHOLDER patterns that LLM might output
            import re
            answer = re.sub(r'CHART_PLACEHOLDER_\d+', '', answer)
            answer = re.sub(r'__CHART_PLACEHOLDER_\d+__', '', answer)
            answer = re.sub(r'\bCHART_PLACEHOLDER_\d+\b', '', answer)
            answer = re.sub(r'CHART_PLACEHOLDER_\d+\s*', '', answer)
            answer = re.sub(r'\s*CHART_PLACEHOLDER_\d+', '', answer)
            answer = re.sub(r'\n\s*CHART_PLACEHOLDER_\d+\s*\n', '\n', answer)
            answer = re.sub(r'^CHART_PLACEHOLDER_\d+\s*\n', '', answer, flags=re.MULTILINE)
            answer = re.sub(r'\n\s*\n\s*\n', '\n\n', answer).strip()
            
            # Extract structured data FIRST (before removing references)
            structured_data = extract_structured_data(answer, None, mode)
            
            # NOW remove references section from the main content since we send them separately as structured data
            clean_answer = re.sub(r'---\s*\n### 📋 References[\s\S]*?---', '', answer)
            clean_answer = re.sub(r'📋 References[\s\S]*$', '', clean_answer)
            clean_answer = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_answer).strip()
            
            # Save original answer to chat history (with references for context)
            save_user_chat_history(current_user.id, session_id, mode, query, answer, structured_data)
            
            processing_time = time.time() - start_time
            chat_logger.info(f"{mode.title()} query processed for user {current_user.username}: {processing_time:.2f}s total")

            return jsonify({
                "answer": clean_answer,
                "server_time": round(ai_duration, 1),  # Server-side processing time in seconds
                "structured": safe_json_serialize(structured_data)
            })
            
        except Exception as e:
            log_error(e, f"Error processing chat query for user {current_user.username}")
            return jsonify({
                "answer": "Sorry, the insight engine ran into an error while answering. Please try again."
            })
    
    except Exception as e:
        log_error(e, f"Request processing error for user {current_user.username if current_user.is_authenticated else 'Anonymous'}")
        return jsonify({
            "answer": "Sorry, I could not generate a response."
        })


