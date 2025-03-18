import asyncio
import json
import logging
import os
import shutil
from contextlib import AsyncExitStack
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Configuration:
    """Manages configuration and environment variables for the MCP Slackbot."""

    def __init__(self) -> None:
        """Initialize configuration with environment variables."""
        self.load_env()
        self.slack_bot_token = os.getenv("SLACK_BOT_TOKEN")
        self.slack_app_token = os.getenv("SLACK_APP_TOKEN")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.llm_model = os.getenv("LLM_MODEL", "gpt-4-turbo")

        # MCP Slack server configuration
        self.mcp_server_oauth = os.getenv("MCP_SERVER_OAUTH")
        self.mcp_team_id = os.getenv("TEAM_ID")

    @staticmethod
    def load_env() -> None:
        """Load environment variables from .env file."""
        load_dotenv()

    @staticmethod
    def load_config(file_path: str) -> Dict[str, Any]:
        """Load server configuration from JSON file.

        Args:
            file_path: Path to the JSON configuration file.

        Returns:
            Dict containing server configuration.

        Raises:
            FileNotFoundError: If configuration file doesn't exist.
            JSONDecodeError: If configuration file is invalid JSON.
        """
        with open(file_path, "r") as f:
            return json.load(f)

    @property
    def llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on the model.

        Returns:
            The API key as a string.

        Raises:
            ValueError: If no API key is found for the selected model.
        """
        if "gpt" in self.llm_model.lower() and self.openai_api_key:
            return self.openai_api_key
        elif "llama" in self.llm_model.lower() and self.groq_api_key:
            return self.groq_api_key
        elif "claude" in self.llm_model.lower() and self.anthropic_api_key:
            return self.anthropic_api_key

        # Fallback to any available key
        if self.openai_api_key:
            return self.openai_api_key
        elif self.groq_api_key:
            return self.groq_api_key
        elif self.anthropic_api_key:
            return self.anthropic_api_key

        raise ValueError("No API key found for any LLM provider")


class Server:
    """Manages MCP server connections and tool execution."""

    def __init__(self, name: str, config: Dict[str, Any]) -> None:
        self.name: str = name
        self.config: Dict[str, Any] = config
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        """Initialize the server connection."""
        command = (
            shutil.which("npx")
            if self.config["command"] == "npx"
            else self.config["command"]
        )
        if command is None:
            raise ValueError("The command must be a valid string and cannot be None.")

        server_params = StdioServerParameters(
            command=command,
            args=self.config["args"],
            env=(
                {**os.environ, **self.config["env"]} if self.config.get("env") else None
            ),
        )
        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> List[Any]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools_response = await self.session.list_tools()
        tools = []

        for item in tools_response:
            if isinstance(item, tuple) and item[0] == "tools":
                for tool in item[1]:
                    tools.append(Tool(tool.name, tool.description, tool.inputSchema))

        return tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool with retry mechanism.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If server is not initialized.
            Exception: If tool execution fails after all retries.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name}...")
                result = await self.session.call_tool(tool_name, arguments)
                return result
            except Exception as e:
                attempt += 1
                logging.warning(
                    f"Error executing tool: {e}. Attempt {attempt} of {retries}."
                )
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")


class Tool:
    """Represents a tool with its properties and formatting."""

    def __init__(
        self, name: str, description: str, input_schema: Dict[str, Any]
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: Dict[str, Any] = input_schema

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


class LLMClient:
    """Client for communicating with LLM APIs."""

    def __init__(self, api_key: str, model: str) -> None:
        """Initialize the LLM client.

        Args:
            api_key: API key for the LLM provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
        self.timeout = 30.0  # 30 second timeout
        self.max_retries = 2

    async def get_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the LLM.

        Args:
            messages: List of conversation messages

        Returns:
            Text response from the LLM
        """
        if self.model.startswith("gpt-") or self.model.startswith("ft:gpt-"):
            return await self._get_openai_response(messages)
        elif self.model.startswith("llama-"):
            return await self._get_groq_response(messages)
        elif self.model.startswith("claude-"):
            return await self._get_anthropic_response(messages)
        else:
            raise ValueError(f"Unsupported model: {self.model}")

    async def _get_openai_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the OpenAI API."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1500,
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code == 200:
                        response_data = response.json()
                        return response_data["choices"][0]["message"]["content"]
                    else:
                        if attempt == self.max_retries:
                            return (
                                f"Error from API: {response.status_code} - "
                                f"{response.text}"
                            )
                        await asyncio.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                if attempt == self.max_retries:
                    return f"Failed to get response: {str(e)}"
                await asyncio.sleep(2**attempt)  # Exponential backoff

    async def _get_groq_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the Groq API."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1500,
        }

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code == 200:
                        response_data = response.json()
                        return response_data["choices"][0]["message"]["content"]
                    else:
                        if attempt == self.max_retries:
                            return (
                                f"Error from API: {response.status_code} - "
                                f"{response.text}"
                            )
                        await asyncio.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                if attempt == self.max_retries:
                    return f"Failed to get response: {str(e)}"
                await asyncio.sleep(2**attempt)  # Exponential backoff

    async def _get_anthropic_response(self, messages: List[Dict[str, str]]) -> str:
        """Get a response from the Anthropic API."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        # Convert messages to Anthropic format
        system_message = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            elif msg["role"] == "user":
                anthropic_messages.append({"role": "user", "content": msg["content"]})
            elif msg["role"] == "assistant":
                anthropic_messages.append(
                    {"role": "assistant", "content": msg["content"]}
                )

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": 0.7,
            "max_tokens": 1500,
        }

        if system_message:
            payload["system"] = system_message

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload, headers=headers)

                    if response.status_code == 200:
                        response_data = response.json()
                        return response_data["content"][0]["text"]
                    else:
                        if attempt == self.max_retries:
                            return (
                                f"Error from API: {response.status_code} - "
                                f"{response.text}"
                            )
                        await asyncio.sleep(2**attempt)  # Exponential backoff
            except Exception as e:
                if attempt == self.max_retries:
                    return f"Failed to get response: {str(e)}"
                await asyncio.sleep(2**attempt)  # Exponential backoff


