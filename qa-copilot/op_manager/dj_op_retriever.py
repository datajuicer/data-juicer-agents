# -*- coding: utf-8 -*-
"""Data-Juicer Operator Retriever"""

import logging
import re
import traceback
from typing import List, Dict

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock

from data_juicer_agents.tools.op_manager.op_retrieval import (
    retrieve_ops_vector,
    init_dj_func_info,
    get_dj_func_info,
)


class DJOperatorRetriever:

    def __init__(self):
        init_dj_func_info()

        self.operators_count = len(get_dj_func_info())
        logging.info(
            f"Initialized DJOperatorRetriever with {self.operators_count} operators"
        )

    async def search_operators(
        self,
        query: str,
        limit: int = 10,
    ) -> ToolResponse:
        """
        Search for relevant Data-Juicer operators based on user query.

        This tool searches through 100+ Data-Juicer operators and returns
        the most relevant ones for data processing tasks.

        Args:
            query (str): Description of data processing requirement.
            Note: It is recommended to use English query.
                Examples:
                - "filter low quality text"
                - "remove duplicate images"
                - "clean special characters"
                - "aggregate nested content"
            limit (int): Maximum number of operators to return (default: 10, max: 30)

        Returns:
            ToolResponse with list of relevant operator names and brief descriptions.
            For detailed information about a specific operator, use get_operator_details().
        """
        try:
            limit = max(1, min(limit, 30))

            operator_names = retrieve_ops_vector(query, limit=limit)

            dj_func_info = get_dj_func_info()
            operator_summaries = []

            for op_name in operator_names:
                op_info = next(
                    (op for op in dj_func_info if op["class_name"] == op_name), None
                )
                if op_info:
                    brief_desc = self._extract_brief_description(op_info["class_desc"])
                    operator_summaries.append(
                        {
                            "name": op_info["class_name"],
                            "brief_description": brief_desc,
                        }
                    )

            result_text = self._format_search_results(query, operator_summaries)

            return ToolResponse(
                metadata={
                    "success": True,
                    "query": query,
                    "found_count": len(operator_summaries),
                    "operator_names": operator_names, 
                },
                content=[
                    TextBlock(
                        type="text",
                        text=result_text,
                    ),
                ],
            )

        except Exception as e:
            traceback.print_exc()
            logging.error(f"Error searching operators: {str(e)}")
            return ToolResponse(
                metadata={
                    "success": False,
                    "error": str(e),
                },
                content=[
                    TextBlock(
                        type="text",
                        text=f"❌ Error searching operators: {str(e)}",
                    ),
                ],
            )

    async def get_operator_details(
        self,
        operator_name: str,
    ) -> ToolResponse:
        """
        Get detailed information about a specific Data-Juicer operator.

        This tool provides comprehensive information including:
        - Full description
        - All parameters and their types
        - Usage examples
        - Code and test paths

        Args:
            operator_name (str): Exact name of the operator
                (e.g., "nested_aggregator", "language_id_score_filter")

        Returns:
            ToolResponse with detailed operator documentation.
        """
        try:
            dj_func_info = get_dj_func_info()
            op_info = next(
                (op for op in dj_func_info if op["class_name"] == operator_name), None
            )

            if not op_info:
                similar_ops = self._find_similar_operators(operator_name, dj_func_info)

                error_msg = f"❌ Operator '{operator_name}' not found.\n\n"
                if similar_ops:
                    error_msg += "Did you mean one of these?\n"
                    for op in similar_ops[:5]:
                        error_msg += f"  - {op}\n"

                return ToolResponse(
                    metadata={"success": False},
                    content=[
                        TextBlock(
                            type="text",
                            text=error_msg,
                        ),
                    ],
                )

            details_text = self._format_operator_details(op_info)

            return ToolResponse(
                metadata={
                    "success": True,
                    "operator_name": operator_name,
                },
                content=[
                    TextBlock(
                        type="text",
                        text=details_text,
                    ),
                ],
            )

        except Exception as e:
            logging.error(f"Error getting operator details: {str(e)}")
            return ToolResponse(
                metadata={"success": False, "error": str(e)},
                content=[
                    TextBlock(
                        type="text",
                        text=f"❌ Error: {str(e)}",
                    ),
                ],
            )

    def _extract_brief_description(self, full_desc: str) -> str:
        """Extract the first sentence of the description"""
        sentences = full_desc.split("\n\n")
        first_paragraph = sentences[0].strip()

        first_sentence = first_paragraph.split(".")[0]

        if len(first_sentence) > 150:
            first_sentence = first_sentence[:147] + "..."

        return first_sentence

    def _parse_arguments(self, arguments_str: str) -> List[Dict]:
        """Parse arguments strings into structured data"""
        params = []

        # param_name (<type>): description
        pattern = r"(\w+)\s*\(([^)]+)\):\s*([^\n]+)"
        matches = re.findall(pattern, arguments_str)

        for param_name, param_type, param_desc in matches:
            params.append(
                {
                    "name": param_name,
                    "type": param_type.strip(),
                    "description": param_desc.strip(),
                }
            )

        return params

    def _format_search_results(self, query: str, operators: List[Dict]) -> str:
        if not operators:
            return f"❌ No operators found for query: '{query}'"

        result = f"🔍 **Found {len(operators)} relevant operators**\n"
        result += f'Query: "{query}"\n\n'
        result += "---\n\n"

        for i, op in enumerate(operators, 1):
            result += f"**{i}. {op['name']}**\n"
            result += f"   {op['brief_description']}\n\n"

        result += "---\n\n"
        result += "**Tip**: If results don't match your need, try rewriting the query—rephrase the intent, "
        result += "use synonyms, or emphasize different constraints. Retry search 1-3 times with different formulations."

        return result

    def _format_operator_details(self, op_info: Dict) -> str:
        details = f"# 📋 {op_info['class_name']}\n\n"

        details += f"## Description\n\n{op_info['class_desc']}\n\n"

        details += f"## Parameters\n\n"

        params = self._parse_arguments(op_info["arguments"])
        if params:
            for param in params:
                details += f"### `{param['name']}`\n"
                details += f"- **Type**: `{param['type']}`\n"
                details += f"- **Description**: {param['description']}\n\n"
        else:
            details += "*No parameters documented*\n\n"

        details += f"## Usage Example\n\n"
        details += "```yaml\n"
        details += f"# Add to your Data-Juicer config.yaml\n"
        details += f"process:\n"
        details += f"  - {op_info['class_name']}:\n"

        if params:
            for param in params:
                details += f"      {param['name']}: <value>\n"

        op_type = op_info["class_name"].split("_")[-1]

        details += (
            f"\ncode path: https://github.com/datajuicer/data-juicer/tree/main/data_juicer/core/{op_type}/{op_info['class_name']}.py\n"
        )
        details += f"test path: https://github.com/datajuicer/data-juicer/tree/main/tests/ops/{op_type}/test_{op_info['class_name']}.py\n"
        details += f"op_doc path: https://github.com/datajuicer/data-juicer/tree/main/docs/operators/{op_type}/{op_info['class_name']}.md\n"

        details += "```\n"

        return details

    def _find_similar_operators(
        self, query: str, dj_func_info: List[Dict], limit: int = 5
    ) -> List[str]:
        """Find similar operator names (simple string matching)"""
        query_lower = query.lower()
        similar = []

        for op in dj_func_info:
            op_name = op["class_name"]
            if query_lower in op_name.lower():
                similar.append(op_name)

        return similar[:limit]
