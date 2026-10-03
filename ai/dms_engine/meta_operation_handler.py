"""
Meta-Operation Handler for DMS Pipeline

Handles queries that operate on PREVIOUS ANSWERS (not database queries).
These operations transform/reformat the previous response WITHOUT re-querying the DB.

META-OPERATION TYPES:
=====================
1. SUMMARIZE: "Summarize above in 100 words"
2. ELABORATE: "Elaborate on the first point", "Explain more"
3. REFORMAT_BULLETS: "Give me that in bullet points"
4. REFORMAT_CHART: "Convert to chart form"
5. REFORMAT_TABLE: "Show as table"
6. GENERATE_REPORT: "Create a report for my manager"
7. GENERAL_TRANSFORM: Any other transformation

WORKFLOW:
=========
User Query (complex) → DMS Pipeline → SQL → Results → Natural Answer
    ↓
User: "Summarize above in 100 words"
    ↓
Meta-Operation Handler → Extract previous answer → Transform with LLM
    ↓
Return transformed answer (NO SQL EXECUTION!)

EDGE CASES HANDLED:
===================
- No previous answer in history → Error message
- LLM transformation fails → Error message
- Previous answer too short → Skip transformation
- Invalid chat history format → Error message

"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from ai.llm_client import BaseLLMClient


@dataclass
class MetaOperationResult:
    """
    Result from meta-operation (transformed answer).

    Contains:
        - query: User's meta-operation query
        - original_answer: Previous assistant answer
        - transformed_answer: New transformed answer
        - operation_type: Type of operation performed
        - success: Whether transformation succeeded
        - error_message: Error message if failed
        - execution_time: Time taken (seconds)
    """
    query: str
    original_answer: str
    transformed_answer: str
    operation_type: str  # 'summarize', 'elaborate', 'reformat_bullets', etc.
    success: bool
    error_message: Optional[str] = None
    execution_time: float = 0.0


class MetaOperationHandler:
    """
    Handles meta-operations on previous DMS answers.

    Meta-operations are queries that transform/operate on the PREVIOUS ANSWER
    rather than querying new data from the database.

    Examples:
        - "Summarize above in 100 words" → Summarize previous answer
        - "Elaborate on the first point" → Expand on previous answer
        - "Give me that in bullet points" → Reformat previous answer
        - "Convert to chart form" → Transform to chart format
        - "Generate a report for my manager" → Create formal report

    CRITICAL: Meta-operations bypass the DMS pipeline entirely!
    No SQL generation, no database queries, just LLM transformation.
    """

    def __init__(self, llm: BaseLLMClient, verbose: bool = True):
        """
        Initialize meta-operation handler.

        Args:
            llm: LLM client for transformations
            verbose: Enable detailed logging (default: True)
        """
        self.llm = llm
        self.verbose = verbose

        if self.verbose:
            print("[MetaOpHandler] Initialized meta-operation handler")

    def handle(
        self,
        query: str,
        chat_history: List[Dict[str, str]]
    ) -> MetaOperationResult:
        """
        Handle meta-operation on previous answer.

        WORKFLOW:
        =========
        1. Validate inputs (query, history)
        2. Extract previous assistant answer from history
        3. Detect operation type (summarize, elaborate, etc.)
        4. Build transformation prompt
        5. Call LLM to transform answer
        6. Return MetaOperationResult

        Args:
            query: User's meta-operation query
            chat_history: Recent conversation (must contain previous answer)

        Returns:
            MetaOperationResult with transformed answer

        Edge Cases:
            - No chat history → Error
            - No previous assistant answer → Error
            - LLM transformation fails → Error
            - Previous answer too short → Skip transformation

        Examples:
            >>> handler.handle("Summarize above in 100 words", history)
            MetaOperationResult(
                query="Summarize above in 100 words",
                original_answer="...",
                transformed_answer="Summary: ...",
                operation_type="summarize",
                success=True
            )
        """
        import time
        start_time = time.time()

        if self.verbose:
            print(f"\n[MetaOpHandler] ════════════════════════════════════════════════")
            print(f"[MetaOpHandler] META-OPERATION START")
            print(f"[MetaOpHandler] Query: '{query}'")

        # =====================================================================
        # EDGE CASE 1: Empty or invalid query
        # =====================================================================
        if not query or len(query.strip()) == 0:
            if self.verbose:
                print(f"[MetaOpHandler] ✗ ERROR: Empty query")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query if query else "",
                original_answer="",
                transformed_answer="I received an empty meta-operation query. Please rephrase your request.",
                operation_type="error",
                success=False,
                error_message="Empty query",
                execution_time=time.time() - start_time
            )

        # =====================================================================
        # EDGE CASE 2: No chat history
        # =====================================================================
        if not chat_history or len(chat_history) == 0:
            if self.verbose:
                print(f"[MetaOpHandler] ✗ ERROR: No chat history provided")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query,
                original_answer="",
                transformed_answer="I don't see a previous answer to operate on. Please ask a new question first.",
                operation_type="error",
                success=False,
                error_message="No chat history",
                execution_time=time.time() - start_time
            )

        # =====================================================================
        # STEP 1: Extract previous assistant answer
        # =====================================================================
        if self.verbose:
            print(f"[MetaOpHandler] Chat history: {len(chat_history)} messages")
            print(f"[MetaOpHandler] Extracting previous assistant answer...")

        previous_answer = self._get_previous_answer(chat_history)

        # =====================================================================
        # EDGE CASE 3: No previous assistant answer found
        # =====================================================================
        if not previous_answer:
            if self.verbose:
                print(f"[MetaOpHandler] ✗ ERROR: No previous assistant answer found")
                print(f"[MetaOpHandler] Chat history messages:")
                for i, msg in enumerate(chat_history[-3:], 1):
                    role = msg.get('role', 'unknown')
                    print(f"[MetaOpHandler]   {i}. {role}: {msg.get('content', '')[:50]}...")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query,
                original_answer="",
                transformed_answer="I don't see a previous answer to operate on. Please ask a question first, then I can help transform the answer.",
                operation_type="error",
                success=False,
                error_message="No previous assistant answer found in chat history",
                execution_time=time.time() - start_time
            )

        if self.verbose:
            print(f"[MetaOpHandler] ✓ Found previous answer ({len(previous_answer)} chars)")
            print(f"[MetaOpHandler]   Preview: {previous_answer[:100]}...")

        # =====================================================================
        # EDGE CASE 4: Previous answer too short
        # =====================================================================
        if len(previous_answer.strip()) < 20:
            if self.verbose:
                print(f"[MetaOpHandler] ⚠ Previous answer too short ({len(previous_answer)} chars)")
                print(f"[MetaOpHandler] Returning previous answer as-is")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query,
                original_answer=previous_answer,
                transformed_answer=previous_answer,  # Return as-is
                operation_type="passthrough",
                success=True,
                execution_time=time.time() - start_time
            )

        # =====================================================================
        # STEP 2: Detect operation type
        # =====================================================================
        operation_type = self._detect_operation_type(query)

        if self.verbose:
            print(f"[MetaOpHandler] Operation type: {operation_type.upper()}")

        # =====================================================================
        # STEP 3: Build transformation prompt
        # =====================================================================
        if self.verbose:
            print(f"[MetaOpHandler] Building transformation prompt...")

        try:
            prompt = self._build_transformation_prompt(
                query=query,
                previous_answer=previous_answer,
                operation_type=operation_type
            )

            if self.verbose:
                print(f"[MetaOpHandler] ✓ Prompt built ({len(prompt)} chars)")

        except Exception as e:
            if self.verbose:
                print(f"[MetaOpHandler] ✗ ERROR building prompt: {e}")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query,
                original_answer=previous_answer,
                transformed_answer=f"Error building transformation prompt: {str(e)}",
                operation_type=operation_type,
                success=False,
                error_message=f"Prompt building error: {str(e)}",
                execution_time=time.time() - start_time
            )

        # =====================================================================
        # STEP 4: Call LLM to transform answer
        # =====================================================================
        if self.verbose:
            print(f"[MetaOpHandler] Calling LLM for transformation...")

        try:
            messages = [{"role": "user", "content": prompt}]

            # Get max_tokens based on operation type
            max_tokens = self._get_max_tokens(operation_type)

            if self.verbose:
                print(f"[MetaOpHandler]   Max tokens: {max_tokens}")
                print(f"[MetaOpHandler]   Temperature: 0.3 (slightly creative)")

            response = self.llm.generate(
                messages,
                max_tokens=max_tokens,
                temperature=0.3  # Slightly creative for rephrasing
            )

            transformed = response.content.strip()

            if self.verbose:
                print(f"[MetaOpHandler] ✓ LLM transformation successful ({len(transformed)} chars)")
                print(f"[MetaOpHandler]   Preview: {transformed[:100]}...")

        except Exception as e:
            # =================================================================
            # EDGE CASE 5: LLM transformation fails
            # =================================================================
            if self.verbose:
                print(f"[MetaOpHandler] ✗ LLM ERROR: {e}")
                print(f"[MetaOpHandler] Returning error message")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query,
                original_answer=previous_answer,
                transformed_answer=f"I encountered an error while transforming the answer: {str(e)}. Please try rephrasing your request.",
                operation_type=operation_type,
                success=False,
                error_message=f"LLM transformation error: {str(e)}",
                execution_time=time.time() - start_time
            )

        # =====================================================================
        # EDGE CASE 6: Empty transformation result
        # =====================================================================
        if not transformed or len(transformed.strip()) < 10:
            if self.verbose:
                print(f"[MetaOpHandler] ⚠ Transformed result too short or empty")
                print(f"[MetaOpHandler] Returning previous answer as-is")
                print(f"[MetaOpHandler] ════════════════════════════════════════════════")

            return MetaOperationResult(
                query=query,
                original_answer=previous_answer,
                transformed_answer=previous_answer,  # Return original
                operation_type=operation_type,
                success=True,
                execution_time=time.time() - start_time
            )

        # =====================================================================
        # SUCCESS: Return transformed answer
        # =====================================================================
        execution_time = time.time() - start_time

        if self.verbose:
            print(f"[MetaOpHandler] ✓ META-OPERATION COMPLETE")
            print(f"[MetaOpHandler] Operation: {operation_type}")
            print(f"[MetaOpHandler] Original length: {len(previous_answer)} chars")
            print(f"[MetaOpHandler] Transformed length: {len(transformed)} chars")
            print(f"[MetaOpHandler] Change: {len(transformed) - len(previous_answer):+d} chars")
            print(f"[MetaOpHandler] Execution time: {execution_time:.2f}s")
            print(f"[MetaOpHandler] ════════════════════════════════════════════════")

        return MetaOperationResult(
            query=query,
            original_answer=previous_answer,
            transformed_answer=transformed,
            operation_type=operation_type,
            success=True,
            execution_time=execution_time
        )

    def _get_previous_answer(self, chat_history: List[Dict[str, str]]) -> Optional[str]:
        """
        Extract last assistant answer from chat history.

        Searches messages in reverse order (most recent first).

        Args:
            chat_history: List of conversation messages

        Returns:
            Last assistant answer or None if not found

        Edge Cases:
            - No messages → None
            - No assistant messages → None
            - Invalid format → None
        """
        if not chat_history:
            return None

        # Find last assistant message (scan in reverse)
        for msg in reversed(chat_history):
            try:
                role = msg.get('role', '').lower()
                if role == 'assistant':
                    content = msg.get('content', '').strip()
                    if content:  # Non-empty content
                        return content
            except Exception as e:
                if self.verbose:
                    print(f"[MetaOpHandler]   ⚠ Error processing message: {e}")
                continue

        return None

    def _detect_operation_type(self, query: str) -> str:
        """
        Detect what type of meta-operation the user wants.

        OPERATION TYPES:
        ================
        - summarize: Condense information
        - elaborate: Expand with more details
        - reformat_bullets: Convert to bullet points
        - reformat_chart: Prepare for chart/graph
        - reformat_table: Convert to table format
        - generate_report: Create formal business report
        - general_transform: Other transformations

        Args:
            query: User's meta-operation query

        Returns:
            Operation type string

        Edge Cases:
            - Multiple matches → First match wins
            - No match → "general_transform"
            - Empty query → "general_transform"
        """
        if not query:
            return "general_transform"

        query_lower = query.lower()

        # Check for each operation type (order matters - most specific first)
        if any(kw in query_lower for kw in ['summarize', 'summary', 'sum up', 'condense', 'brief']):
            return 'summarize'

        elif any(kw in query_lower for kw in ['elaborate', 'explain more', 'more details', 'expand', 'tell me more']):
            return 'elaborate'

        elif any(kw in query_lower for kw in ['bullet', 'bullet points', 'list', 'numbered list', 'points']):
            return 'reformat_bullets'

        elif any(kw in query_lower for kw in ['chart', 'graph', 'visual', 'visualize', 'plot']):
            return 'reformat_chart'

        elif any(kw in query_lower for kw in ['table', 'tabular', 'spreadsheet']):
            return 'reformat_table'

        elif any(kw in query_lower for kw in ['report', 'generate report', 'create report', 'for my manager', 'for executive', 'executive summary']):
            return 'generate_report'

        else:
            return 'general_transform'

    def _get_max_tokens(self, operation_type: str) -> int:
        """
        Get appropriate max_tokens for operation type.

        Different operations need different output lengths.

        Args:
            operation_type: Type of operation

        Returns:
            Max tokens value
        """
        token_map = {
            'summarize': 500,  # Shorter output
            'elaborate': 1500,  # Longer output
            'reformat_bullets': 1000,  # Medium
            'reformat_chart': 1000,  # Medium
            'reformat_table': 1500,  # Medium-long
            'generate_report': 2500,  # Longest
            'general_transform': 1500,  # Default medium-long
        }

        return token_map.get(operation_type, 1500)

    def _build_transformation_prompt(
        self,
        query: str,
        previous_answer: str,
        operation_type: str
    ) -> str:
        """
        Build prompt for LLM to transform the previous answer.

        Constructs operation-specific instructions for the LLM.

        Args:
            query: User's meta-operation query
            previous_answer: Previous assistant answer to transform
            operation_type: Type of operation to perform

        Returns:
            Complete prompt string

        Edge Cases:
            - Unknown operation type → Use general instructions
            - Very long previous answer → Truncate in prompt
        """
        # Truncate previous answer if too long (keep first 5000 chars)
        if len(previous_answer) > 5000:
            previous_answer_truncated = previous_answer[:5000] + "\n\n[... truncated for brevity ...]"
            if self.verbose:
                print(f"[MetaOpHandler]   Previous answer truncated ({len(previous_answer)} → 5000 chars)")
        else:
            previous_answer_truncated = previous_answer

        base_prompt = f"""You are a data analyst assistant helping with DMS (Dealer Management System) queries.

