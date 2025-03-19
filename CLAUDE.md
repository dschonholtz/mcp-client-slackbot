# MCP Simple Slackbot - Development Guide

## Environment Setup
```bash
# Activate virtual environment (REQUIRED for all commands)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r mcp_simple_slackbot/requirements.txt
```

## Build/Run Commands
```bash
# Install in development mode
pip install -e .

# Start the Slackbot (recommended)
./run.sh

# Alternative methods to run:
# From project root
venv/bin/python -m mcp_simple_slackbot

# From module directory (legacy)
cd mcp_simple_slackbot
python -m mcp_simple_slackbot
```

## Testing Commands
```bash
# Run all tests
venv/bin/pytest

# Run unit tests only
venv/bin/pytest tests/unit

# Run integration tests only
venv/bin/pytest tests/integration

# Run tests with verbosity
venv/bin/pytest -v

# Run tests with coverage reporting
venv/bin/pytest --cov=mcp_simple_slackbot

# Run specific test file
venv/bin/pytest tests/unit/test_specific_file.py

# Run tests matching a pattern
venv/bin/pytest -k "test_pattern"
```

## Testing Guidelines

IMPORTANT: All code changes must be tested! Follow these guidelines:

1. **Test-Driven Development**:
   - Write tests before implementing features
   - Run tests frequently during development

2. **Test Coverage**:
   - Unit tests for individual functions and classes
   - Integration tests for component interactions
   - Test both success and failure cases

3. **Mocking**:
   - Use pytest fixtures and mocks for external dependencies
   - Use `pytest-asyncio` for testing async code
   - Mock API calls and external services

4. **Test Organization**:
   - Place unit tests in `tests/unit/`
   - Place integration tests in `tests/integration/`
   - Name test files with `test_` prefix
   - Name test functions with `test_` prefix

5. **Test Verification**:
   - Run tests before committing changes
   - Run tests before submitting PRs
   - Fix failing tests before moving on

## Code Style & Linting
```bash
# Run typecheck
venv/bin/pyright

# Run linter
venv/bin/ruff check .
```

## Project Structure
- **config/** - Configuration and settings
- **mcp/** - MCP server and tool integration
- **llm/** - LLM API integrations
- **slack/** - Slack app and event handlers
- **conversation/** - Conversation history management
- **tools/** - Tool execution and parsing
- **utils/** - Utility functions

## Code Style Guidelines
- Line length: 88 characters
- Python 3.10+ features
- Type annotations required
- Error handling with try/except blocks and proper logging
- CamelCase for classes, snake_case for functions/variables
- Imports organization: stdlib, third-party, local modules
- Async code with proper exception handling