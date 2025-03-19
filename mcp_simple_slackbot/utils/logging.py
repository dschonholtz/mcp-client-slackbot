"""Logging configuration for MCP Slackbot."""

import logging
import os
import sys
from typing import Optional


def setup_logging(level: int = logging.DEBUG, log_format: Optional[str] = None) -> None:
    """Configure logging for the application.
    
    Args:
        level: Logging level (default: DEBUG)
        log_format: Custom log format string
    """
    if log_format is None:
        log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
    )
    
    # Configure module-specific loggers
    logging.getLogger("mcp_simple_slackbot.slack.handlers").setLevel(logging.DEBUG)
    logging.getLogger("mcp_simple_slackbot.tools.parser").setLevel(logging.DEBUG)
    logging.getLogger("mcp_simple_slackbot.tools.executor").setLevel(logging.DEBUG)
    logging.getLogger("mcp_simple_slackbot.mcp.server").setLevel(logging.DEBUG)
    
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)
    
    # Log environment variables (without sensitive values)
    safe_env_vars = {
        k: v if not any(x in k.lower() for x in ["token", "key", "secret", "password", "auth"])
        else "[REDACTED]" 
        for k, v in os.environ.items()
    }
    logging.debug(f"Environment variables: {safe_env_vars}")
    
    # Log Python version
    logging.debug(f"Python version: {sys.version}")
    
    logging.info("Logging initialized")