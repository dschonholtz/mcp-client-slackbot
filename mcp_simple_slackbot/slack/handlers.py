"""Event handlers for Slack events."""

import logging
from typing import Any, Callable, Dict, List, Optional

from slack_sdk.web.async_client import AsyncWebClient

from mcp_simple_slackbot.conversation.manager import ConversationManager
from mcp_simple_slackbot.llm.client import LLMClient
from mcp_simple_slackbot.mcp.tool import Tool
from mcp_simple_slackbot.slack.ui import SlackUI
from mcp_simple_slackbot.tools.executor import ToolExecutor


class SlackEventHandlers:
    """Handlers for Slack events."""
    
    def __init__(
        self,
        client: AsyncWebClient,
        conversation_manager: ConversationManager,
        llm_client: LLMClient,
        tool_executor: ToolExecutor,
        tools: list[Tool],
        bot_id: Optional[str] = None,
    ):
        """Initialize Slack event handlers.
        
        Args:
            client: Slack API client
            conversation_manager: Conversation context manager
            llm_client: LLM client
            tool_executor: Tool execution handler
            tools: List of available tools
            bot_id: Bot user ID
        """
        self.client = client
        self.conversation_manager = conversation_manager
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.tools = tools
        self.bot_id = bot_id
    
    def set_bot_id(self, bot_id: Optional[str]) -> None:
        """Set the bot ID.
        
        Args:
            bot_id: Bot user ID
        """
        self.bot_id = bot_id
    
    async def handle_mention(self, event: Dict[str, Any], say: Callable) -> None:
        """Handle mentions of the bot in channels.
        
        Args:
            event: Slack event data
            say: Function to send a message
        """
        await self._process_message(event, say)
    
    async def handle_message(self, message: Dict[str, Any], say: Callable) -> None:
        """Handle direct messages to the bot.
        
        Args:
            message: Slack message data
            say: Function to send a message
        """
        # Only process direct messages
        if message.get("channel_type") == "im" and not message.get("subtype"):
            await self._process_message(message, say)
    
    async def handle_home_opened(self, event: Dict[str, Any], client: AsyncWebClient) -> None:
        """Handle when a user opens the App Home tab.
        
        Args:
            event: Slack event data
            client: Slack API client
        """
        user_id = event["user"]
        view = SlackUI.build_home_view(self.tools)
        
        try:
            await client.views_publish(user_id=user_id, view=view)
        except Exception as e:
            logging.error(f"Error publishing home view: {e}")
    
    async def _process_message(self, event: Dict[str, Any], say: Callable) -> None:
        """Process incoming messages and generate responses.
        
        Args:
            event: Slack event data
            say: Function to send a message
        """
        channel = event["channel"]
        user_id = event.get("user")

        # Skip messages from the bot itself
        if user_id == self.bot_id:
            return

        # Get text and remove bot mention if present
        text = event.get("text", "")
        if self.bot_id:
            text = text.replace(f"<@{self.bot_id}>", "").strip()

        thread_ts = event.get("thread_ts", event.get("ts"))
        
        # Use channel+thread as conversation ID
        conversation_id = f"{channel}-{thread_ts}"

        try:
            # Create system message with tool descriptions
            tools_text = "\n".join([tool.format_for_llm() for tool in self.tools])
            system_message = {
                "role": "system",
                "content": (
                    f"""You are a helpful slack bot with the following tools:

{tools_text}

You can use multiple tools (up to 10) to fulfill a user's request before providing a final response.
Make all of your tool calls BEFORE responding to the user otherwise, they will not be able to see the results.

Your goal should always be to provide useful information answering the user's question, or their implied question. Many of these tools respond with metadata that is uninteresting. Make sure to summarize effectively and to focus on what the member actually wants.

When you need to use tools, you MUST format your response exactly like this for each tool:
[TOOL] tool_name
{{"param1": "value1", "param2": "value2"}}

You can call multiple tools by including multiple [TOOL] blocks in your response.
Make sure to include both the tool name AND the JSON arguments for each tool.
Never leave out the JSON arguments.

After receiving all tool results, provide a helpful interpretation that addresses the user's original request.
"""
                ),
            }

            # Add user message to history
            self.conversation_manager.add_message(conversation_id, "user", text)

            # Set up messages for LLM
            messages = [system_message]

            # Add conversation history
            messages.extend(self.conversation_manager.get_messages(conversation_id))

            # Get LLM response
            response = await self.llm_client.get_response(messages)

            # Process tool calls in the response
            if "[TOOL]" in response:
                response = await self.tool_executor.process_tool_calls(response, conversation_id)
                
                # Add system message with tool results
                self.conversation_manager.add_message(
                    conversation_id, "system", "Tool results processed"
                )

            # Add assistant response to conversation history
            self.conversation_manager.add_message(conversation_id, "assistant", response)

            # Send the response to the user
            await say(text=response, channel=channel, thread_ts=thread_ts)

        except Exception as e:
            error_message = f"I'm sorry, I encountered an error: {str(e)}"
            logging.error(f"Error processing message: {e}", exc_info=True)
            await say(text=error_message, channel=channel, thread_ts=thread_ts)