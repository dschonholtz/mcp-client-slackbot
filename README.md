# MCP Simple Slackbot

A simple Slack bot that uses the Model Context Protocol (MCP) to enhance its capabilities with external tools.

## Features

![2025-03-08-ezgif com-video-to-gif-converter](https://github.com/user-attachments/assets/0e2b6e1c-80f2-48c3-8ca4-1c41f3678478)

- **AI-Powered Assistant**: Responds to messages in channels and DMs using LLM capabilities
- **MCP Integration**: Full access to MCP tools like SQLite database and web fetching
- **Multi-LLM Support**: Works with OpenAI, Groq, and Anthropic models
- **App Home Tab**: Shows available tools and usage information

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click "Create New App"
2. Choose "From an app manifest" and select your workspace
3. Copy the contents of `mcp_simple_slackbot/manifest.yaml` into the manifest editor
4. Create the app and install it to your workspace
5. Under the "Basic Information" section, scroll down to "App-Level Tokens"
6. Click "Generate Token and Scopes" and:
   - Enter a name like "mcp-assistant"
   - Add the `connections:write` scope
   - Click "Generate"
7. Take note of both your:
   - Bot Token (`xoxb-...`) found in "OAuth & Permissions"
   - App Token (`xapp-...`) that you just generated

### 2. Install Dependencies

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install project dependencies
pip install -r mcp_simple_slackbot/requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the project root directory:

```bash
# Copy the example file
cp .env.example .env

# Edit the file with your credentials
nano .env  # or use your preferred editor
```

### 4. Install in Development Mode

```bash
# Install the package in development mode
pip install -e .
```

## Running the Bot

```bash
# Use the run script (recommended)
./run.sh

# Alternatively, run directly with Python
venv/bin/python -m mcp_simple_slackbot
```

The bot will:
1. Connect to all configured MCP servers
2. Discover available tools
3. Start the Slack app in Socket Mode
4. Listen for mentions and direct messages

## Usage

- **Direct Messages**: Send a direct message to the bot
- **Channel Mentions**: Mention the bot in a channel with `@MCP Assistant`
- **App Home**: Visit the bot's App Home tab to see available tools

## Architecture

The bot has been refactored into a modular architecture with clear separation of concerns:

- **config/** - Configuration and settings
- **mcp/** - MCP server and tool integration
- **llm/** - LLM API integrations (OpenAI, Groq, Anthropic)
- **slack/** - Slack app and event handlers
- **conversation/** - Conversation history management
- **tools/** - Tool execution and parsing
- **utils/** - Logging and utility functions

When a message is received, the bot:
1. Sends the message to the LLM along with available tools
2. Parses the LLM response for tool calls
3. Executes tools with the requested parameters
4. Returns the result to the LLM for interpretation
5. Delivers the final response to the user

For more details on development, testing, and code style, see the [CLAUDE.md](CLAUDE.md) file.

## Credits

This project is based on the [MCP Simple Chatbot example](https://github.com/modelcontextprotocol/python-sdk/tree/main/examples/clients/simple-chatbot).

## License

MIT License
