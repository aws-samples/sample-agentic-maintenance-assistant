#!/bin/bash

echo "Starting Agentic Maintenance Assistant"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this script from the maintenance-assistant-app directory"
    echo "   cd maintenance-assistant-app && ./start_all_servers.sh"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down all servers..."
    kill $ADMIN_PID $API_PID $CHAT_PID 2>/dev/null || true
    exit 0
}

# Set trap to cleanup on Ctrl+C
trap cleanup SIGINT

# Kill any existing processes for clean restart
echo "Stopping any existing servers..."
pkill -f "python3.*asset_api" 2>/dev/null || true
pkill -f "python3.*api_server" 2>/dev/null || true
pkill -f "python3.*chat_server" 2>/dev/null || true
pkill -f "npm start" 2>/dev/null || true
pkill -f "react-scripts" 2>/dev/null || true

# Kill processes on specific ports
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
lsof -ti:5001 | xargs kill -9 2>/dev/null || true
lsof -ti:5002 | xargs kill -9 2>/dev/null || true

echo "Waiting for processes to terminate..."
sleep 3

# Check and install Python dependencies
echo "Checking Python dependencies..."
if ! pip3 show flask > /dev/null 2>&1; then
    echo "Installing Python dependencies..."
    pip3 install -r ../requirements.txt
else
    echo "Python dependencies already installed"
fi

# Check and install Node dependencies
echo "Checking Node.js dependencies..."
if [ ! -d "node_modules" ]; then
    echo "Installing Node.js dependencies..."
    npm install
else
    echo "Node.js dependencies already installed"
fi

# Start backend servers in background
echo "Starting Asset API server (port 5001)..."
python3 asset_api.py &
ADMIN_PID=$!

echo "Starting API server (port 5000)..."
python3 api_server.py &
API_PID=$!

echo "Starting Chat server (port 5002)..."
python3 chat_server.py > chat_server.log 2>&1 &
CHAT_PID=$!

# Wait for servers to start
echo "Waiting for servers to initialize..."
sleep 5

# Check if servers are running with detailed feedback
echo "Checking server status..."
servers_ok=true

if ps -p $ADMIN_PID > /dev/null; then
    echo "Asset API server running (PID: $ADMIN_PID)"
else
    echo "Asset API server failed to start"
    servers_ok=false
fi

if ps -p $API_PID > /dev/null; then
    echo "API server running (PID: $API_PID)"
else
    echo "API server failed to start"
    servers_ok=false
fi

if ps -p $CHAT_PID > /dev/null; then
    echo "Chat server running (PID: $CHAT_PID)"
else
    echo "Chat server failed to start (check chat_server.log)"
    servers_ok=false
fi

if [ "$servers_ok" = false ]; then
    echo ""
    echo "WARNING: Some servers failed to start. Check the logs above."
    echo "   You can still continue, but some features may not work."
    echo ""
fi

# Display access URLs
echo ""
echo "Access URLs:"
echo "   Main App:     http://localhost:3000"
echo "   Admin Panel:  http://localhost:3000/admin"
echo "   API Server:   http://localhost:5000"
echo "   Asset API:    http://localhost:5001"
echo "   Chat Server:  http://localhost:5002"
echo ""
echo "Tips:"
echo "   • Click on alerts in the main app to open AI chat"
echo "   • Use the admin panel to configure assets and maps"
echo "   • Check chat_server.log if chat features aren't working"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Start React app (this will block until Ctrl+C)
echo "Starting React frontend..."
npm start

# Cleanup will be called by trap