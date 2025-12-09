#!/bin/bash
# ========================================================================
# CLEANUP.SH - Complete Cleanup Script
# ========================================================================
# This script removes all deployed resources:
# 1. Stops port forwarding processes
# 2. Uninstalls Helm release
# 3. Deletes Kubernetes namespace
# 4. Optionally removes Docker images
# 5. Cleans up temporary files
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

echo -e "${RED}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║                    CLEANUP SCRIPT                            ║${NC}"
echo -e "${RED}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Parse Arguments
# ============================================================================

CLEAN_IMAGES=false
FORCE_CLEANUP=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --images)
            CLEAN_IMAGES=true
            shift
            ;;
        --force)
            FORCE_CLEANUP=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --images    Also remove Docker images"
            echo "  --force     Skip confirmation prompt"
            echo "  -h, --help  Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Basic cleanup (interactive)"
            echo "  $0 --images           # Cleanup including Docker images"
            echo "  $0 --force            # Cleanup without confirmation"
            echo "  $0 --images --force   # Full cleanup without confirmation"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# Confirmation
# ============================================================================

if [ "$FORCE_CLEANUP" = false ]; then
    echo -e "${YELLOW}⚠️  WARNING: This will remove the following:${NC}"
    echo "   • Helm release: $HELM_RELEASE"
    echo "   • Kubernetes namespace: $NAMESPACE"
    echo "   • All pods, services, and deployments in the namespace"
    echo "   • All persistent data (PostgreSQL data)"

    if [ "$CLEAN_IMAGES" = true ]; then
        echo "   • Docker images: chat-server:latest, chat-autoscaler:latest"
    fi

    echo ""
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${CYAN}Cleanup cancelled.${NC}"
        exit 0
    fi
    echo ""
fi

# ============================================================================
# STEP 1: Kill Port Forwarding Processes
# ============================================================================

echo -e "${YELLOW}[1/5]${NC} Stopping port forwarding processes..."

# Find and kill kubectl port-forward processes
PORT_FORWARD_PIDS=$(ps aux | grep "kubectl port-forward" | grep -v grep | awk '{print $2}' || true)

if [ -z "$PORT_FORWARD_PIDS" ]; then
    echo -e "${CYAN}  → No port forwarding processes found${NC}"
else
    echo "$PORT_FORWARD_PIDS" | while read -r pid; do
        kill $pid 2>/dev/null || true
        echo -e "${GREEN}  ✓ Stopped port-forward process (PID: $pid)${NC}"
    done
fi

echo -e "${GREEN}✓ Port forwarding processes cleaned${NC}"
echo ""

# ============================================================================
# STEP 2: Uninstall Helm Release
# ============================================================================

echo -e "${YELLOW}[2/5]${NC} Uninstalling Helm release..."

if helm list -n $NAMESPACE 2>/dev/null | grep -q $HELM_RELEASE; then
    helm uninstall $HELM_RELEASE -n $NAMESPACE
    echo -e "${GREEN}✓ Helm release '$HELM_RELEASE' uninstalled${NC}"
else
    echo -e "${CYAN}  → Helm release '$HELM_RELEASE' not found${NC}"
fi

echo ""

# ============================================================================
# STEP 3: Delete Namespace
# ============================================================================

echo -e "${YELLOW}[3/5]${NC} Deleting namespace..."

if kubectl get namespace $NAMESPACE >/dev/null 2>&1; then
    kubectl delete namespace $NAMESPACE --ignore-not-found=true

    echo "  → Waiting for namespace to be fully deleted..."
    # Wait for namespace deletion (max 60 seconds)
    for i in {1..60}; do
        if ! kubectl get namespace $NAMESPACE >/dev/null 2>&1; then
            break
        fi
        sleep 1
        if [ $((i % 10)) -eq 0 ]; then
            echo "  → Still deleting... ($i seconds)"
        fi
    done

    echo -e "${GREEN}✓ Namespace '$NAMESPACE' deleted${NC}"
else
    echo -e "${CYAN}  → Namespace '$NAMESPACE' not found${NC}"
fi

echo ""

# ============================================================================
# STEP 4: Clean Docker Images (Optional)
# ============================================================================

