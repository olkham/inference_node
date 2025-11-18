#!/bin/bash

# Script to run the inference node in production mode with nohup
# This allows the process to continue running after SSH disconnect

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment not found. Please create one first."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run main.py in production mode with nohup
echo "Starting inference node in production mode..."
nohup python main.py --production > logs/nohup.log 2>&1 &

# Get the process ID
PID=$!
echo "Inference node started with PID: $PID"
echo $PID > logs/inference_node.pid

echo "Process is running in the background. Logs are being written to logs/nohup.log"
echo "To stop the process, run: kill $PID"
echo "Or use: kill \$(cat logs/inference_node.pid)"
