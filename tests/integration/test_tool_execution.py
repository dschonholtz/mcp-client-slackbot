"""Integration tests for tool execution."""

import asyncio
from unittest import mock

import pytest

from mcp_simple_slackbot.llm.client import LLMClient
from mcp_simple_slackbot.mcp.server import Server
from mcp_simple_slackbot.mcp.tool import Tool
from mcp_simple_slackbot.tools.executor import ToolExecutor


class MockServer:
    """Mock Server for testing."""
    
    def __init__(self, name, tools):
        """Initialize with predefined tools."""
        self.name = name
        self._tools = tools
    
    async def list_tools(self):
        """Return mock tools."""
        return self._tools
    
    async def execute_tool(self, tool_name, arguments, **kwargs):
        """Mock tool execution."""
        if tool_name == "query":
            return {"results": [{"id": 1, "name": "Test User"}]}
        elif tool_name == "fetch":
            return {"content": "<html><body>Test content</body></html>"}
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


class MockLLMClient:
    """Mock LLM client for testing."""
    
    async def get_response(self, messages):
        """Return a predetermined response based on the content."""
        # Check if this is for error handling
        for msg in messages:
            if "Error:" in msg.get("content", ""):
                return "Error occurred: Tool 'unknown_tool' not available"
            
        return "Here's the interpreted result: 1 user found named Test User."


@pytest.fixture
def mock_server():
    """Create a mock server with predefined tools."""
    query_tool = Tool(
        "query",
        "Query a database",
        {
            "type": "object",
            "properties": {
                "sql": {"description": "SQL query to execute"}
            },
            "required": ["sql"]
        }
    )
    
    fetch_tool = Tool(
        "fetch",
        "Fetch a web page",
        {
            "type": "object",
            "properties": {
                "url": {"description": "URL to fetch"}
            },
            "required": ["url"]
        }
    )
    
    return MockServer("test", [query_tool, fetch_tool])


@pytest.fixture
def tool_executor(mock_server):
    """Create a tool executor with mock components."""
    servers = [mock_server]
    llm_client = MockLLMClient()
    
    return ToolExecutor(servers, llm_client)


class TestToolExecution:
    """Integration tests for ToolExecutor."""
    
    @pytest.mark.asyncio
    async def test_process_tool_calls_single_tool(self, tool_executor):
        """Test processing a response with a single tool call."""
        response = """Let me check the database:
        
[TOOL] query
{"sql": "SELECT * FROM users LIMIT 1"}"""
        
        result = await tool_executor.process_tool_calls(response, "test-conversation")
        
        assert "interpreted result" in result.lower()
        assert "test user" in result.lower()
    
    @pytest.mark.asyncio
    async def test_process_tool_calls_unknown_tool(self, tool_executor):
        """Test processing a response with an unknown tool."""
        response = """Let me try this:
        
[TOOL] unknown_tool
{"param": "value"}"""
        
        result = await tool_executor.process_tool_calls(response, "test-conversation")
        
        # Should include error information
        assert "tool 'unknown_tool' not available" in result.lower()
    
    @pytest.mark.asyncio
    async def test_process_tool_calls_no_tools(self, tool_executor):
        """Test processing a response with no tool calls."""
        response = "This is a simple response with no tool calls."
        
        result = await tool_executor.process_tool_calls(response, "test-conversation")
        
        # Should return the original response
        assert result == response