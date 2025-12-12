#!/bin/bash
# ============================================================
# LOAD_TEST.SH - Load Testing with Autoscaling Verification
# Tests chat application load and verifies autoscaler behavior
# ============================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

NAMESPACE="chat-app"
MINIKUBE_IP=$(minikube ip)
NODE_PORT=$(kubectl get svc chat-service -n $NAMESPACE -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "30080")

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║              LOAD TEST & AUTOSCALING VERIFICATION            ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${CYAN}Test Server: ${YELLOW}$MINIKUBE_IP:$NODE_PORT${NC}"
echo ""

# Function to get current pod count
get_pod_count() {
    kubectl get pods -n $NAMESPACE -l app=chat-server --no-headers 2>/dev/null | grep "Running" | wc -l
}

# Function to get autoscaler logs (last 5 lines)
get_autoscaler_status() {
    kubectl logs -n $NAMESPACE deployment/chat-autoscaler --tail=5 2>/dev/null | tail -1
}

# Function to create test client connection
create_test_client() {
    local username=$1
    local password="test123"
    local client_num=$2
    
    # Create a simple Python script to simulate a client
    cat > /tmp/test_client_$client_num.py << EOF
import socket
import time
import sys

def test_client(host, port, username, password):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, int(port)))
        
        # Receive welcome
        sock.recv(1024)
        
        # Send signup option
        sock.sendall(b"2\n")
        time.sleep(0.1)
        
        # Send username
        sock.sendall(f"{username}\n".encode())
        time.sleep(0.1)
        
        # Send password
        sock.sendall(f"{password}\n".encode())
        time.sleep(0.1)
        
        # Send password confirmation
        sock.sendall(f"{password}\n".encode())
        time.sleep(0.1)
        
        # Stay connected
        print(f"[{username}] Connected successfully", flush=True)
        
        # Keep connection alive
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print(f"[{username}] Disconnecting...", flush=True)
        sock.close()
    except Exception as e:
        print(f"[{username}] Error: {e}", flush=True)
        sys.exit(1)

if __name__ == "__main__":
    test_client(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
EOF

    # Run client in background
    python3 /tmp/test_client_$client_num.py $MINIKUBE_IP $NODE_PORT $username $password > /tmp/client_$client_num.log 2>&1 &
    echo $!
}

