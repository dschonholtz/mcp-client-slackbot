"""Main Slack bot implementation."""

import asyncio
import logging
from typing import List, Optional, Union

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient

from mcp_simple_slackbot.conversation.manager import ConversationManager
from mcp_simple_slackbot.llm.client import LLMClient
from mcp_simple_slackbot.mcp.server import Server
from mcp_simple_slackbot.mcp.tool import Tool
from mcp_simple_slackbot.slack.handlers import SlackEventHandlers
from mcp_simple_slackbot.tools.executor import ToolExecutor


class SlackMCPBot:
    """Manages the Slack bot integration with MCP servers."""

    def __init__(
        self,
        slack_bot_token: str,
        slack_app_token: str,
        servers: List[Server],
        llm_client: LLMClient,
    ) -> None:
        """Initialize the Slack MCP bot.
        
        Args:
            slack_bot_token: Slack bot token (xoxb-...)
            slack_app_token: Slack app token (xapp-...)
            servers: List of MCP servers
            llm_client: LLM client for message processing
        """
        self.app = AsyncApp(token=slack_bot_token)
        # Create a socket mode handler with the app token
        self.socket_mode_handler = AsyncSocketModeHandler(self.app, slack_app_token)

        self.client = AsyncWebClient(token=slack_bot_token)
        self.servers = servers
        self.llm_client = llm_client
        self.bot_id: Optional[str] = None
        self.tools: List[Tool] = []
        
        # Initialize conversation manager
        self.conversation_manager = ConversationManager()
        
        # Initialize tool executor
        self.tool_executor = ToolExecutor(servers, llm_client)
        
        # Initialize event handlers
        self.event_handlers = SlackEventHandlers(
            self.client,
            self.conversation_manager,
            self.llm_client,
            self.tool_executor,
            self.tools,
        )
        
        # Set up event handlers
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """Register event handlers with the Slack app."""
        self.app.event("app_mention")(self.event_handlers.handle_mention)
        self.app.message()(self.event_handlers.handle_message)
        self.app.event("app_home_opened")(self.event_handlers.handle_home_opened)

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
        
        # Update handlers with tools
        self.event_handlers.tools = self.tools

    async def initialize_bot_info(self) -> None:
        """Get the bot's ID and other info."""
        try:
            auth_info = await self.client.auth_test()
            self.bot_id = auth_info["user_id"]
            logging.info(f"Bot initialized with ID: {self.bot_id}")
            # Update handlers with bot ID
            self.event_handlers.set_bot_id(self.bot_id)
        except Exception as e:
            logging.error(f"Failed to get bot info: {e}")
            self.bot_id = None

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