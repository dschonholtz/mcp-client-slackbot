"""Tool representation and formatting for MCP servers."""

from typing import Any, Dict


class Tool:
    """Represents a tool with its properties and formatting."""

    def __init__(
        self, name: str, description: str, input_schema: Dict[str, Any], is_system: bool = False
    ) -> None:
        """Initialize a tool.
        
        Args:
            name: The name of the tool
            description: The description of the tool
            input_schema: The JSON schema for the tool's input
            is_system: Whether this is a system tool not from an MCP server
        """
        self.name: str = name
        self.description: str = description
        self.input_schema: Dict[str, Any] = input_schema
        self.is_system: bool = is_system

    def format_for_llm(self) -> str:
        """Format tool information for LLM.

        Returns:
            A formatted string describing the tool.
        """
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
Tool: {self.name}
Description: {self.description}
Arguments:
{chr(10).join(args_desc)}
"""