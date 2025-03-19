"""Main application entry point."""

import asyncio
import logging
import os
from typing import List

from mcp_simple_slackbot.config.config import Configuration
from mcp_simple_slackbot.llm.client import LLMClient
from mcp_simple_slackbot.mcp.server import Server
from mcp_simple_slackbot.slack.bot import SlackMCPBot
from mcp_simple_slackbot.utils.logging import setup_logging


async def create_servers(config: Configuration) -> List[Server]:
    """Create MCP server instances.
    
    Args:
        config: Application configuration
        
    Returns:
        List of MCP server instances
    """
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

    return [
        Server(name, srv_config)
        for name, srv_config in server_config["mcpServers"].items()
    ]


async def run_bot() -> None:
    """Initialize and run the Slack bot."""
    # Setup logging
    setup_logging()

    config = Configuration()

    if not config.slack_bot_token or not config.slack_app_token:
        raise ValueError(
            "SLACK_BOT_TOKEN and SLACK_APP_TOKEN must be set in environment variables"
        )

    # Create MCP servers
    servers = await create_servers(config)
    
    # Create LLM client
    llm_client = LLMClient(config.llm_api_key, config.llm_model)

    # Create and start Slack bot
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


def main() -> None:
    """Run the application."""
    asyncio.run(run_bot())