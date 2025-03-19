#!/bin/bash

# Check if logs directory exists
if [ ! -d "logs" ]; then
    echo "Error: logs directory does not exist. Run the application first."
    exit 1
fi

# Function to monitor the latest log file
monitor_latest_log() {
    # Get the most recent log file
    local latest_log=$(ls -t logs/slackbot_*.log 2>/dev/null | head -n 1)
    
    if [ -z "$latest_log" ]; then
        echo "No log files found. Run the application first."
        exit 1
    fi
    
    echo "Monitoring log file: $latest_log"
    echo "Press Ctrl+C to exit"
    echo "------------------------------------------------------------"
    
    # Use tail to follow the log file
    tail -f "$latest_log"
}

# Function to find logs by date
find_logs_by_date() {
    local date_pattern="$1"
    
    echo "Searching for logs with date pattern: $date_pattern"
    local matching_logs=$(ls -1 logs/slackbot_${date_pattern}*.log 2>/dev/null)
    
    if [ -z "$matching_logs" ]; then
        echo "No logs found for date pattern: $date_pattern"
        exit 1
    fi
    
    echo "Found matching logs:"
    echo "$matching_logs"
    echo "------------------------------------------------------------"
    
    # Get the most recent matching log
    local latest_matching=$(ls -t logs/slackbot_${date_pattern}*.log 2>/dev/null | head -n 1)
    echo "Monitoring most recent matching log: $latest_matching"
    echo "Press Ctrl+C to exit"
    echo "------------------------------------------------------------"
    
    # Use tail to follow the log file
    tail -f "$latest_matching"
}

# Function to search logs
search_logs() {
    local search_term="$1"
    local log_file="$2"
    
    if [ -z "$log_file" ]; then
        echo "Searching all logs for: $search_term"
        grep --color=auto -i "$search_term" logs/slackbot_*.log
    else
        echo "Searching $log_file for: $search_term"
        grep --color=auto -i "$search_term" "$log_file"
    fi
}

# Function to filter logs by component
filter_by_component() {
    local component="$1"
    local log_file="$2"
    
    if [ -z "$log_file" ]; then
        # Get the most recent log file
        log_file=$(ls -t logs/slackbot_*.log 2>/dev/null | head -n 1)
    fi
    
    echo "Filtering $log_file for component: $component"
    echo "Press Ctrl+C to exit"
    echo "------------------------------------------------------------"
    
    # Use grep to filter and tail to follow
    tail -f "$log_file" | grep --color=auto -i "$component"
}

# Function to display tool calls
show_tool_calls() {
    local log_file="$1"
    
    if [ -z "$log_file" ]; then
        # Get the most recent log file
        log_file=$(ls -t logs/slackbot_*.log 2>/dev/null | head -n 1)
    fi
    
    echo "Showing tool calls in $log_file"
    echo "Press Ctrl+C to exit"
    echo "------------------------------------------------------------"
    
    # Use grep to filter for tool-related logs and tail to follow
    tail -f "$log_file" | grep --color=auto -i -E "(Looking for tool:|Executing tool:|Tool .* result:|Parsed tool calls)"
}

# Main menu
show_menu() {
    echo "====== Log Monitor Tool ======"
    echo "1. Monitor latest log file"
    echo "2. Find logs by date (YYYYMMDD)"
    echo "3. Search logs for keyword"
    echo "4. Filter logs by component"
    echo "5. Show tool calls only"
    echo "6. Exit"
    echo "============================"
    echo -n "Enter your choice [1-6]: "
}

# Main loop
while true; do
    show_menu
    read choice
    
    case "$choice" in
        1)
            monitor_latest_log
            ;;
        2)
            echo -n "Enter date pattern (YYYYMMDD): "
            read date_pattern
            find_logs_by_date "$date_pattern"
            ;;
        3)
            echo -n "Enter search term: "
            read search_term
            echo -n "Enter specific log file (or leave empty for all logs): "
            read log_file
            search_logs "$search_term" "$log_file"
            ;;
        4)
            echo -n "Enter component name to filter (e.g., parser, handler, server): "
            read component
            echo -n "Enter specific log file (or leave empty for latest): "
            read log_file
            filter_by_component "$component" "$log_file"
            ;;
        5)
            echo -n "Enter specific log file (or leave empty for latest): "
            read log_file
            show_tool_calls "$log_file"
            ;;
        6)
            echo "Exiting."
            exit 0
            ;;
        *)
            echo "Invalid choice. Please try again."
            ;;
    esac
    
    # If we get here, we've returned from a command, so wait for user input
    echo "Press Enter to return to menu..."
    read
done