class SlackMCPBot:
    """Manages the Slack bot integration with MCP servers."""

    def __init__(
        self,
        slack_bot_token: str,
        slack_app_token: str,
        servers: List[Server],
        llm_client: LLMClient,
    ) -> None:
        self.app = AsyncApp(token=slack_bot_token)
        # Create a socket mode handler with the app token
        self.socket_mode_handler = AsyncSocketModeHandler(self.app, slack_app_token)

        self.client = AsyncWebClient(token=slack_bot_token)
        self.servers = servers
        self.llm_client = llm_client
        self.conversations = {}  # Store conversation context per channel
        self.tools = []

        # Set up event handlers
        self.app.event("app_mention")(self.handle_mention)
        self.app.message()(self.handle_message)
        self.app.event("app_home_opened")(self.handle_home_opened)

    async def initialize_servers(self) -> None:
        """Initialize all MCP servers and discover tools."""
        for server in self.servers:
            try:
                await server.initialize()
                server_tools = await server.list_tools()
                self.tools.extend(server_tools)
                logging.info(
                    f"Initialized server {server.name} with {len(server_tools)} tools"
                )
            except Exception as e:
                logging.error(f"Failed to initialize server {server.name}: {e}")

    async def initialize_bot_info(self) -> None:
        """Get the bot's ID and other info."""
        try:
            auth_info = await self.client.auth_test()
            self.bot_id = auth_info["user_id"]
            logging.info(f"Bot initialized with ID: {self.bot_id}")
        except Exception as e:
            logging.error(f"Failed to get bot info: {e}")
            self.bot_id = None

    async def handle_mention(self, event, say):
        """Handle mentions of the bot in channels."""
        await self._process_message(event, say)

    async def handle_message(self, message, say):
        """Handle direct messages to the bot."""
        # Only process direct messages
        if message.get("channel_type") == "im" and not message.get("subtype"):
            await self._process_message(message, say)

    async def handle_home_opened(self, event, client):
        """Handle when a user opens the App Home tab."""
        user_id = event["user"]

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Welcome to MCP Assistant!"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "I'm an AI assistant with access to tools and resources "
                        "through the Model Context Protocol."
                    ),
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Available Tools:*"},
            },
        ]

        # Add tools
        for tool in self.tools:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"• *{tool.name}*: {tool.description}",
                    },
                }
            )

        # Add usage section
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*How to Use:*\n• Send me a direct message\n"
                        "• Mention me in a channel with @MCP Assistant"
                    ),
                },
            }
        )

        try:
            await client.views_publish(
                user_id=user_id, view={"type": "home", "blocks": blocks}
            )
        except Exception as e:
            logging.error(f"Error publishing home view: {e}")

    async def _process_message(self, event, say):
        """Process incoming messages and generate responses."""
        channel = event["channel"]
        user_id = event.get("user")

        # Skip messages from the bot itself
        if user_id == getattr(self, "bot_id", None):
            return

        # Get text and remove bot mention if present
        text = event.get("text", "")
        if hasattr(self, "bot_id") and self.bot_id:
            text = text.replace(f"<@{self.bot_id}>", "").strip()

        thread_ts = event.get("thread_ts", event.get("ts"))

        # Get or create conversation context
        if channel not in self.conversations:
            self.conversations[channel] = {"messages": []}

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
            self.conversations[channel]["messages"].append(
                {"role": "user", "content": text}
            )

            # Set up messages for LLM
            messages = [system_message]

            # Add conversation history (last 5 messages)
            if "messages" in self.conversations[channel]:
                messages.extend(self.conversations[channel]["messages"][-5:])

            # Get LLM response
            response = await self.llm_client.get_response(messages)

            # Process tool calls in the response
            if "[TOOL]" in response:
                response = await self._process_tool_calls(response, channel)

            # Add assistant response to conversation history
            self.conversations[channel]["messages"].append(
                {"role": "assistant", "content": response}
            )

            # Send the response to the user
            await say(text=response, channel=channel, thread_ts=thread_ts)

        except Exception as e:
            error_message = f"I'm sorry, I encountered an error: {str(e)}"
            logging.error(f"Error processing message: {e}", exc_info=True)
            await say(text=error_message, channel=channel, thread_ts=thread_ts)

    async def _process_tool_calls(self, response: str, channel: str) -> str:
        """Process multiple tool calls from the LLM response."""
        try:
            # Check if there are any tool calls
            if "[TOOL]" not in response:
                return response

            # Split the response into parts based on [TOOL] tag
            parts = response.split("[TOOL]")
            non_tool_content = parts[0]  # Content before the first tool call
            tool_parts = parts[1:]  # All tool call parts

            # Limit to max 10 tool calls
            if len(tool_parts) > 10:
                tool_parts = tool_parts[:10]
                logging.warning(f"Limiting to 10 tool calls out of {len(parts) - 1}")

            tool_results = []

            # Process each tool call
            for i, tool_part in enumerate(tool_parts):
                try:
                    # Extract tool name and arguments
                    tool_lines = tool_part.strip().split("\n", 1)
                    tool_name = tool_lines[0].strip()

                    # Handle incomplete tool calls
                    if len(tool_lines) < 2:
                        tool_results.append(
                            {
                                "tool": tool_name,
                                "success": False,
                                "error": "Incomplete tool call - no arguments provided",
                                "result": None,
                            }
                        )
                        continue

                    # Parse JSON arguments
                    try:
                        args_text = tool_lines[1].strip()
                        arguments = json.loads(args_text)
                    except json.JSONDecodeError:
                        tool_results.append(
                            {
                                "tool": tool_name,
                                "success": False,
                                "error": "Invalid JSON arguments",
                                "result": None,
                            }
                        )
                        continue

                    # Find the appropriate server for this tool
                    tool_executed = False
                    for server in self.servers:
                        server_tools = [tool.name for tool in await server.list_tools()]
                        if tool_name in server_tools:
                            # Execute the tool
                            tool_executed = True
                            try:
                                result = await server.execute_tool(tool_name, arguments)
                                tool_results.append(
                                    {
                                        "tool": tool_name,
                                        "success": True,
                                        "arguments": arguments,
                                        "result": result,
                                    }
                                )
                            except Exception as e:
                                tool_results.append(
                                    {
                                        "tool": tool_name,
                                        "success": False,
                                        "arguments": arguments,
                                        "error": str(e),
                                        "result": None,
                                    }
                                )
                            break

                    if not tool_executed:
                        tool_results.append(
                            {
                                "tool": tool_name,
                                "success": False,
                                "error": f"Tool '{tool_name}' not available",
                                "result": None,
                            }
                        )

                except Exception as e:
                    logging.error(f"Error processing tool call: {e}", exc_info=True)
                    tool_results.append(
                        {
                            "tool": f"Unknown (parsing error in tool call {i+1})",
                            "success": False,
                            "error": str(e),
                            "result": None,
                        }
                    )

            # Build a message with all tool results for the LLM
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
                    tool_results_text += (
                        f"\n\nTool {i+1}: {tool_name}\nSuccess: False\nError: {error}"
                    )

            # Record all tool results in conversation history
            tool_result_msg = f"Tool results:\n{tool_results_text}"
            self.conversations[channel]["messages"].append(
                {"role": "system", "content": tool_result_msg}
            )

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

        except Exception as e:
            logging.error(f"Error executing tools: {e}", exc_info=True)
            return (
                f"I tried to use one or more tools, but encountered an error: {str(e)}\n\n"
                f"Here's my response without the tools:\n\n{response.split('[TOOL]')[0]}"
            )

    async def _process_tool_call(self, response: str, channel: str) -> str:
        """Legacy method - redirects to the new multiple tool call processor."""
        return await self._process_tool_calls(response, channel)

    async def start(self) -> None:
        """Start the Slack bot."""
        await self.initialize_servers()
        await self.initialize_bot_info()
        # Start the socket mode handler
        logging.info("Starting Slack bot...")
        asyncio.create_task(self.socket_mode_handler.start_async())
        logging.info("Slack bot started and waiting for messages")

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if hasattr(self, "socket_mode_handler"):
                await self.socket_mode_handler.close_async()
            logging.info("Slack socket mode handler closed")
        except Exception as e:
            logging.error(f"Error closing socket mode handler: {e}")

        # Clean up servers
        for server in self.servers:
            try:
                await server.cleanup()
                logging.info(f"Server {server.name} cleaned up")
            except Exception as e:
                logging.error(f"Error during cleanup of server {server.name}: {e}")


