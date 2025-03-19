"""Tool execution and result handling."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from mcp_simple_slackbot.config.settings import MAX_TOOL_CALLS
from mcp_simple_slackbot.llm.client import LLMClient
from mcp_simple_slackbot.mcp.server import Server
from mcp_simple_slackbot.tools.parser import ToolParser


class ToolExecutor:
    """Execute tools and process results."""

    def __init__(self, servers: List[Server], llm_client: LLMClient) -> None:
        """Initialize tool executor.
        
        Args:
            servers: List of MCP servers
            llm_client: LLM client for result interpretation
        """
        self.servers = servers
        self.llm_client = llm_client
    
    async def process_tool_calls(self, response: str, conversation_id: str) -> str:
        """Process multiple tool calls from the LLM response.
        
        Args:
            response: LLM response text
            conversation_id: Unique identifier for the conversation
            
        Returns:
            Final interpretation or error message
        """
        try:
            # Check if there are any tool calls
            if "[TOOL]" not in response:
                return response

            # Parse tool calls
            non_tool_content, tool_calls = ToolParser.split_response(response)
            
            # Limit to max tool calls
            if len(tool_calls) > MAX_TOOL_CALLS:
                tool_calls = tool_calls[:MAX_TOOL_CALLS]
                logging.warning(f"Limiting to {MAX_TOOL_CALLS} tool calls out of {len(tool_calls)}")

            # Execute tools and collect results
            tool_results = await self._execute_tools(tool_calls)
            
            # If no tool was successfully executed, return original content
            if not tool_results:
                return non_tool_content if non_tool_content else response
            
            # Get interpretation from LLM
            interpretation = await self._get_interpretation(tool_results)
            return interpretation

        except Exception as e:
            logging.error(f"Error executing tools: {e}", exc_info=True)
            return (
                f"I tried to use one or more tools, but encountered an error: {str(e)}\n\n"
                f"Here's my response without the tools:\n\n{response.split('[TOOL]')[0]}"
            )
    
    async def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute multiple tools and collect results.
        
        Args:
            tool_calls: List of tool calls with tool_name and arguments
            
        Returns:
            List of tool execution results
        """
        tool_results = []
        
        for i, tool_call in enumerate(tool_calls):
            tool_name = tool_call["tool_name"]
            arguments = tool_call["arguments"]
            
            # Find the appropriate server for this tool
            tool_executed = False
            for server in self.servers:
                try:
                    server_tools = [tool.name for tool in await server.list_tools()]
                    if tool_name in server_tools:
                        # Execute the tool
                        tool_executed = True
                        try:
                            result = await server.execute_tool(tool_name, arguments)
                            tool_results.append({
                                "tool": tool_name,
                                "success": True,
                                "arguments": arguments,
                                "result": result,
                            })
                        except Exception as e:
                            tool_results.append({
                                "tool": tool_name,
                                "success": False,
                                "arguments": arguments,
                                "error": str(e),
                                "result": None,
                            })
                        break
                except Exception as e:
                    logging.error(f"Error checking tools on server: {e}")
                    continue
            
            if not tool_executed:
                tool_results.append({
                    "tool": tool_name,
                    "success": False,
                    "error": f"Tool '{tool_name}' not available",
                    "result": None,
                })
        
        return tool_results
    
    async def _get_interpretation(self, tool_results: List[Dict]) -> str:
        """Get LLM interpretation of tool results.
        
        Args:
            tool_results: List of tool execution results
            
        Returns:
            Interpreted response from LLM
        """
        # Format tool results for LLM
        tool_results_text = self._format_tool_results(tool_results)
        
        # Get final interpretation from LLM
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. You've just used multiple tools and received results. "
                    "Interpret these results for the user in a clear, helpful way that addresses their original question. "
                    "Focus on the most relevant information from the tool results."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"I executed {len(tool_results)} tools based on the request and got these results:"
                    f"{tool_results_text}\n\n"
                    f"Please provide a helpful response that addresses the original question using this information."
                ),
            },
        ]
        
        interpretation = await self.llm_client.get_response(messages)
        return interpretation
    
    @staticmethod
    def _format_tool_results(tool_results: List[Dict]) -> str:
        """Format tool results for LLM consumption.
        
        Args:
            tool_results: List of tool execution results
            
        Returns:
            Formatted string with tool results
        """
        tool_results_text = ""
        for i, result in enumerate(tool_results):
            tool_name = result["tool"]
            if result["success"]:
                result_data = result["result"]
                # Format the result data
                if isinstance(result_data, dict):
                    result_str = json.dumps(result_data, indent=2)
                else:
                    result_str = str(result_data)
                tool_results_text += f"\n\nTool {i+1}: {tool_name}\nSuccess: True\nResult:\n{result_str}"
            else:
                error = result.get("error", "Unknown error")
                tool_results_text += f"\n\nTool {i+1}: {tool_name}\nSuccess: False\nError: {error}"
        
        return tool_results_text