echo -e "${YELLOW}[4/5]${NC} Cleaning Docker images..."

if [ "$CLEAN_IMAGES" = true ]; then
    # Switch to minikube docker env if minikube is running
    if command -v minikube >/dev/null 2>&1 && minikube status >/dev/null 2>&1; then
        echo "  → Switching to Minikube Docker environment..."
        eval $(minikube docker-env)
    fi

    # Remove chat application images
    IMAGES=("chat-server:latest" "chat-autoscaler:latest")

    for image in "${IMAGES[@]}"; do
        if docker images | grep -q "$(echo $image | cut -d: -f1)"; then
            docker rmi -f $image >/dev/null 2>&1 || true
            echo -e "${GREEN}  ✓ Removed image: $image${NC}"
        else
            echo -e "${CYAN}  → Image not found: $image${NC}"
        fi
    done

    # Clean up dangling images
    echo "  → Cleaning up dangling images..."
    docker image prune -f >/dev/null 2>&1 || true

    echo -e "${GREEN}✓ Docker images cleaned${NC}"
else
    echo -e "${CYAN}  → Skipping Docker images cleanup${NC}"
    echo -e "${CYAN}  → Use --images flag to remove Docker images${NC}"
fi

echo ""

# ============================================================================
# STEP 5: Clean Temporary Files
# ============================================================================

echo -e "${YELLOW}[5/5]${NC} Cleaning temporary files..."

# Clean Python cache
if [ -d "__pycache__" ]; then
    rm -rf __pycache__
    echo -e "${GREEN}  ✓ Removed __pycache__${NC}"
fi

# Clean .pyc files
PYCS=$(find . -name "*.pyc" 2>/dev/null || true)
if [ ! -z "$PYCS" ]; then
    find . -name "*.pyc" -delete
    echo -e "${GREEN}  ✓ Removed .pyc files${NC}"
fi

# Clean Python egg-info
if [ -d "*.egg-info" ]; then
    rm -rf *.egg-info
    echo -e "${GREEN}  ✓ Removed .egg-info${NC}"
fi

echo -e "${GREEN}✓ Temporary files cleaned${NC}"
echo ""

# ============================================================================
# Summary
# ============================================================================

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                    CLEANUP COMPLETE! ✨                      ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${GREEN}📋 Summary:${NC}"
echo -e "${GREEN}  ✓ Port forwarding processes stopped${NC}"
echo -e "${GREEN}  ✓ Helm release uninstalled${NC}"
echo -e "${GREEN}  ✓ Namespace deleted${NC}"

if [ "$CLEAN_IMAGES" = true ]; then
    echo -e "${GREEN}  ✓ Docker images removed${NC}"
else
    echo -e "${YELLOW}  ⊘ Docker images preserved${NC}"
fi

echo -e "${GREEN}  ✓ Temporary files cleaned${NC}"
echo ""

echo -e "${CYAN}🔄 To redeploy the application, run:${NC}"
echo "   ./full-deploy.sh"
echo ""

echo -e "${CYAN}💡 Tip: Use './cleanup.sh --images' to also remove Docker images${NC}"
echo ""

# ============================================================================
# Verification
# ============================================================================

echo -e "${YELLOW}📊 Verification:${NC}"

# Check namespace
if kubectl get namespace $NAMESPACE >/dev/null 2>&1; then
    echo -e "${RED}  ✗ Namespace still exists (may be terminating)${NC}"
else
    echo -e "${GREEN}  ✓ Namespace deleted${NC}"
fi

# Check Helm release
if helm list -n $NAMESPACE 2>/dev/null | grep -q $HELM_RELEASE; then
    echo -e "${RED}  ✗ Helm release still exists${NC}"
else
    echo -e "${GREEN}  ✓ Helm release removed${NC}"
fi

# Check port forwards
if ps aux | grep "kubectl port-forward" | grep -v grep >/dev/null 2>&1; then
    echo -e "${YELLOW}  ⚠ Some port-forward processes may still be running${NC}"
else
    echo -e "${GREEN}  ✓ No port-forward processes running${NC}"
fi

echo ""
echo -e "${GREEN}All cleanup tasks completed! 🎉${NC}"
