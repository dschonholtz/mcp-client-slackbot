"""Default settings and constants for MCP Slackbot."""

# LLM Settings
DEFAULT_LLM_MODEL = "gpt-4-turbo"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 1500
DEFAULT_TIMEOUT = 30.0  # seconds
DEFAULT_MAX_RETRIES = 2

# API Endpoints
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"

# MCP Server settings
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_DELAY = 1.0  # seconds

# Slack message settings
MAX_TOOL_CALLS = 10
DEFAULT_CONVERSATION_HISTORY_LIMIT = 5