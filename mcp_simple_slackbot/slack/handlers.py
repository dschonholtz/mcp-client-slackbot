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
        
        # Add system tools
        self.handoff_tool = Tool(
            name="handoff",
            description="Use this tool to hand off your response to continue working on a complex task, showing your work in progress.",
            input_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The intermediate message to show the user, which will be displayed in italics"
                    }
                },
                "required": ["message"]
            },
            is_system=True
        )
        
        self.end_response_tool = Tool(
            name="end_response",
            description="Use this tool to finish the conversation after providing your final answer. This will terminate the response.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            is_system=True
        )
        
        # Add system tools to the tools list
        self.tools.append(self.handoff_tool)
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
                    f"""You are a helpful Slack bot with access to powerful tools. You MUST follow this EXACT conversation flow for EVERY request:

STEP 1: Initial Greeting - DO NOT USE ANY TOOL YET
- Acknowledge the user's request
- Tell them what tools you'll use to help them

STEP 2: Tool Usage - EACH RESPONSE MUST CONTAIN EXACTLY ONE TOOL CALL
- For each tool you need, make ONE separate response with ONLY that tool call
- Format each tool call EXACTLY like this:
  [TOOL] tool_name
  {{"param1": "value1", "param2": "value2"}}

STEP 3: Progress Updates - USE HANDOFF TOOL BETWEEN REGULAR TOOLS
- After each regular tool call, send a handoff message to explain what you found and what you'll do next
- Format the handoff EXACTLY like this:
  [TOOL] handoff
  {{"message": "I found X using the first tool. Now I'll use Y tool to..."}}

STEP 4: Final Answer - REGULAR TEXT RESPONSE WITH YOUR FINDINGS
- Provide a complete answer based on all tool results
- Summarize what you found
- DO NOT use any tool calls in this response

STEP 5: End Conversation - MUST BE YOUR LAST RESPONSE
- Use ONLY the end_response tool to finish
- Format EXACTLY like this:
  [TOOL] end_response
  {{}}

Available tools:

{tools_text}

IMPORTANT RULES:
1. NEVER combine multiple tool calls in a single response
2. NEVER skip the final end_response tool call
3. NEVER add extra text around tool calls - ONLY the [TOOL] format
4. ALWAYS use handoff between tools to show progress
5. ALWAYS make your final answer a plain text response WITHOUT tool calls
6. ALWAYS end with the end_response tool in a separate response

Example conversation flow:
1. User: "Tell me about active Slack channels"
2. You: "I'll help you get information about the active Slack channels. I'll use the list_channels tool to find all channels, then check each one's activity."
3. You: "[TOOL] list_channels\\n{{}}"
4. You: "[TOOL] handoff\\n{{\\"message\\": \\"I found 5 channels. I'll now check the activity in each one.\\"}}"
5. You: "[TOOL] channel_history\\n{{\\"channel_id\\": \\"C12345\\"}}"
6. You: "Based on my analysis, there are 5 active channels. The most active is #general with 120 messages today, followed by #random with 45 messages..."
7. You: "[TOOL] end_response\\n{{}}"

This specific flow with separate responses for each step is MANDATORY.
"""
                ),
            }

            # Add user message to history
            self.conversation_manager.add_message(conversation_id, "user", text)

            # Set up messages for LLM
            messages = [system_message]

            # Add conversation history
            messages.extend(self.conversation_manager.get_messages(conversation_id))

            # Send initial response to acknowledge the request
            initial_response = await self.llm_client.get_response(
                messages + [{"role": "system", "content": "EXECUTE STEP 1 ONLY: Generate a brief initial greeting that acknowledges the user's request and explains what tools you plan to use. This should be plain text without any [TOOL] tags. Remember, this is just the first step of the conversation flow described in your instructions."}]
            )
            await say(text=initial_response, channel=channel, thread_ts=thread_ts)
            self.conversation_manager.add_message(conversation_id, "assistant", initial_response)

            # Start the multi-turn tool execution process
            await self._process_multi_turn_response(conversation_id, messages, channel, thread_ts, say)

        except Exception as e:
            error_message = f"I'm sorry, I encountered an error: {str(e)}"
            logging.error(f"Error processing message: {e}", exc_info=True)
            await say(text=error_message, channel=channel, thread_ts=thread_ts)
            
    async def _process_multi_turn_response(
        self, conversation_id: str, messages: List[Dict], channel: str, thread_ts: str, say: Callable
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
        max_iterations = 10  # Limit the number of iterations to prevent infinite loops
        iterations = 0
        
        while not response_complete and iterations < max_iterations:
            iterations += 1
            
            # Get LLM response for next action
            response = await self.llm_client.get_response(messages)
            logging.info(f"LLM response: {response}")
            
            # Process any tool calls in the response
            if "[TOOL]" not in response:
                logging.info("No tool calls found in response - treating as final answer")
                # If no tools called, this should be the final summary response
                await say(text=response, channel=channel, thread_ts=thread_ts)
                self.conversation_manager.add_message(conversation_id, "assistant", response)
                
                # Prompt for the end_response tool
                messages.append({"role": "system", "content": "Now proceed to STEP 5: End the conversation with the end_response tool. Send ONLY the end_response tool call."})
                continue
                
            # Parse tool calls - should be only one per response
            non_tool_content, tool_calls = ToolParser.split_response(response)
            logging.info(f"Parsed tool calls: {tool_calls}")
            
            if len(tool_calls) > 1:
                logging.warning(f"Multiple tool calls found in a single response: {len(tool_calls)}. Only processing the first one.")
                tool_call = tool_calls[0]
                messages.append({"role": "system", "content": "REMINDER: You should only include ONE tool call per response. Continue with the next tool or step."})
            elif len(tool_calls) == 0:
                logging.warning("Tool tag found but no valid tools parsed")
                messages.append({"role": "system", "content": "Your tool call could not be parsed. Please use the exact format specified in the instructions."})
                continue
            else:
                tool_call = tool_calls[0]
                
            # Process the single tool call
            tool_name = tool_call["tool_name"]
            arguments = tool_call["arguments"]
            
            # Handle system tools
            if tool_name == "handoff":
                    # Send intermediate message in italics
                    handoff_message = f"_{arguments.get('message', 'Working on your request...')}_"
                    await say(text=handoff_message, channel=channel, thread_ts=thread_ts)
                    self.conversation_manager.add_message(conversation_id, "assistant", handoff_message)
                    # Add to LLM context
                    messages.append({"role": "assistant", "content": f"I sent an intermediate message: {arguments.get('message')}"})
                    continue
                    
                elif tool_name == "end_response":
                    # End the response loop
                    response_complete = True
                    break
                    
                # For regular tools, execute them and show progress
                tool_found = False
                
                # List all available tools for debugging
                all_available_tools = []
                for server in self.tool_executor.servers:
                    try:
                        server_tool_list = await server.list_tools()
                        server_tools = [tool.name for tool in server_tool_list]
                        all_available_tools.extend(server_tools)
                    except Exception as e:
                        logging.error(f"Error listing tools on server: {e}")
                
                logging.info(f"All available tools: {all_available_tools}")
                logging.info(f"Looking for tool: {tool_name}")
                
                for server in self.tool_executor.servers:
                    try:
                        server_tools = [tool.name for tool in await server.list_tools()]
                        if tool_name in server_tools:
                            tool_found = True
                            # Notify user which tool is being used
                            tool_msg = f"_Using tool: {tool_name}_"
                            logging.info(f"Executing tool: {tool_name} with arguments: {arguments}")
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
                                messages.append({
                                    "role": "system", 
                                    "content": f"Tool {tool_name} executed successfully. Result:\n{result_str}"
                                })
                            except Exception as e:
                                error_msg = f"_Error executing tool {tool_name}: {str(e)}_"
                                logging.error(f"Error executing tool {tool_name}: {e}")
                                await say(text=error_msg, channel=channel, thread_ts=thread_ts)
                                messages.append({
                                    "role": "system", 
                                    "content": f"Tool {tool_name} failed with error: {str(e)}"
                                })
                            break
                    except Exception as e:
                        logging.error(f"Error checking tools on server: {e}")
                        continue
                
                if not tool_found and tool_name not in ["handoff", "end_response"]:
                    error_msg = f"_Tool not found: {tool_name}_"
                    logging.warning(f"Tool not found: {tool_name}")
                    await say(text=error_msg, channel=channel, thread_ts=thread_ts)
                    messages.append({
                        "role": "system", 
                        "content": f"Tool {tool_name} not found. Available tools: {', '.join(all_available_tools)}"
                    })
            
            # If no end_response tool was called, continue the loop
            if not response_complete and iterations < max_iterations:
                # Add a prompt for the LLM to continue with the next step in the flow
                if tool_name == "handoff":
                    messages.append({
                        "role": "system",
                        "content": (
                            "Continue with STEP 2: Make your next tool call following the conversation flow. "
                            "Remember to send only ONE tool call in your next response, exactly in the format specified."
                        )
                    })
                elif tool_name == "end_response":
                    # Should be handled by the response_complete flag, but just in case
                    response_complete = True
                else:
                    # After a regular tool call, prompt for a handoff message
                    messages.append({
                        "role": "system",
                        "content": (
                            "Continue with STEP 3: Send a handoff message explaining what you found and what you'll do next. "
                            "If you have all the information needed, proceed to STEP 4 instead and provide your final answer without any tool calls."
                        )
                    })
                })
            elif iterations >= max_iterations:
                # Safety measure: end if we've hit the max iterations
                await say(
                    text="I've reached the maximum number of steps for this request. Here's what I've found so far.",
                    channel=channel, 
                    thread_ts=thread_ts
                )
                response_complete = True