"""
Dealership Database Pipeline

Main orchestrator for dealership database queries.
Handles query classification, entity extraction, SQL generation,
execution, and result formatting.
"""

from typing import List, Dict, Any, Optional
import sqlite3
from config.llm_config import get_llm_for_component
from models.dealership import DealershipDatabase, InspectionService
from ai.dealership_engine.domain_classifier import classify_dealership_domain, get_out_of_domain_message
from ai.dealership_engine.query_classifier import classify_dealership_query
from ai.dealership_engine.entity_extractor import extract_entities
from ai.dealership_engine.sql_generator import generate_sql, validate_sql
from ai.dealership_engine.result_formatter import format_results
from ai.rag_engine.query_reformulator import reformulate_query


class DealershipPipeline:
    """
    Main pipeline for dealership database queries.

    Converts natural language questions into SQL queries,
    executes them safely, and formats results into natural language.
    """

    def __init__(self, db_path: str = "data/dealership.db"):
        """Initialize dealership pipeline"""
        self.db_path = db_path
        self.db = DealershipDatabase(db_path)

        # Load LLM clients for different components
        self.domain_classifier_llm = get_llm_for_component("dealership_domain_classifier")
        self.classifier_llm = get_llm_for_component("dealership_query_classifier")
        self.entity_extractor_llm = get_llm_for_component("dealership_entity_extractor")
        self.sql_generator_llm = get_llm_for_component("dealership_sql_generator")
        self.result_formatter_llm = get_llm_for_component("dealership_result_formatter")

        print("[Dealership Pipeline] Initialized successfully")

    def answer(
        self,
        question: str,
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Answer a dealership database question.

        Args:
            question: User's natural language question
            chat_history: Previous conversation for context

        Returns:
            Natural language answer with data from database
        """

        print(f"\n{'='*80}")
        print(f"[Dealership Pipeline] Processing query: '{question}'")
        print(f"{'='*80}\n")

        try:
            # Step 0: Domain Classification - Check if query is about dealership data
            print("[Step 0] Checking if query is about dealership data...")
            domain = classify_dealership_domain(question, self.domain_classifier_llm)
            print(f"[Step 0] ✓ Domain: {domain}")

            if domain == "OUT_OF_DOMAIN":
                print("[Dealership Pipeline] Query rejected: OUT_OF_DOMAIN")
                return get_out_of_domain_message(question)

            # Step 1: Check if this is a follow-up question using existing intent classifier
            if chat_history and len(chat_history) > 0:
                from ai.rag_engine.intent_classifier import classify_query_intent

                intent_llm = get_llm_for_component("query_classification")
                intent = classify_query_intent(question, chat_history, intent_llm)

                if intent == "context_dependent":
                    print("[Dealership Pipeline] Detected context-dependent query (follow-up)")
                    question = self._handle_followup(question, chat_history)
                    print(f"[Dealership Pipeline] Reformulated query: '{question}'")

            # Step 1.5: Check for multi-part queries (multiple questions)
            if self._is_multi_query(question):
                print("[Step 1] Detected multi-part query, decomposing...")
                return self._handle_multi_query(question, chat_history)

            # Step 1.6: Check for visualization requests
            if self._is_visualization_request(question):
                print("[Step 1] Detected visualization request...")
                return self._handle_visualization_request(question, chat_history)

            # Step 2: Classify query type
            print("[Step 1] Classifying query type...")
            query_classification = classify_dealership_query(question, self.classifier_llm)

            query_type = query_classification.get('query_type')
            print(f"[Step 1] ✓ Query Type: {query_type}")

            # Step 3: Extract entities
            print("[Step 2] Extracting entities...")
            entities = extract_entities(question, self.entity_extractor_llm, chat_history)
            print(f"[Step 2] ✓ Entities extracted")

            # Step 4: Handle HISTORY queries specially (use existing method)
            if query_type == 'HISTORY' and entities.get('vin_number'):
                print(f"[Step 3] Using specialized VIN history method")
                return self._get_vin_history(entities['vin_number'])

            # Step 4b: Handle SEMANTIC_SUMMARY queries (SQL + LLM summarization)
            if query_type == 'SEMANTIC_SUMMARY' or query_classification.get('needs_summarization'):
                print(f"[Step 3] Using hybrid SQL + LLM summarization approach")
                return self._get_semantic_summary(question, query_classification, entities)

            # Step 5: Generate SQL
            print("[Step 3] Generating SQL...")
            sql, is_valid = generate_sql(
                question,
                query_classification,
                entities,
                self.sql_generator_llm
            )

            # Check if LLM determined query is unanswerable
            if sql == "INVALID_QUERY":
                return self._handle_unanswerable_query(question)

            if not is_valid:
                return self._handle_invalid_sql(question)

            print(f"[Step 3] ✓ SQL generated and validated")

            # Step 6: Execute SQL
            print("[Step 4] Executing SQL query...")
            results = self._execute_sql(sql)
            print(f"[Step 4] ✓ Query executed ({len(results)} results)")

            # Step 7: Format results
            print("[Step 5] Formatting results...")
            formatted_answer = format_results(
                results,
                question,
                query_classification,
                self.result_formatter_llm
            )
            print(f"[Step 5] ✓ Results formatted")

            print(f"\n{'='*80}")
            print(f"[Dealership Pipeline] Query completed successfully")
            print(f"{'='*80}\n")

            return formatted_answer

        except Exception as e:
            print(f"\n[Dealership Pipeline] ERROR: {str(e)}")
            import traceback
            traceback.print_exc()

            return self._generate_error_response(question, str(e))

    def _handle_followup(
        self,
        question: str,
        chat_history: List[Dict[str, str]]
    ) -> str:
        """
        Handle follow-up questions by reformulating with context.

        Examples:
        Q1: "How many tyre complaints in December?"
        Q2: "What about November?" → Reformulate to: "How many tyre complaints in November?"
        """

        try:
            # Use existing query reformulation
            reformulator_llm = get_llm_for_component("query_reformulation")

            reformulated = reformulate_query(
                query=question,
                chat_history=chat_history,
                llm=reformulator_llm
            )

            return reformulated

        except Exception as e:
            print(f"[Dealership Pipeline] Follow-up reformulation failed: {e}")
            return question  # Fallback to original question

    def _get_vin_history(self, vin_number: str) -> str:
        """
        Get complete VIN history using existing model method.

        Args:
            vin_number: Vehicle VIN

        Returns:
            Formatted history timeline
        """

        print(f"[VIN History] Retrieving complete history for VIN: {vin_number}")

        try:
            history = InspectionService.get_vin_complete_history(vin_number)

            if not history or not history.get('vehicle_info'):
                return f"No vehicle found with VIN: {vin_number}. Please verify the VIN number is correct."

            # Format complete history
            response = f"**Complete Service History for VIN: {vin_number}**\n\n"

            # Vehicle Info
            vehicle = history['vehicle_info']
            response += "**Vehicle Information:**\n"
            response += f"- Model: {vehicle.get('car_model', 'Unknown')}\n"
            response += f"- Variant: {vehicle.get('variant', 'N/A')}\n"
            response += f"- Year: {vehicle.get('model_year', 'N/A')}\n"
            response += f"- Color: {vehicle.get('color', 'N/A')}\n"
            response += f"- Dealership: {vehicle.get('dealership_name', 'N/A')}\n"
            response += f"- Status: {vehicle.get('status', 'N/A')}\n\n"

            # PDI Inspection
            if history.get('pdi_inspection'):
                pdi = history['pdi_inspection']
                response += "**PDI Inspection:**\n"
                response += f"- Date: {pdi.get('inspection_date', 'N/A')}\n"
                response += f"- Status: {pdi.get('pdi_status', 'N/A')}\n"
                response += f"- Objections: {pdi.get('objection_count', 0)}\n"
                response += f"- Delivery Status: {pdi.get('delivery_status', 'N/A')}\n\n"

            # FFS Inspections
            if history.get('ffs_inspections') and len(history['ffs_inspections']) > 0:
                response += f"**FFS Inspections ({len(history['ffs_inspections'])}):**\n"
                for ffs in history['ffs_inspections'][:5]:  # Show first 5
                    response += f"- {ffs.get('inspection_date')}: {ffs.get('dealership_name')} (Odometer: {ffs.get('odometer_reading', 'N/A')} km)\n"
                response += "\n"

            # SFS Inspections
            if history.get('sfs_inspections') and len(history['sfs_inspections']) > 0:
                response += f"**SFS Inspections ({len(history['sfs_inspections'])}):**\n"
                for sfs in history['sfs_inspections'][:5]:
                    response += f"- {sfs.get('inspection_date')}: {sfs.get('dealership_name')} (Odometer: {sfs.get('odometer_reading', 'N/A')} km)\n"
                response += "\n"

            # Warranty Claims
            if history.get('warranty_claims') and len(history['warranty_claims']) > 0:
                response += f"**Warranty Claims ({len(history['warranty_claims'])}):**\n"
                for claim in history['warranty_claims'][:10]:  # Show first 10
                    response += f"- {claim.get('claim_date')}: {claim.get('claim_type')} - {claim.get('problem_description', 'N/A')[:100]}\n"
                response += "\n"

            # Campaigns
            if history.get('campaigns') and len(history['campaigns']) > 0:
                response += f"**Campaign Services ({len(history['campaigns'])}):**\n"
                for campaign in history['campaigns'][:5]:
                    response += f"- {campaign.get('service_date')}: {campaign.get('campaign_name')} ({campaign.get('dealership_name')})\n"
                response += "\n"

            # Repair Orders
            if history.get('repair_orders') and len(history['repair_orders']) > 0:
                response += f"**Repair Orders ({len(history['repair_orders'])}):**\n"
                for ro in history['repair_orders'][:5]:
                    response += f"- {ro.get('ro_date')}: RO #{ro.get('ro_number')} - {ro.get('issue_description', 'N/A')[:100]}\n"
                response += "\n"

            return response

        except Exception as e:
            print(f"[VIN History] Error: {e}")
            return f"Error retrieving VIN history: {str(e)}"

    def _get_semantic_summary(
        self,
        question: str,
        query_classification: Dict[str, Any],
        entities: Dict[str, Any]
    ) -> str:
        """
        Handle SEMANTIC_SUMMARY queries using hybrid SQL + LLM approach.

        Steps:
        1. Generate SQL to retrieve relevant records
        2. Extract text content from results
        3. Use LLM to summarize and provide insights
        4. Optionally include statistics

        Args:
            question: User's question
            query_classification: Classification result
            entities: Extracted entities

        Returns:
            Natural language summary with insights
        """

        try:
            print("[Semantic Summary] Step 1: Generating SQL for data retrieval...")

            # Generate SQL to get relevant records
            sql, is_valid = generate_sql(
                question,
                query_classification,
                entities,
                self.sql_generator_llm
            )

            if not is_valid or sql == "INVALID_QUERY":
                return self._handle_invalid_sql(question)

            print(f"[Semantic Summary] Step 2: Executing SQL...")

            # Execute SQL and get records
            results = self._execute_sql(sql)
            print(f"[Semantic Summary] ✓ Retrieved {len(results)} records")

            if len(results) == 0:
                return f"No records found matching your query: '{question}'"

            # Step 3: Extract text content for summarization
            print("[Semantic Summary] Step 3: Extracting text content...")
            text_segments = []

            for row in results[:50]:  # Limit to 50 records to prevent token overflow
                # Extract text fields based on table
                if 'problem_description' in row:
                    text_segments.append(f"- {row.get('claim_type', 'Issue')}: {row.get('problem_description', '')}")

                if 'problem_cause_analysis' in row and row.get('problem_cause_analysis'):
                    text_segments.append(f"  Cause: {row.get('problem_cause_analysis')}")

                if 'findings' in row and row.get('findings'):
                    text_segments.append(f"- {row.get('findings', '')}")

                if 'issue_description' in row and row.get('issue_description'):
                    text_segments.append(f"- {row.get('issue_description', '')}")

                if 'objections' in row and row.get('objections'):
                    text_segments.append(f"- Objections: {row.get('objections', '')}")

            print(f"[Semantic Summary] ✓ Extracted {len(text_segments)} text segments")

            # Step 4: Use LLM to summarize
            print("[Semantic Summary] Step 4: Generating summary with LLM...")

            summary_prompt = f"""Analyze the following dealership data and provide a concise summary.

**User's Question:** "{question}"

**Data Found ({len(results)} records):**
{chr(10).join(text_segments[:100])}  # Limit to prevent token overflow

**Your Task:**
1. Identify the 2-3 most common patterns or issues
2. Provide frequency/severity assessment if relevant
3. Give actionable insights or recommendations
4. Keep response concise (3-5 bullet points)

**Format:**
- Use markdown formatting
- Start with a brief overview sentence
- List main findings as bullet points
- End with a recommendation if applicable

**Response:**"""

            summary_response = self.result_formatter_llm.generate(
                [{"role": "user", "content": summary_prompt}],
                max_tokens=500,
                temperature=0.3
            )

            summary = summary_response.content.strip()

            # Add statistics footer
            summary += f"\n\n---\n📊 **Data Summary:** Analyzed {len(results)} records from dealership database."

            print("[Semantic Summary] ✓ Summary generated")

            return summary

        except Exception as e:
            print(f"[Semantic Summary] Error: {e}")
            import traceback
            traceback.print_exc()
            return f"Error generating summary: {str(e)}"

    def _is_multi_query(self, question: str) -> bool:
        """
        Detect if query contains multiple questions.

        Args:
            question: User's question

        Returns:
            True if multiple questions detected
        """
        # Check for multiple question marks
        if question.count('?') > 1:
            return True

        # Check for conjunctions that indicate multiple questions
        multi_query_patterns = [
            ' and which ',
            ' and what ',
            ' and how ',
            ' and show ',
            ' also ',
            ' additionally ',
            '; ',  # Semicolon separator
        ]

        q_lower = question.lower()
        for pattern in multi_query_patterns:
            if pattern in q_lower:
                return True

        return False

    def _handle_multi_query(self, question: str, chat_history: Optional[List[Dict[str, str]]]) -> str:
        """
        Handle multi-part queries by decomposing and answering each part.

        Args:
            question: Multi-part question
            chat_history: Chat history

        Returns:
            Combined answer for all parts
        """
        try:
            print("[Multi-Query] Decomposing query into sub-questions...")

            # Use LLM to decompose the query
            decomposition_prompt = f"""The user asked a multi-part question. Break it down into separate independent questions.

**User's Question:** "{question}"

**Your Task:**
1. Identify all distinct questions in the user's query
2. Break them into separate, standalone questions
3. Each question should be complete and answerable independently

**Format:**
Return a JSON array of questions:
["Question 1", "Question 2", ...]

**Example:**
Input: "What is the most common problem and which dealership had most repairs?"
Output: ["What is the most common problem in repair orders?", "Which dealership had the most repairs?"]

**Now decompose the user's question:**
"""

            response = self.classifier_llm.generate(
                [{"role": "user", "content": decomposition_prompt}],
                max_tokens=300,
                temperature=0.0
            )

            # Parse sub-questions
            import json
            import re

            # Extract JSON array from response
            content = response.content.strip()
            # Try to find JSON array
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                sub_questions = json.loads(json_match.group())
            else:
                # Fallback: split by "and"
                sub_questions = [q.strip() + '?' for q in question.split(' and ') if '?' not in q]
                if len(sub_questions) == 0:
                    sub_questions = [question]

            print(f"[Multi-Query] Decomposed into {len(sub_questions)} sub-questions:")
            for i, sq in enumerate(sub_questions, 1):
                print(f"  {i}. {sq}")

            # Answer each sub-question
            answers = []
            for i, sub_question in enumerate(sub_questions[:3], 1):  # Limit to 3 sub-questions
                print(f"\n[Multi-Query] Answering sub-question {i}/{len(sub_questions[:3])}...")

                # Recursively call answer() for each sub-question (will not trigger multi-query again)
                sub_answer = self.answer(sub_question, chat_history)
                answers.append(f"**Q{i}: {sub_question}**\n{sub_answer}")

            # Combine answers
            combined_answer = "\n\n---\n\n".join(answers)
            combined_answer += f"\n\n---\n💡 **Note:** Your question contained {len(sub_questions)} parts. I answered each separately above."

            print("[Multi-Query] ✓ All sub-questions answered")

            return combined_answer

        except Exception as e:
            print(f"[Multi-Query] Error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: treat as single query
            print("[Multi-Query] Falling back to single query handling")
            return f"I detected multiple questions in your query. Please ask them one at a time for best results.\n\nYour question: '{question}'"

    def _is_visualization_request(self, question: str) -> bool:
        """
        Detect if query is asking for visualization/charting.

        Args:
            question: User's question

        Returns:
            True if visualization requested
        """
        viz_keywords = [
            'chart', 'graph', 'plot', 'visualize', 'visualization',
            'bar chart', 'bar graph', 'pie chart', 'line graph',
            'histogram', 'scatter plot', 'heatmap'
        ]

        q_lower = question.lower()
        return any(keyword in q_lower for keyword in viz_keywords)

    def _handle_visualization_request(self, question: str, chat_history: Optional[List[Dict[str, str]]]) -> str:
        """
        Handle visualization requests by providing data and explanation.

        Args:
            question: Visualization request
            chat_history: Chat history

        Returns:
            Data with visualization note
        """
        try:
            print("[Visualization] Processing visualization request...")

            # Extract the actual data question from the visualization request
            # Example: "show me a bar graph of common issues" → "what are the common issues?"
            data_question_prompt = f"""The user asked for a visualization. Extract the underlying data question.

**User's Request:** "{question}"

**Examples:**
- "show me a bar graph of tyre complaints" → "what are the tyre complaints and their frequencies?"
- "plot the above data" → "provide the data from the previous response"
- "chart dealership repairs" → "which dealerships had how many repairs?"

**Your Task:**
Convert the visualization request into a data query that can be answered with SQL.

**Response:**
Return ONLY the data question (no explanations):"""

            response = self.classifier_llm.generate(
                [{"role": "user", "content": data_question_prompt}],
                max_tokens=100,
                temperature=0.0
            )

            data_question = response.content.strip().strip('"')
            print(f"[Visualization] Extracted data question: '{data_question}'")

            # Answer the data question
            answer = self.answer(data_question, chat_history)

            # Add visualization note
            viz_note = f"""\n\n---\n📊 **Visualization Note:**

I've provided the data you requested. While I cannot generate visual charts directly, you can:

1. **Copy the data above** into Excel, Google Sheets, or any spreadsheet tool
2. **Use the built-in chart features** to create bar graphs, pie charts, etc.
3. **Or use Python/R** with libraries like matplotlib, seaborn, or ggplot2

The data is formatted for easy copying and visualization."""

            return answer + viz_note

        except Exception as e:
            print(f"[Visualization] Error: {e}")
            import traceback
            traceback.print_exc()
            return f"I understand you want a visualization, but I can only provide the data in text/table format. Please rephrase your question to ask for the data, and you can visualize it using Excel or other tools."

    def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """
        Execute SQL query safely.

        Args:
            sql: Validated SQL query

        Returns:
            List of result rows as dictionaries
        """

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Return rows as dictionaries
                cursor = conn.cursor()

                cursor.execute(sql)
                results = [dict(row) for row in cursor.fetchall()]

                return results

        except sqlite3.Error as e:
            print(f"[SQL Execution] Database error: {e}")
            raise Exception(f"Database query failed: {str(e)}")

        except Exception as e:
            print(f"[SQL Execution] Unexpected error: {e}")
            raise

    def _handle_unanswerable_query(self, question: str) -> str:
        """Handle cases where query cannot be answered from dealership database"""

        return f"""I'm sorry, but the question **"{question}"** cannot be answered using the dealership database.

**Dealership Database Contains:**
✅ Warranty Claims (technical reports, problem descriptions)
✅ PDI Inspections (pre-delivery inspections, objections)
✅ FFS/SFS Inspections (free service records)
✅ Campaign Services (recall campaigns, service campaigns)
✅ Repair Orders (RO numbers, service history)
✅ Vehicle Information (VIN, model, variant, dealership)

**Dealership Database Does NOT Contain:**
❌ Sales data (salespeople, revenue, profits)
❌ Customer purchase history
❌ Inventory or stock information
❌ Employee or HR data
❌ WhatsApp messages
❌ PakWheels forum discussions

**What you can ask about:**
- "How many warranty claims in December?"
- "Which dealership has most PDI inspections?"
- "Show complete service history for VIN [VIN]"
- "Compare warranty claims between dealerships"

**For other questions:**
- General questions → Use **Insights Mode**
- PakWheels forums → Use **PakWheels Mode**
- WhatsApp data → Use **WhatsApp Mode**"""

    def _handle_invalid_sql(self, question: str) -> str:
        """Handle cases where SQL generation failed validation"""

        return f"""I encountered an issue generating a safe database query for your question.

**Your Question:** "{question}"

**Possible reasons:**
- The question might be too complex for automated SQL generation
- Required information might be ambiguous

**What you can try:**
1. Rephrase your question more specifically
2. Break complex questions into simpler parts
3. Specify exact filters (VIN, dealership name, dates)

**Examples of good questions:**
- "How many warranty claims in December?"
- "Show PDI inspections for Lahore dealership"
- "Which VIN has most complaints?"
- "Compare warranty claims across different models"
- "Show complete history for VIN ABC123..."

Please try rephrasing your question."""

    def _generate_error_response(self, question: str, error: str) -> str:
        """Generate user-friendly error response"""

        return f"""Sorry, I encountered an error processing your dealership query.

**Your Question:** "{question}"

**Error:** {error}

**What you can try:**
1. Check if the VIN number is correct (17 characters)
2. Verify dealership names (Lahore, Karachi, Islamabad, etc.)
3. Try a simpler version of your question
4. Make sure you're asking about dealership data (warranty claims, PDI inspections, campaigns, etc.)

If the problem persists, please contact support."""
