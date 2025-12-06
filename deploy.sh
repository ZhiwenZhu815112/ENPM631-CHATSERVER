#!/bin/bash
# ========================================================================
# CLEAN_DEPLOY.SH - Full Cleanup + Fresh Deployment for Chat Application
# ========================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="chat-app"
HELM_RELEASE="my-chat"
HELM_CHART="./helm-chart/chat-app"

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║             CLEAN DEPLOYMENT: CLEANUP + REDEPLOY             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# CLEANUP
# ============================================================================

echo -e "${YELLOW}[CLEANUP]${NC} Removing old deployments & images..."

# Remove Helm release (if any)
echo "  • Uninstalling Helm release (if exists)..."
helm uninstall $HELM_RELEASE -n $NAMESPACE >/dev/null 2>&1 || true

# Delete namespace
echo "  • Deleting namespace: $NAMESPACE"
kubectl delete namespace $NAMESPACE --ignore-not-found=true >/dev/null 2>&1 || true

echo "  • Waiting for namespace to fully disappear..."
for i in {1..20}; do
    if ! kubectl get namespace $NAMESPACE >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
echo "  • Namespace cleared"

# Docker environment for Minikube
echo "  • Switching Docker to Minikube..."
eval $(minikube docker-env)

echo "  • Removing old local images..."
docker rmi -f chat-server:latest  >/dev/null 2>&1 || true
docker rmi -f chat-autoscaler:latest >/dev/null 2>&1 || true
docker image prune -f >/dev/null 2>&1 || true

echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# ============================================================================
# DEPLOYMENT
# ============================================================================

# 1 — Check tools
echo -e "${YELLOW}[1/10]${NC} Checking prerequisites..."
for cmd in helm kubectl minikube docker; do
    command -v $cmd >/dev/null || { echo -e "${RED}Missing: $cmd${NC}"; exit 1; }
done
echo -e "${GREEN}✓ All prerequisites OK${NC}"
echo ""

# 2 — Ensure Minikube is running
echo -e "${YELLOW}[2/10]${NC} Checking Minikube..."
if ! minikube status >/dev/null; then
    minikube start --cpus=4 --memory=4096
fi
eval $(minikube docker-env)
echo -e "${GREEN}✓ Minikube ready${NC}"
echo ""

# 3 — Build chat-server
echo -e "${YELLOW}[3/10]${NC} Building chat-server Docker image..."
docker build --no-cache -t chat-server:latest . || {
    echo -e "${RED}✗ Build failed (chat-server)${NC}"
    exit 1
}
echo -e "${GREEN}✓ chat-server built${NC}"
echo ""

# 4 — Build autoscaler
echo -e "${YELLOW}[4/10]${NC} Building chat-autoscaler image..."
docker build --no-cache -t chat-autoscaler:latest -f Dockerfile.autoscaler . || {
    echo -e "${RED}✗ Build failed (autoscaler)${NC}"
    exit 1
}
echo -e "${GREEN}✓ autoscaler built${NC}"
echo ""

# 5 — Pull DB images
echo -e "${YELLOW}[5/10]${NC} Pulling Redis & Postgres..."
docker pull redis:7-alpine
docker pull postgres:15-alpine
echo -e "${GREEN}✓ Base images pulled${NC}"
echo ""

# 6 — Helm install (THIS CREATES THE NAMESPACE)
echo -e "${YELLOW}[6/10]${NC} Deploying via Helm..."
helm install $HELM_RELEASE $HELM_CHART -n $NAMESPACE --create-namespace || {
    echo -e "${RED}✗ Helm deployment failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Helm deployment successful${NC}"
echo ""

# 7 — Initial wait
echo -e "${YELLOW}[7/10]${NC} Allowing pods to boot..."
sleep 10
echo -e "${GREEN}✓ Initial wait done${NC}"
echo ""

# 8 — Wait for pods
echo -e "${YELLOW}[8/10]${NC} Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod --all -n $NAMESPACE --timeout=300s || {
    echo -e "${YELLOW}⚠ Some pods not ready. Showing status:${NC}"
    kubectl get pods -n $NAMESPACE
}
echo ""
echo -e "${GREEN}✓ Pods ready${NC}"
echo ""

# 9 — Verify
echo -e "${YELLOW}[9/10]${NC} Verifying deployment..."
kubectl get pods -n $NAMESPACE
kubectl get svc -n $NAMESPACE
echo -e "${GREEN}✓ Verification complete${NC}"
echo ""

# 10 — Summary
echo -e "${YELLOW}[10/10]${NC} Deployment Summary"
echo ""

MINIKUBE_IP=$(minikube ip)
NODE_PORT=$(kubectl get svc chat-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}')

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                     DEPLOYMENT SUCCESSFUL!                   ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}📡 Connect using:${NC}"
echo "   python3 chat_client.py $MINIKUBE_IP $NODE_PORT"
echo ""

echo -e "${GREEN}🔍 Monitor pods:${NC}"
echo "   watch kubectl get pods -n $NAMESPACE"
echo ""

echo -e "${GREEN}📜 Logs:${NC}"
echo "   kubectl logs -f deployment/chat-server -n $NAMESPACE"
echo "   kubectl logs -f deployment/chat-autoscaler -n $NAMESPACE"
echo ""

echo -e "${GREEN}🎉 System ready!${NC}"
