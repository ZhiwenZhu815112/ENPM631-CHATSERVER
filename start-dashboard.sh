#!/bin/bash

# Chat Server Monitoring Dashboard Startup Script
# This script sets up and runs the monitoring dashboard

echo "🚀 Starting Chat Server Monitoring Dashboard"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "dashboard.py" ]; then
    echo "❌ dashboard.py not found. Please run this script from the project root directory."
    exit 1
fi

# Install/upgrade dashboard dependencies
echo "📦 Installing dashboard dependencies..."
pip install -r dashboard-requirements.txt

echo ""
echo "🔧 Configuration Options:"
echo "  Set these environment variables to customize the dashboard:"
echo ""
echo "  Kubernetes:"
echo "    NAMESPACE=chat-app                    # K8s namespace to monitor"
echo "    DEPLOYMENT_NAME=chat-server           # Deployment name to monitor"
echo ""
echo "  Redis:"
echo "    REDIS_HOST=localhost                  # Redis host"
echo "    REDIS_PORT=6379                       # Redis port"
echo "    REDIS_PASSWORD=                       # Redis password (if any)"
echo ""
echo "  Database:"
echo "    DB_HOST=localhost                     # PostgreSQL host"
echo "    DB_PORT=5432                          # PostgreSQL port"
echo "    DB_NAME=chatdb                        # Database name"
echo "    DB_USER=chatuser                      # Database user"
echo "    DB_PASS=chatpass                      # Database password"
echo ""
echo "🌐 Starting dashboard on http://localhost:5000"
echo "   Press Ctrl+C to stop"
echo ""

# Start the dashboard
python3 dashboard.py