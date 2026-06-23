#!/bin/bash
# Development script for Personal Quant Web Console
# Starts both FastAPI backend and Vite frontend dev server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo " Personal Quant Web Console - Dev Mode"
echo "=========================================="
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "Error: Python not found"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "Error: Node.js not found"
    exit 1
fi

# Install Python dependencies if needed
echo "Checking Python dependencies..."
pip install fastapi uvicorn python-jose passlib python-multipart pyyaml 2>/dev/null || true

# Install frontend dependencies if needed
echo "Checking frontend dependencies..."
cd "$ROOT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start FastAPI backend
echo ""
echo "Starting FastAPI backend on port 8000..."
cd "$ROOT_DIR"
python -m quant.apps.web --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Start Vite frontend
echo "Starting Vite frontend on port 5173..."
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================="
echo " Services started!"
echo "=========================================="
echo " Frontend: http://localhost:5173"
echo " Backend:  http://localhost:8000"
echo " API Docs: http://localhost:8000/docs"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop all services"

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

# Wait for processes
wait
