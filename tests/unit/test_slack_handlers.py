"""Unit tests for Slack event handlers."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_simple_slackbot.slack.handlers import SlackEventHandlers
from mcp_simple_slackbot.mcp.tool import Tool


@pytest.fixture
def mock_client():
    """Create a mock Slack client."""
    return AsyncMock()


@pytest.fixture
def mock_conversation_manager():
    """Create a mock conversation manager."""
    manager = MagicMock()
    manager.get_messages.return_value = []
    manager.add_message = AsyncMock()
    return manager


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_tool_executor():
    """Create a mock tool executor."""
    executor = AsyncMock()
    executor.servers = []
    return executor


@pytest.fixture
def mock_tools():
    """Create a list of mock tools."""
    return [
        Tool(
            name="test_tool",
            description="A test tool",
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"description": "Parameter 1"}
                },
                "required": ["param1"]
            }
        )
    ]


@pytest.fixture
def handlers(mock_client, mock_conversation_manager, mock_llm_client, 
             mock_tool_executor, mock_tools):
    """Create a SlackEventHandlers instance with mocks."""
    return SlackEventHandlers(
        mock_client,
        mock_conversation_manager,
        mock_llm_client,
        mock_tool_executor,
        mock_tools,
        "U12345"
    )


@pytest.mark.asyncio
async def test_initialization(handlers, mock_tools):
    """Test handler initialization."""
    # Check that system tools are added
    assert len(handlers.tools) == len(mock_tools) + 2
    
    # Check that handoff tool exists
    handoff_tool = next((t for t in handlers.tools if t.name == "handoff"), None)
    assert handoff_tool is not None
    assert handoff_tool.is_system is True
    
    # Check that end_response tool exists
    end_tool = next((t for t in handlers.tools if t.name == "end_response"), None)
    assert end_tool is not None
    assert end_tool.is_system is True


@pytest.mark.asyncio
async def test_handle_mention(handlers, mock_llm_client):
    """Test handle_mention method."""
    # We'll use patch to intercept _process_message method to simplify testing
    with patch.object(handlers, '_process_message') as mock_process:
        # Mock say function
        say = AsyncMock()
        
        # Mock event data
        event = {
            "channel": "C12345",
            "user": "U67890",
            "text": "<@U12345> Hello bot",
            "ts": "1234567890.123456"
        }
        
        # Call the method
        await handlers.handle_mention(event, say)
        
        # Verify _process_message was called with correct arguments
        mock_process.assert_called_once_with(event, say)


@pytest.mark.asyncio
async def test_process_multiple_tools(handlers, mock_llm_client, mock_tool_executor):
    """Test processing multiple tools in sequence."""
    # Mock say function
    say = AsyncMock()
    
    # Set up conversation details
    conversation_id = "C12345-1234567890.123456"
    channel = "C12345"
    thread_ts = "1234567890.123456"
    
    # Mock conversation messages
    messages = [{"role": "system", "content": "System prompt"}]
    
    # Mock tool server
    mock_server = AsyncMock()
    mock_server.list_tools.return_value = [
        Tool("test_tool", "Test tool", {})
    ]
    mock_server.execute_tool.return_value = {"result": "Success"}
    mock_tool_executor.servers = [mock_server]
    
    # Mock LLM responses
    mock_llm_client.get_response.side_effect = [
        # Regular tool call
        "[TOOL] test_tool\n{\"param1\": \"value1\"}",
        
        # Handoff message
        "[TOOL] handoff\n{\"message\": \"Got results, now finishing up\"}",
        
        # Final answer (no tools)
        "Here are the results of my analysis.",
        
        # End response
        "[TOOL] end_response\n{}"
    ]
    
    # Call the method
    await handlers._process_multi_turn_response(
        conversation_id, messages, channel, thread_ts, say
    )
    
    # Verify tool was executed
    mock_server.execute_tool.assert_called_once_with("test_tool", {"param1": "value1"})
    
    # Verify tool usage message was sent
    say.assert_any_call(
        text="_Using tool: test_tool_",
        channel=channel,
        thread_ts=thread_ts
    )
    
    # Verify handoff message was sent
    say.assert_any_call(
        text="_Got results, now finishing up_",
        channel=channel,
        thread_ts=thread_ts
    )
    
    # Verify final answer was sent
    say.assert_any_call(
        text="Here are the results of my analysis.",
        channel=channel,
        thread_ts=thread_ts
    )


@pytest.mark.asyncio
async def test_single_tool_per_response(handlers, mock_llm_client):
    """Test handling single tool per response."""
    # Mock say function
    say = AsyncMock()
    
    # Set up conversation details
    conversation_id = "C12345-1234567890.123456"
    channel = "C12345"
    thread_ts = "1234567890.123456"
    
    # Mock conversation messages
    messages = [{"role": "system", "content": "System prompt"}]
    
    # Mock LLM response with multiple tools in one response
    mock_llm_client.get_response.side_effect = [
        # Multiple tools in one response (should only use first)
        """[TOOL] handoff
{"message": "First message"}

[TOOL] handoff
{"message": "Second message"}""",
        
        # End response
        "[TOOL] end_response\n{}"
    ]
    
    # Call the method
    await handlers._process_multi_turn_response(
        conversation_id, messages, channel, thread_ts, say
    )
    
    # Verify only first handoff was processed
    say.assert_any_call(
        text="_First message_",
        channel=channel,
        thread_ts=thread_ts
    )
    
    # Verify reminder was added to context
    assert any(
        "REMINDER: You should only include ONE tool call per response" in msg["content"]
        for msg in mock_llm_client.get_response.call_args_list[1][0][0]
        if isinstance(msg, dict) and msg.get("role") == "system"
    )


@pytest.mark.asyncio
async def test_final_answer_then_end_response(handlers, mock_llm_client):
    """Test final answer followed by end_response pattern."""
    # Mock say function
    say = AsyncMock()
    
    # Set up conversation details
    conversation_id = "C12345-1234567890.123456"
    channel = "C12345"
    thread_ts = "1234567890.123456"
    
    # Mock conversation messages
    messages = [{"role": "system", "content": "System prompt"}]
    
    # Mock LLM responses
    mock_llm_client.get_response.side_effect = [
        # Final answer (no tools)
        "Here are the results of my analysis.",
        
        # End response
        "[TOOL] end_response\n{}"
    ]
    
    # Call the method
    await handlers._process_multi_turn_response(
        conversation_id, messages, channel, thread_ts, say
    )
    
    # Verify final answer was sent
    say.assert_any_call(
        text="Here are the results of my analysis.",
        channel=channel,
        thread_ts=thread_ts
    )
    
    # Verify a prompt for end_response was added
    assert any(
        "Now proceed to STEP 5: End the conversation with the end_response tool" in msg["content"]
        for msg in mock_llm_client.get_response.call_args_list[1][0][0]
        if isinstance(msg, dict) and msg.get("role") == "system"
    )