#!/bin/bash
# ========================================================================
# START_DASHBOARD.SH - Start Dashboard with Port Forwarding
# ========================================================================
# This script:
# 1. Sets up port forwarding for Redis and PostgreSQL
# 2. Starts the monitoring dashboard
# 3. Cleans up port forwards on exit
# ========================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

NAMESPACE="chat-app"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           Starting Monitoring Dashboard                     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Check Prerequisites
# ============================================================================

echo -e "${YELLOW}[1/4]${NC} Checking prerequisites..."

# Check if kubectl is available
if ! command -v kubectl >/dev/null 2>&1; then
    echo -e "${RED}✗ kubectl not found. Please install kubectl.${NC}"
    exit 1
fi

# Check if python3.11 is available
if ! command -v python3.11 >/dev/null 2>&1; then
    echo -e "${RED}✗ python3.11 not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Check if dashboard.py exists
if [ ! -f "dashboard.py" ]; then
    echo -e "${RED}✗ dashboard.py not found in current directory${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# ============================================================================
# Verify Kubernetes Deployment
# ============================================================================

echo -e "${YELLOW}[2/4]${NC} Verifying Kubernetes deployment..."

# Check if namespace exists
if ! kubectl get namespace $NAMESPACE >/dev/null 2>&1; then
    echo -e "${RED}✗ Namespace '$NAMESPACE' not found${NC}"
    echo "  Please run './full-deploy.sh' first to deploy the application."
    exit 1
fi

# Check if services exist
SERVICES_OK=1

if ! kubectl get svc redis-service -n $NAMESPACE >/dev/null 2>&1; then
    echo -e "${RED}✗ redis-service not found${NC}"
    SERVICES_OK=0
fi

if ! kubectl get svc postgres-service -n $NAMESPACE >/dev/null 2>&1; then
    echo -e "${RED}✗ postgres-service not found${NC}"
    SERVICES_OK=0
fi

if [ $SERVICES_OK -eq 0 ]; then
    echo -e "${RED}Required services not found. Please deploy the application first.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Kubernetes deployment verified${NC}"
echo ""

# ============================================================================
# Setup Port Forwarding
# ============================================================================

echo -e "${YELLOW}[3/4]${NC} Setting up port forwarding..."

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up port forwards...${NC}"

    if [ ! -z "$REDIS_PID" ] && kill -0 $REDIS_PID 2>/dev/null; then
        kill $REDIS_PID 2>/dev/null
        echo -e "${GREEN}✓ Redis port forward stopped${NC}"
    fi

    if [ ! -z "$POSTGRES_PID" ] && kill -0 $POSTGRES_PID 2>/dev/null; then
        kill $POSTGRES_PID 2>/dev/null
        echo -e "${GREEN}✓ PostgreSQL port forward stopped${NC}"
    fi

    echo -e "${CYAN}Dashboard stopped. Goodbye!${NC}"
    exit 0
}

# Trap EXIT and SIGINT (Ctrl+C) to cleanup
trap cleanup EXIT INT TERM

# Check if ports are already in use
if lsof -Pi :6379 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Port 6379 is already in use${NC}"
    echo "  Attempting to continue... (may be existing port-forward)"
else
    # Start Redis port forward
    echo "  → Forwarding Redis (localhost:6379 → redis-service:6379)..."
    kubectl port-forward svc/redis-service 6379:6379 -n $NAMESPACE >/dev/null 2>&1 &
    REDIS_PID=$!
    echo -e "${GREEN}  ✓ Redis port forward started (PID: $REDIS_PID)${NC}"
fi

if lsof -Pi :5432 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ Port 5432 is already in use${NC}"
    echo "  Attempting to continue... (may be existing port-forward)"
else
    # Start PostgreSQL port forward
    echo "  → Forwarding PostgreSQL (localhost:5432 → postgres-service:5432)..."
    kubectl port-forward svc/postgres-service 5432:5432 -n $NAMESPACE >/dev/null 2>&1 &
    POSTGRES_PID=$!
    echo -e "${GREEN}  ✓ PostgreSQL port forward started (PID: $POSTGRES_PID)${NC}"
fi

# Wait for port forwards to be ready
echo "  → Waiting for port forwards to be ready..."
sleep 3

echo -e "${GREEN}✓ Port forwarding active${NC}"
echo ""

# ============================================================================
# Start Dashboard
# ============================================================================

echo -e "${YELLOW}[4/4]${NC} Starting dashboard..."
echo ""

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                   DASHBOARD STARTING...                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}📊 Dashboard URL: ${GREEN}http://localhost:5000${NC}"
echo -e "${CYAN}📡 Health Check:  ${GREEN}http://localhost:5000/api/health${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the dashboard and cleanup port forwards${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Start dashboard (this will run in foreground)
python3.11 dashboard.py

# Cleanup will be called automatically on exit
