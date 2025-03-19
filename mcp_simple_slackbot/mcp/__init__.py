"""MCP (Model Context Protocol) integration module."""

# Import names in __all__ are imported lazily to avoid circular imports
__all__ = ["Server", "Tool"]

# These will be populated when imported
Server = None
Tool = None

# Import at the end to avoid circular imports
from mcp_simple_slackbot.mcp.tool import Tool as _Tool
from mcp_simple_slackbot.mcp.server import Server as _Server

# Assign to module attributes
Server = _Server
Tool = _Tool