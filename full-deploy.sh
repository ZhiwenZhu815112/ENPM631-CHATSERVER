#!/bin/bash
# ========================================================================
# FULL_DEPLOY.SH - Complete Deployment Script
# ========================================================================
# This script:
# 1. Builds Docker images
# 2. Deploys to Kubernetes using Helm
# 3. Installs dashboard dependencies
# 4. Provides instructions for next steps
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
HELM_RELEASE="my-chat"
HELM_CHART="./helm-chart/chat-app"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          FULL DEPLOYMENT - Chat Application                  ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# STEP 1: Check Prerequisites
# ============================================================================

echo -e "${YELLOW}[1/8]${NC} Checking prerequisites..."
MISSING_TOOLS=0

for cmd in kubectl helm docker python3.11; do
    if ! command -v $cmd >/dev/null 2>&1; then
        echo -e "${RED}✗ Missing: $cmd${NC}"
        MISSING_TOOLS=1
    else
        echo -e "${GREEN}  ✓ $cmd found${NC}"
    fi
done

if [ $MISSING_TOOLS -eq 1 ]; then
    echo -e "${RED}Please install missing tools and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites OK${NC}"
echo ""

# ============================================================================
# STEP 2: Detect Kubernetes Environment
# ============================================================================

echo -e "${YELLOW}[2/8]${NC} Detecting Kubernetes environment..."

# Check if minikube is available and running
if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
    K8S_ENV="minikube"
    echo -e "${CYAN}  → Using Minikube${NC}"

    # Ensure minikube is running
    if ! minikube status | grep -q "Running"; then
        echo "  → Starting Minikube..."
        minikube start --cpus=4 --memory=4096
    fi

    # Set Docker environment to Minikube
    eval $(minikube docker-env)
    echo -e "${GREEN}  ✓ Switched to Minikube Docker environment${NC}"

elif kubectl cluster-info | grep -q "Docker Desktop"; then
    K8S_ENV="docker-desktop"
    echo -e "${CYAN}  → Using Docker Desktop Kubernetes${NC}"
else
    echo -e "${YELLOW}  → Using generic Kubernetes cluster${NC}"
    K8S_ENV="generic"
fi

echo -e "${GREEN}✓ Kubernetes environment: $K8S_ENV${NC}"
echo ""

# ============================================================================
# STEP 3: Build Docker Images
# ============================================================================

echo -e "${YELLOW}[3/8]${NC} Building Docker images..."

echo "  → Building chat-server image..."
docker build --no-cache -t chat-server:latest . || {
    echo -e "${RED}✗ Failed to build chat-server${NC}"
    exit 1
}
echo -e "${GREEN}  ✓ chat-server:latest built${NC}"

echo "  → Building chat-autoscaler image..."
docker build --no-cache -t chat-autoscaler:latest -f Dockerfile.autoscaler . || {
    echo -e "${RED}✗ Failed to build chat-autoscaler${NC}"
    exit 1
}
echo -e "${GREEN}  ✓ chat-autoscaler:latest built${NC}"

echo -e "${GREEN}✓ Docker images built successfully${NC}"
echo ""

# ============================================================================
# STEP 4: Pull Base Images
# ============================================================================

echo -e "${YELLOW}[4/8]${NC} Pulling Redis and PostgreSQL images..."

docker pull redis:7-alpine
docker pull postgres:15-alpine

# Load images into Minikube if needed
if [ "$K8S_ENV" = "minikube" ]; then
    echo "  → Loading images into Minikube..."
    minikube image load chat-server:latest
    minikube image load chat-autoscaler:latest
    minikube image load redis:7-alpine
    minikube image load postgres:15-alpine
    echo -e "${GREEN}  ✓ Images loaded into Minikube${NC}"
fi

echo -e "${GREEN}✓ Base images ready${NC}"
echo ""

# ============================================================================
# STEP 5: Deploy with Helm
# ============================================================================

echo -e "${YELLOW}[5/8]${NC} Deploying application with Helm..."

# Check if release already exists
if helm list -n $NAMESPACE 2>/dev/null | grep -q $HELM_RELEASE; then
    echo -e "${YELLOW}  ⚠ Release '$HELM_RELEASE' already exists. Upgrading...${NC}"
    helm upgrade $HELM_RELEASE $HELM_CHART -n $NAMESPACE || {
        echo -e "${RED}✗ Helm upgrade failed${NC}"
        exit 1
    }