async def main() -> None:
    """Initialize and run the Slack bot."""
    config = Configuration()

    if not config.slack_bot_token or not config.slack_app_token:
        raise ValueError(
            "SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables"
        )

    # Get this file from the servers config that is in the same directory as this file
    server_config = config.load_config(
        os.path.join(os.path.dirname(__file__), "servers_config.json")
    )

    # Inject environment variables into server configurations
    if (
        "slack" in server_config["mcpServers"]
        and config.mcp_server_oauth
        and config.mcp_team_id
    ):
        if "env" not in server_config["mcpServers"]["slack"]:
            server_config["mcpServers"]["slack"]["env"] = {}

        # Map environment variables to the expected Slack MCP server configuration
        server_config["mcpServers"]["slack"]["env"].update(
            {
                "SLACK_BOT_TOKEN": config.mcp_server_oauth,
                "SLACK_TEAM_ID": config.mcp_team_id,
            }
        )
        logging.info(
            "Injected MCP Slack server configuration from environment variables"
        )

    servers = [
        Server(name, srv_config)
        for name, srv_config in server_config["mcpServers"].items()
    ]

    llm_client = LLMClient(config.llm_api_key, config.llm_model)

    slack_bot = SlackMCPBot(
        config.slack_bot_token, config.slack_app_token, servers, llm_client
    )

    try:
        await slack_bot.start()
        # Keep the main task alive until interrupted
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Error: {e}")
    finally:
        await slack_bot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
