# Quick Start with Helm Chart

## 🚀 For Instructors/Reviewers

This guide will get the application running in **5 minutes**.

### Prerequisites
- Kubernetes cluster (Minikube or Docker Desktop with Kubernetes enabled)
- kubectl installed
- Helm 3.x installed
- Docker installed

---

## ⚡ One-Command Deployment

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd chatp

# 2. Start Kubernetes (if using Minikube)
minikube start --cpus=4 --memory=4096

# 3. Build Docker images
docker build -t chat-server:latest .
docker build -t chat-autoscaler:latest -f Dockerfile.autoscaler .

# 4. Load images (Minikube only, skip for Docker Desktop)
minikube image load chat-server:latest
minikube image load chat-autoscaler:latest

# 5. Deploy with Helm
helm install my-chat ./helm-chart/chat-app

# 6. Wait for pods (2-3 minutes)
kubectl wait --for=condition=ready pod --all -n chat-app --timeout=300s

# ✅ Done!
```

---

## 📊 Verify Deployment

```bash
# Check all resources
kubectl get all -n chat-app

# Expected output:
NAME                                   READY   STATUS    RESTARTS   AGE
pod/chat-autoscaler-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
pod/chat-server-xxxxxxxxxx-xxxxx       1/1     Running   0          2m
pod/postgres-0                         1/1     Running   0          2m
pod/redis-xxxxxxxxxx-xxxxx             1/1     Running   0          2m

NAME                      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
service/chat-service      NodePort    10.96.xxx.xxx   <none>        8080:30080/TCP   2m
service/postgres-service  ClusterIP   None            <none>        5432/TCP         2m
service/redis-service     ClusterIP   10.96.xxx.xxx   <none>        6379/TCP         2m

# View autoscaler logs
kubectl logs -f deployment/chat-autoscaler -n chat-app
```

---

## 🎮 Test the Application

### Connect Client

```bash
# For Minikube
python3 chat_client.py $(minikube ip) 30080

# For Docker Desktop
python3 chat_client.py localhost 30080
```

### Create Test Users

**Terminal 1:**
```
Choose option: 2 (Sign Up)
Username: alice
Password: test123
```

**Terminal 2:**
```
Choose option: 2 (Sign Up)
Username: bob
Password: test123
```

**Terminal 3:**
```
Choose option: 2 (Sign Up)
Username: carol
Password: test123
```

**Terminal 4:**
```
Choose option: 2 (Sign Up)
Username: david
Password: test123
```

---

## 📈 Watch Autoscaling in Action

### Setup Monitoring

**Terminal A:** Monitor Autoscaler
```bash
kubectl logs -f deployment/chat-autoscaler -n chat-app
```

**Terminal B:** Monitor Pods
```bash
watch kubectl get pods -n chat-app -l app=chat-server
```

### Observe Scaling

**Expected behavior:**
- **1-3 users online**: 1 Pod
- **4th user logs in**: Autoscaler scales to 2 Pods (within 10 seconds)
- **7th user logs in**: Scales to 3 Pods
- **Users log out**: After 60 seconds, scales back down

**Autoscaler log output:**
```
[22:00:00] Users: 3 | Current: 1 Pods | Desired: 1 Pods | ✓ No change needed
[22:00:10] Users: 4 | Current: 1 Pods | Desired: 2 Pods | ↗️  SCALING UP
✅ Scaled deployment to 2 replicas
```

---

## 🧹 Cleanup

```bash
# Uninstall application
helm uninstall my-chat

# Delete namespace
kubectl delete namespace chat-app

# Stop Minikube (if using)
minikube stop
```

---

## 🔧 Troubleshooting

### Pods not starting?

```bash
# Check pod status
kubectl get pods -n chat-app

# Describe problematic pod
kubectl describe pod <pod-name> -n chat-app

# Check logs
kubectl logs <pod-name> -n chat-app
```

**Common issue:** Images not loaded (Minikube)
```bash
minikube image load chat-server:latest
minikube image load chat-autoscaler:latest
```

### Can't connect to server?

```bash
# For Minikube, get IP
minikube ip

# Or use port-forward
kubectl port-forward svc/chat-service -n chat-app 8080:8080
python3 chat_client.py localhost 8080
```

### Autoscaler not working?

```bash
# Check autoscaler logs
kubectl logs deployment/chat-autoscaler -n chat-app

# Check online users in Redis
kubectl exec -it deployment/redis -n chat-app -- redis-cli SCARD online_users

# Check RBAC permissions
kubectl describe role chat-autoscaler-role -n chat-app
```

---

## 📚 More Information

- Full deployment guide: `HELM_DEPLOYMENT.md`
- Project README: `README.md`
- Bug fixes and testing: `BUGFIXES_AND_TESTING.md`

---

**Ready to start? Run the commands in the "One-Command Deployment" section! 🚀**
