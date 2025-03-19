"""UI components and blocks for Slack."""

from typing import List

from mcp_simple_slackbot.mcp.tool import Tool


class SlackUI:
    """Slack UI component builder."""
    
    @staticmethod
    def build_home_view(tools: List[Tool]) -> dict:
        """Build the App Home tab view.
        
        Args:
            tools: List of available tools
            
        Returns:
            Slack blocks for the home view
        """
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
        for tool in tools:
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
        
        return {"type": "home", "blocks": blocks}