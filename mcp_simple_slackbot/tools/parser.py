"""Parse tool calls from LLM responses."""

import json
import logging
import re
from typing import Dict, List, Tuple


class ToolParser:
    """Parse tool calls from LLM responses."""

    @staticmethod
    def extract_tool_calls(response: str) -> List[Dict]:
        """Extract tool calls from LLM response text.
        
        Args:
            response: Text response from LLM
            
        Returns:
            List of dictionaries with tool_name and arguments
        """
        if "[TOOL]" not in response:
            logging.debug("No [TOOL] tag found in response")
            return []
        
        # Use regex to find all tool call blocks
        # This handles multiple tool calls more reliably than simple splitting
        pattern = r'\[TOOL\]\s*([^\n]+)\s*\n\s*(\{.*?\})'
        logging.debug(f"Searching for tool calls with pattern: {pattern}")
        logging.debug(f"Response text: {response}")
        
        matches = re.findall(pattern, response, re.DOTALL)
        logging.debug(f"Found {len(matches)} pattern matches")
        
        tool_calls = []
        for tool_name, args_text in matches:
            logging.debug(f"Processing match: '{tool_name}' with args '{args_text}'")
            try:
                tool_name = tool_name.strip()
                logging.debug(f"Attempting to parse JSON: {args_text}")
                arguments = json.loads(args_text)
                tool_calls.append({
                    "tool_name": tool_name,
                    "arguments": arguments
                })
                logging.debug(f"Successfully parsed tool call: {tool_name}")
            except json.JSONDecodeError as e:
                logging.warning(f"Invalid JSON arguments for tool {tool_name}: {e}")
                logging.warning(f"Problematic JSON: {args_text}")
            except Exception as e:
                logging.error(f"Error parsing tool call: {e}")
                
        logging.debug(f"Extracted {len(tool_calls)} valid tool calls")
        return tool_calls
    
    @staticmethod
    def split_response(response: str) -> Tuple[str, List[Dict]]:
        """Split LLM response into content and tool calls.
        
        Args:
            response: Text response from LLM
            
        Returns:
            Tuple of (non-tool content, list of tool calls)
        """
        if "[TOOL]" not in response:
            return response, []
            
        parts = response.split("[TOOL]")
        non_tool_content = parts[0].strip()
        tool_calls = ToolParser.extract_tool_calls(response)
        
        return non_tool_content, tool_calls