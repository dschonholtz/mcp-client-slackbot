"""Unit tests for tool parser."""

import pytest

from mcp_simple_slackbot.tools.parser import ToolParser


class TestToolParser:
    """Test the ToolParser class."""
    
    def test_extract_tool_calls_no_tools(self):
        """Test extract_tool_calls with no tool calls."""
        response = "This is a simple response with no tool calls."
        tool_calls = ToolParser.extract_tool_calls(response)
        
        assert tool_calls == []
    
    def test_extract_tool_calls_single_tool(self):
        """Test extract_tool_calls with a single tool call."""
        response = """Here's what I found:
        
[TOOL] query
{"sql": "SELECT * FROM users LIMIT 10"}"""
        
        tool_calls = ToolParser.extract_tool_calls(response)
        
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "query"
        assert tool_calls[0]["arguments"] == {"sql": "SELECT * FROM users LIMIT 10"}
    
    def test_extract_tool_calls_multiple_tools(self):
        """Test extract_tool_calls with multiple tool calls."""
        response = """I'll help you with that:
        
[TOOL] query
{"sql": "SELECT * FROM users LIMIT 10"}

Now let's also check the orders:

[TOOL] query
{"sql": "SELECT * FROM orders LIMIT 5"}"""
        
        tool_calls = ToolParser.extract_tool_calls(response)
        
        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "query"
        assert tool_calls[0]["arguments"] == {"sql": "SELECT * FROM users LIMIT 10"}
        assert tool_calls[1]["tool_name"] == "query"
        assert tool_calls[1]["arguments"] == {"sql": "SELECT * FROM orders LIMIT 5"}
    
    def test_extract_tool_calls_invalid_json(self):
        """Test extract_tool_calls with invalid JSON arguments."""
        response = """Let me check that for you:
        
[TOOL] query
{"sql": "SELECT * FROM users LIMIT 10" invalid json}"""
        
        tool_calls = ToolParser.extract_tool_calls(response)
        
        # Should skip invalid JSON
        assert tool_calls == []
    
    def test_extract_tool_calls_missing_args(self):
        """Test extract_tool_calls with missing arguments."""
        response = """Let me check:
        
[TOOL] query"""
        
        tool_calls = ToolParser.extract_tool_calls(response)
        
        # Should skip tools with missing arguments
        assert tool_calls == []
    
    def test_split_response(self):
        """Test split_response method."""
        response = """Here's what I found:
        
[TOOL] query
{"sql": "SELECT * FROM users LIMIT 10"}"""
        
        non_tool_content, tool_calls = ToolParser.split_response(response)
        
        assert non_tool_content == "Here's what I found:"
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "query"
        
        # Test with no tools
        simple_response = "Just a simple response"
        non_tool_content, tool_calls = ToolParser.split_response(simple_response)
        
        assert non_tool_content == "Just a simple response"
        assert tool_calls == []