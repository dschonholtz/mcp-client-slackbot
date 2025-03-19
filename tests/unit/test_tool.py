"""Unit tests for MCP Tool."""

import pytest

from mcp_simple_slackbot.mcp.tool import Tool


class TestTool:
    """Test the Tool class."""
    
    def test_initialization(self):
        """Test tool initialization."""
        name = "test_tool"
        description = "A test tool"
        input_schema = {
            "type": "object",
            "properties": {
                "param1": {"description": "Parameter 1"},
                "param2": {"description": "Parameter 2"}
            },
            "required": ["param1"]
        }
        
        tool = Tool(name, description, input_schema)
        
        assert tool.name == name
        assert tool.description == description
        assert tool.input_schema == input_schema
    
    def test_format_for_llm(self):
        """Test formatting tool for LLM."""
        tool = Tool(
            "query",
            "Query a database",
            {
                "type": "object",
                "properties": {
                    "sql": {"description": "SQL query to execute"},
                    "limit": {"description": "Limit results"}
                },
                "required": ["sql"]
            }
        )
        
        formatted = tool.format_for_llm()
        
        # Check that all required components are in the output
        assert "Tool: query" in formatted
        assert "Description: Query a database" in formatted
        assert "- sql: SQL query to execute (required)" in formatted
        assert "- limit: Limit results" in formatted