# Function to display current status
display_status() {
    local user_count=$1
    local pod_count=$2
    local autoscaler_log=$3
    
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 Current Status:${NC}"
    echo -e "   Online Users: ${GREEN}$user_count${NC}"
    echo -e "   Running Pods: ${GREEN}$pod_count${NC}"
    echo -e "   Autoscaler:   $autoscaler_log"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Array to store client PIDs
CLIENT_PIDS=()

# Cleanup function
cleanup_clients() {
    echo ""
    echo -e "${YELLOW}Cleaning up test clients...${NC}"
    for pid in "${CLIENT_PIDS[@]}"; do
        kill $pid 2>/dev/null || true
    done
    rm -f /tmp/test_client_*.py /tmp/client_*.log
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Trap to cleanup on exit
trap cleanup_clients EXIT INT TERM

# ============================================================
# TEST SEQUENCE
# ============================================================

echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                      TEST SEQUENCE                           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Initial state
echo -e "${YELLOW}[PHASE 0] Initial State${NC}"
INITIAL_PODS=$(get_pod_count)
display_status 0 $INITIAL_PODS "$(get_autoscaler_status)"
sleep 2

# Phase 1: Add 3 users (should stay at 1 pod)
echo ""
echo -e "${YELLOW}[PHASE 1] Adding 3 users (should maintain $INITIAL_PODS pod)${NC}"
for i in {1..3}; do
    echo -n "  Starting user$i... "
    PID=$(create_test_client "user$i" $i)
    CLIENT_PIDS+=($PID)
    echo "PID=$PID"
    sleep 2
done

echo "Waiting for autoscaler to evaluate (15s)..."
sleep 15

PODS_PHASE1=$(get_pod_count)
display_status 3 $PODS_PHASE1 "$(get_autoscaler_status)"

if [ "$PODS_PHASE1" -eq "$INITIAL_PODS" ]; then
    echo -e "${GREEN}✓ PASS: Autoscaler correctly maintained $INITIAL_PODS pod for 3 users${NC}"
else
    echo -e "${RED}✗ FAIL: Expected $INITIAL_PODS pod, got $PODS_PHASE1${NC}"
fi

# Phase 2: Add 4th user (should trigger scale to 2 pods)
echo ""
echo -e "${YELLOW}[PHASE 2] Adding 4th user (should scale to 2 pods)${NC}"
PID=$(create_test_client "user4" 4)
CLIENT_PIDS+=($PID)
echo "  Starting user4... PID=$PID"

echo "Waiting for autoscaler to scale up (30s)..."
for i in {1..30}; do
    sleep 1
    CURRENT_PODS=$(get_pod_count)
    if [ "$CURRENT_PODS" -gt "$PODS_PHASE1" ]; then
        echo -e "${GREEN}✓ Scale-up detected after ${i}s!${NC}"
        break
    fi
    echo -n "."
done
echo ""

PODS_PHASE2=$(get_pod_count)
display_status 4 $PODS_PHASE2 "$(get_autoscaler_status)"

if [ "$PODS_PHASE2" -gt "$PODS_PHASE1" ]; then
    echo -e "${GREEN}✓ PASS: Autoscaler scaled up to $PODS_PHASE2 pods${NC}"
else
    echo -e "${YELLOW}⚠ WARNING: No scale-up detected. Check autoscaler logs:${NC}"
    kubectl logs -n $NAMESPACE deployment/chat-autoscaler --tail=20
fi

# Phase 3: Add more users to trigger further scaling
echo ""
echo -e "${YELLOW}[PHASE 3] Adding users 5-7 (may trigger more scaling)${NC}"
for i in {5..7}; do
    echo -n "  Starting user$i... "
    PID=$(create_test_client "user$i" $i)
    CLIENT_PIDS+=($PID)
    echo "PID=$PID"
    sleep 2
done

echo "Waiting for autoscaler to evaluate (30s)..."
sleep 30

PODS_PHASE3=$(get_pod_count)
display_status 7 $PODS_PHASE3 "$(get_autoscaler_status)"

if [ "$PODS_PHASE3" -gt "$PODS_PHASE2" ]; then
    echo -e "${GREEN}✓ PASS: Autoscaler scaled to $PODS_PHASE3 pods${NC}"
elif [ "$PODS_PHASE3" -eq "$PODS_PHASE2" ]; then
    echo -e "${YELLOW}⚠ INFO: Pods remained at $PODS_PHASE3 (within threshold)${NC}"
fi

# Phase 4: Show pod distribution
echo ""
echo -e "${YELLOW}[PHASE 4] Pod Distribution${NC}"
kubectl get pods -n $NAMESPACE -l app=chat-server -o wide

# Phase 5: Show autoscaler logs
echo ""
echo -e "${YELLOW}[PHASE 5] Autoscaler Logs (last 20 lines)${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
kubectl logs -n $NAMESPACE deployment/chat-autoscaler --tail=20
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Phase 6: Test scale-down (disconnect users)
echo ""
echo -e "${YELLOW}[PHASE 6] Testing scale-down (disconnecting all users)${NC}"
echo "This will take ~90s (60s cooldown + 30s evaluation)..."

cleanup_clients
sleep 10

echo "Waiting for autoscaler to detect and scale down (90s)..."
for i in {1..90}; do
    sleep 1
    CURRENT_PODS=$(get_pod_count)
    if [ "$CURRENT_PODS" -lt "$PODS_PHASE3" ]; then
        echo -e "${GREEN}✓ Scale-down detected after ${i}s!${NC}"
        break
    fi
    if [ $((i % 10)) -eq 0 ]; then
        echo -n "  ${i}s..."
    fi
done
echo ""

PODS_FINAL=$(get_pod_count)
display_status 0 $PODS_FINAL "$(get_autoscaler_status)"

if [ "$PODS_FINAL" -lt "$PODS_PHASE3" ]; then
    echo -e "${GREEN}✓ PASS: Autoscaler scaled down to $PODS_FINAL pod(s)${NC}"
else
    echo -e "${YELLOW}⚠ WARNING: No scale-down detected after 90s${NC}"
    echo "This may be normal if cooldown period hasn't elapsed"
fi

# Summary
echo ""
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                       TEST SUMMARY                           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}Test Results:${NC}"
echo -e "  Initial pods:     ${YELLOW}$INITIAL_PODS${NC}"
echo -e "  After 3 users:    ${YELLOW}$PODS_PHASE1${NC} (expected: $INITIAL_PODS)"
echo -e "  After 4 users:    ${YELLOW}$PODS_PHASE2${NC} (expected: >$PODS_PHASE1)"
echo -e "  After 7 users:    ${YELLOW}$PODS_PHASE3${NC}"
echo -e "  After cleanup:    ${YELLOW}$PODS_FINAL${NC} (expected: <$PODS_PHASE3)"
echo ""

# Overall verdict
SCALE_UP_OK=false
SCALE_DOWN_OK=false

if [ "$PODS_PHASE2" -gt "$PODS_PHASE1" ]; then
    SCALE_UP_OK=true
fi

if [ "$PODS_FINAL" -lt "$PODS_PHASE3" ]; then
    SCALE_DOWN_OK=true
fi

if $SCALE_UP_OK && $SCALE_DOWN_OK; then
    echo -e "${GREEN}✅ AUTOSCALING WORKING CORRECTLY!${NC}"
    echo -e "   ✓ Scale-up detected"
    echo -e "   ✓ Scale-down detected"
elif $SCALE_UP_OK; then
    echo -e "${YELLOW}⚠ PARTIAL SUCCESS${NC}"
    echo -e "   ✓ Scale-up detected"
    echo -e "   ✗ Scale-down not detected (may need more time)"
elif $SCALE_DOWN_OK; then
    echo -e "${YELLOW}⚠ PARTIAL SUCCESS${NC}"
    echo -e "   ✗ Scale-up not detected"
    echo -e "   ✓ Scale-down detected"
else
    echo -e "${RED}⚠ AUTOSCALING NEEDS INVESTIGATION${NC}"
    echo ""
    echo "Possible causes:"
    echo "  1. Autoscaler configuration (check USERS_PER_POD, thresholds)"
    echo "  2. Cooldown period not elapsed"
    echo "  3. Redis connection issues"
    echo ""
    echo "Check autoscaler logs:"
    echo "  kubectl logs -f deployment/chat-autoscaler -n $NAMESPACE"
fi

echo ""
echo -e "${CYAN}To manually verify:${NC}"
echo "  kubectl logs -f deployment/chat-autoscaler -n $NAMESPACE"
echo "  watch kubectl get pods -n $NAMESPACE -l app=chat-server"
echo ""