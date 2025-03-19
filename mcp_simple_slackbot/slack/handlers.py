"""Event handlers for Slack events."""

import logging
from typing import Any, Callable, Dict, List, Optional
import json

from slack_sdk.web.async_client import AsyncWebClient

from mcp_simple_slackbot.conversation.manager import ConversationManager
from mcp_simple_slackbot.llm.client import LLMClient
from mcp_simple_slackbot.mcp.tool import Tool
from mcp_simple_slackbot.slack.ui import SlackUI
from mcp_simple_slackbot.tools.executor import ToolExecutor
from mcp_simple_slackbot.tools.parser import ToolParser


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
        self.tools = tools.copy()  # Copy to avoid modifying the original list
        self.bot_id = bot_id

        # Add system tool for ending the response
        self.end_response_tool = Tool(
            name="end_response",
            description="Use this tool to finish the conversation after providing your final answer. This will terminate the response.",
            input_schema={"type": "object", "properties": {}, "required": []},
            is_system=True,
        )

        # Add system tool to the tools list
        self.tools.append(self.end_response_tool)

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

    async def handle_home_opened(
        self, event: Dict[str, Any], client: AsyncWebClient
    ) -> None:
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
            # Create message metadata with Slack context
            message_metadata = {
                "channel_id": channel,
                "thread_timestamp": thread_ts,
                "user_id": user_id,
                "event": event,
            }
            system_message = {
                "role": "system",
                "content": (
                    f"""You are a helpful Slack bot with access to powerful tools. Follow this conversation flow:

STEP 1: Initial Greeting
- Acknowledge the user's request
- Briefly explain your approach and what information you'll gather

STEP 2: Tool Usage (REPEAT AS NEEDED)
- Use tools to gather all the information needed to answer the user's question
- Make ONE tool call per response with the EXACT format:
  [TOOL] tool_name
  {{"param1": "value1", "param2": "value2"}}
- Continue making tool calls until you have all the information needed

STEP 3: Final Answer
- Once you have all necessary information, provide a complete answer
- Make this a plain text response without any tool calls
- Format your response appropriately for the question (bullet points, paragraphs, etc.)

STEP 4: End Conversation
- After providing your final answer, end the conversation with the special end_response tool. It isn't listed with the other tools because it is a system tool that ends the conversation.
  [TOOL] end_response
  {{}}

Available tools:

{tools_text}

IMPORTANT RULES:
1. Make only ONE tool call per response - you can make multiple tool calls across multiple responses
2. You MUST use tools to gather information before answering
3. Always end with the end_response tool as your final response after providing your answer
4. If there doesn't seem to be enough information. See if you can find the corresponding context in the thread with tools.
5. If you really can't find the information you should say so and immediately end the conversation. BUT THIS IS A LAST RESORT.

Message metadata:
{message_metadata}
"""
                ),
            }

            # Add user message to history with metadata
            # self.conversation_manager.add_message(conversation_id, "user", text)
            user_message = {"role": "user", "content": text}

            # Set up messages for LLM
            messages = [system_message, user_message]

            # Add conversation history
            # messages.extend(self.conversation_manager.get_messages(conversation_id))

            # Send initial response to acknowledge the request
            initial_response = await self.llm_client.get_response(messages)
            await say(text=initial_response, channel=channel, thread_ts=thread_ts)

            # Add assistant response to conversation history
            # self.conversation_manager.add_message(
            #     conversation_id, "assistant", initial_response
            # )
            # Add assistant response to LLM context
            messages.append({"role": "assistant", "content": initial_response})

            # Start the multi-turn tool execution process
            await self._process_multi_turn_response(
                conversation_id, messages, channel, thread_ts, say
            )

        except Exception as e:
            error_message = f"I'm sorry, I encountered an error: {str(e)}"
            logging.error(f"Error processing message: {e}", exc_info=True)
            await say(text=error_message, channel=channel, thread_ts=thread_ts)

    async def _process_multi_turn_response(
        self,
        conversation_id: str,
        messages: List[Dict],
        channel: str,
        thread_ts: str,
        say: Callable,
    ) -> None:
        """Process multi-turn responses with tool calls.

        Args:
            conversation_id: Unique identifier for the conversation
            messages: List of message objects for the LLM
            channel: Slack channel ID
            thread_ts: Thread timestamp
            say: Function to send messages
        """
        response_complete = False
        max_iterations = 15  # Reasonable limit to prevent infinite loops
        iterations = 0

        # Initial state after greeting is to expect a tool call
        expect_tool_after_greeting = True

        while not response_complete and iterations < max_iterations:
            iterations += 1

            # Get LLM response for next action
            response = await self.llm_client.get_response(messages)
            await say(text=response, channel=channel, thread_ts=thread_ts)
            logging.info(f"LLM response: {response}")

            # Add assistant response to messages list to maintain context
            messages.append({"role": "assistant", "content": response})

            # Check if we just sent the greeting and enforce a tool call if needed
            if expect_tool_after_greeting and "[TOOL]" not in response:
                messages.append(
                    {
                        "role": "user",
                        "content": "You need to gather information using tools before you can answer the question. Please make a tool call now.",
                    }
                )
                # We don't remove the response here - we want to keep the reasoning but prompt for a tool call
                expect_tool_after_greeting = False  # Only enforce this once
                continue

            # Parse tool calls
            non_tool_content, tool_calls = ToolParser.split_response(response)
            logging.info(f"Parsed tool calls: {tool_calls}")

            # Handle tool parsing failures
            if len(tool_calls) == 0 and "[TOOL]" in response:
                logging.warning("Tool tag found but no valid tools parsed")
                messages.append(
                    {
                        "role": "user",
                        "content": 'Your tool call could not be parsed. Please use the exact format: [TOOL] tool_name\n{"param1": "value1"}',
                    }
                )
                # Remove the invalid response from the context
                messages.pop(-2)
                continue

            # Handle multiple tool calls in a single response
            if len(tool_calls) > 1:
                logging.warning(
                    f"Multiple tool calls found in a single response: {len(tool_calls)}. Only processing the first one."
                )
                messages.append(
                    {
                        "role": "user",
                        "content": "Please make only ONE tool call per response. I'll process your first tool call now.",
                    }
                )
                tool_call = tool_calls[0]
            elif len(tool_calls) == 1:
                tool_call = tool_calls[0]
            else:
                continue

            # Process the tool call
            tool_name = tool_call["tool_name"]
            arguments = tool_call["arguments"]

            # Handle end_response tool
            if tool_name == "end_response":
                # End the response loop
                await say(
                    text="_Conversation complete_", channel=channel, thread_ts=thread_ts
                )
                response_complete = True
                break

            # For regular tools, execute them and show progress
            tool_found = False

            for server in self.tool_executor.servers:
                try:
                    server_tools = [tool.name for tool in await server.list_tools()]
                    if tool_name in server_tools:
                        tool_found = True
                        # Notify user which tool is being used
                        tool_msg = f"_Using tool: {tool_name}_"
                        logging.info(
                            f"Executing tool: {tool_name} with arguments: {arguments}"
                        )
                        await say(text=tool_msg, channel=channel, thread_ts=thread_ts)

                        # Execute the tool
                        try:
                            result = await server.execute_tool(tool_name, arguments)
                            # Format result for LLM
                            if isinstance(result, dict):
                                result_str = json.dumps(result, indent=2)
                            else:
                                result_str = str(result)

                            logging.info(f"Tool {tool_name} result: {result_str}")

                            # Add tool result to messages for LLM context
                            messages.append(
                                {
                                    "role": "user",
                                    "content": f"Tool {tool_name} executed successfully. Result:\n{result_str}",
                                }
                            )

                            # Reset the greeting flag as we've successfully used a tool
                            expect_tool_after_greeting = False

                        except Exception as e:
                            error_msg = f"_Error executing tool {tool_name}: {str(e)}_"
                            logging.error(f"Error executing tool {tool_name}: {e}")
                            await say(
                                text=error_msg, channel=channel, thread_ts=thread_ts
                            )
                            messages.append(
                                {
                                    "role": "user",
                                    "content": f"Tool {tool_name} failed with error: {str(e)}. Try another approach or tool.",
                                }
                            )
                        break
                except Exception as e:
                    logging.error(f"Error checking tools on server: {e}")
                    continue

            if not tool_found and tool_name != "end_response":
                error_msg = f"_Tool not found: {tool_name}_"
                logging.warning(f"Tool not found: {tool_name}")
                await say(text=error_msg, channel=channel, thread_ts=thread_ts)
                messages.append(
                    {
                        "role": "user",
                        "content": f"Tool {tool_name} not found. Please try a different available tool.",
                    }
                )

            # If we've reached maximum iterations, force a conclusion
            if iterations >= max_iterations:
                # Force end the conversation
                await say(
                    text="_Conversation ended due to reaching maximum number of steps_",
                    channel=channel,
                    thread_ts=thread_ts,
                )
                response_complete = True