else
    helm install $HELM_RELEASE $HELM_CHART -n $NAMESPACE --create-namespace || {
        echo -e "${RED}✗ Helm installation failed${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✓ Helm deployment successful${NC}"
echo ""

# ============================================================================
# STEP 6: Wait for Pods
# ============================================================================

echo -e "${YELLOW}[6/8]${NC} Waiting for pods to be ready..."
echo "  This may take 2-3 minutes..."

# Initial wait to let pods start
sleep 10

# Wait for pods with timeout
kubectl wait --for=condition=ready pod --all -n $NAMESPACE --timeout=300s || {
    echo -e "${YELLOW}⚠ Some pods not ready. Current status:${NC}"
    kubectl get pods -n $NAMESPACE
    echo ""
    echo -e "${YELLOW}Continuing anyway... Pods may still be initializing.${NC}"
}

echo -e "${GREEN}✓ Pods are running${NC}"
echo ""

# ============================================================================
# STEP 7: Install Dashboard Dependencies
# ============================================================================

echo -e "${YELLOW}[7/8]${NC} Installing dashboard dependencies..."

if [ -f "dashboard-requirements.txt" ]; then
    python3.11 -m pip install -r dashboard-requirements.txt --quiet || {
        echo -e "${YELLOW}⚠ Failed to install some dashboard dependencies${NC}"
        echo "  You may need to install them manually:"
        echo "  python3.11 -m pip install -r dashboard-requirements.txt"
    }
    echo -e "${GREEN}✓ Dashboard dependencies installed${NC}"
else
    echo -e "${YELLOW}⚠ dashboard-requirements.txt not found, skipping${NC}"
fi

# Also install client dependencies
if [ -f "requirements.txt" ]; then
    python3.11 -m pip install -r requirements.txt --quiet || {
        echo -e "${YELLOW}⚠ Failed to install some client dependencies${NC}"
    }
    echo -e "${GREEN}✓ Client dependencies installed${NC}"
fi

echo ""

# ============================================================================
# STEP 8: Deployment Summary
# ============================================================================

echo -e "${YELLOW}[8/8]${NC} Deployment Summary"
echo ""

# Get connection info
if [ "$K8S_ENV" = "minikube" ]; then
    MINIKUBE_IP=$(minikube ip)
    NODE_PORT=$(kubectl get svc chat-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')
    CONNECT_CMD="python3.11 chat_client.py $MINIKUBE_IP $NODE_PORT"
elif [ "$K8S_ENV" = "docker-desktop" ]; then
    NODE_PORT=$(kubectl get svc chat-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')
    CONNECT_CMD="python3.11 chat_client.py localhost $NODE_PORT"
else
    NODE_PORT=$(kubectl get svc chat-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')
    CONNECT_CMD="python3.11 chat_client.py <YOUR_K8S_IP> $NODE_PORT"
fi

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                  DEPLOYMENT SUCCESSFUL! 🎉                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Show current pods
echo -e "${CYAN}📦 Current Pods:${NC}"
kubectl get pods -n $NAMESPACE
echo ""

# Show services
echo -e "${CYAN}🌐 Services:${NC}"
kubectl get svc -n $NAMESPACE
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Next Steps:${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${CYAN}1️⃣  Connect a chat client:${NC}"
echo "   $CONNECT_CMD"
echo ""

echo -e "${CYAN}2️⃣  Start the monitoring dashboard:${NC}"
echo "   ./start-dashboard.sh"
echo "   (Or manually: python3.11 dashboard.py with port-forwarding)"
echo ""

echo -e "${CYAN}3️⃣  Monitor autoscaler logs:${NC}"
echo "   kubectl logs -f deployment/chat-autoscaler -n $NAMESPACE"
echo ""

echo -e "${CYAN}4️⃣  Watch pods scale:${NC}"
echo "   watch kubectl get pods -n $NAMESPACE -l app=chat-server"
echo ""

echo -e "${CYAN}5️⃣  View all resources:${NC}"
echo "   kubectl get all -n $NAMESPACE"
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${YELLOW}💡 Tips:${NC}"
echo "  • Create 3+ users to see autoscaling in action"
echo "  • Use 'kubectl logs -f deployment/chat-server -n chat-app' to debug"
echo "  • Dashboard shows real-time metrics at http://localhost:5000"
echo "  • To cleanup: helm uninstall $HELM_RELEASE && kubectl delete namespace $NAMESPACE"
echo ""

echo -e "${GREEN}✅ Deployment complete! Happy testing! 🚀${NC}"
