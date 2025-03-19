"""Logging configuration for MCP Slackbot."""

import logging
from typing import Optional


def setup_logging(level: int = logging.INFO, log_format: Optional[str] = None) -> None:
    """Configure logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        log_format: Custom log format string
    """
    if log_format is None:
        log_format = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
    )
    
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)