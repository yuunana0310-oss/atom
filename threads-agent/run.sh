#!/bin/bash
# Daily run script for Threads automation system
# Recommended: run via cron at multiple times per day
# Example cron: 0 8,10,12,14,16,18,20 * * * /path/to/threads-agent/run.sh

cd "$(dirname "$0")"

# Load .env file if it exists
if [ -f ".env" ]; then
    source .env
fi

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Threads automation run..."
python main.py --agent all

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Run completed successfully."
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Run exited with code $EXIT_CODE."
fi

exit $EXIT_CODE
