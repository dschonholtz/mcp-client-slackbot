"""Configuration management for MCP Slackbot."""

import json
import os
from typing import Any, Dict

from dotenv import load_dotenv


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

        # Always raise ValueError when no keys are available
        raise ValueError("No API key found for any LLM provider")