**PREVIOUS ANSWER:**
{previous_answer_truncated}

**USER REQUEST:** "{query}"

**YOUR TASK:** Transform the previous answer according to the user's request.

"""

        # Add operation-specific instructions
        if operation_type == 'summarize':
            base_prompt += """
**INSTRUCTIONS:**
- Provide a concise summary
- Keep key statistics and insights
- Remove verbose explanations
- Preserve important numbers/dates/VINs
- Use 100-200 words maximum
- Focus on essential information only
"""

        elif operation_type == 'elaborate':
            base_prompt += """
**INSTRUCTIONS:**
- Expand on the key points
- Add context and explanations
- Break down complex terms
- Provide examples if relevant
- Use clear, detailed language
- Maintain professional DMS terminology
"""

        elif operation_type == 'reformat_bullets':
            base_prompt += """
**INSTRUCTIONS:**
- Convert to clear bullet points
- One key insight per bullet
- Use concise language
- Preserve all important data (VINs, dates, numbers)
- Format: • Point 1\\n• Point 2
- Group related items together
"""

        elif operation_type == 'reformat_chart':
            base_prompt += """
**INSTRUCTIONS:**
- Format data suitable for charts/graphs
- Extract numerical data
- Suggest appropriate chart type (bar, line, pie)
- Provide axis labels and data series
- Include data in tabular format
- Make it easy to visualize
"""

        elif operation_type == 'reformat_table':
            base_prompt += """
**INSTRUCTIONS:**
- Convert to markdown table format
- Use | Column1 | Column2 | format
- Include header row with alignment
- Keep data aligned and readable
- Preserve all important information
"""

        elif operation_type == 'generate_report':
            base_prompt += """
**INSTRUCTIONS:**
- Create a professional business report
- Include sections: Executive Summary, Key Findings, Data Analysis, Recommendations
- Use formal business language
- Highlight critical metrics
- Make it manager/executive-ready
- Use clear headings and structure
"""

        else:
            # General transformation
            base_prompt += """
**INSTRUCTIONS:**
- Transform the previous answer as requested
- Keep all important information (VINs, dates, dealer IDs, etc.)
- Improve clarity and readability
- Maintain professional tone
- Preserve data accuracy
"""

        base_prompt += "\n\n**YOUR TRANSFORMED ANSWER:**"

        return base_prompt
