#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Set up logging directory
LOG_DIR="logs"
mkdir -p $LOG_DIR

# Create timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/slackbot_$TIMESTAMP.log"

echo "Starting MCP Slackbot..."
echo "Logs will be written to $LOG_FILE"

# Run the application with logging
venv/bin/python -m mcp_simple_slackbot 2>&1 | tee $LOG_FILE