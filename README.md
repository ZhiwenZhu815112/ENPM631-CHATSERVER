# Chat Application with Kubernetes Autoscaling

Production-ready, multi-threaded private messaging with PostgreSQL, Redis, and custom Kubernetes autoscaling.

## ✨ Key Features

- 🔐 Secure user authentication (SHA-256)
- 💬 Private messages, broadcast, and group chat
- 🔄 Session persistence & auto-reconnection
- 📊 Custom autoscaler (1-10 pods, 3 users/pod)
- 🎯 Real-time monitoring dashboard
- 🐳 Docker + Helm deployment

## 🚀 Quick Start
```bash
# 1. Deploy everything
./scripts/full-deploy.sh

# 2. Start dashboard (separate terminal)
./scripts/start-dashboard.sh

# 3. Connect clients (separate terminals)
python3 chat_client.py localhost 30080
```

**Prerequisites:** Docker Desktop/Minikube, kubectl, Helm 3.x, Python 3.11+

## 📚 Documentation

- [📊 Dashboard Guide](docs/dashboard.md) - Monitoring and metrics
- [🚀 Deployment Guide](docs/deployment.md) - Helm charts & scripts
- [🧪 Testing Guide](docs/testing.md) - Load testing procedures

## 🏗️ Architecture
┌─────────────────────────────────────┐
│      Kubernetes Cluster             │
│  ┌──────────┐  ┌──────────┐         │
│  │Chat Pod 1│  │Chat Pod N│ (1-10)  │
│  └────┬─────┘  └────┬─────┘         │
│       └──────┬───────┘              │
│         ┌────▼─────┐                │
│         │  Redis   │ (state)        │
│         └────┬─────┘                │
│         ┌────▼─────┐                │
│         │PostgreSQL│ (data)         │
│         └──────────┘                │
└─────────────────────────────────────┘

**Components:**
- **Chat Server** (`chat_server.py`) - Multi-threaded message handling
- **PostgreSQL** - Users, messages, groups, sessions
- **Redis** - Online users, session tokens, Pub/Sub messaging
- **Autoscaler** (`autoscaler.py`) - Monitors users, scales pods
- **Dashboard** (`dashboard.py`) - Real-time monitoring (Flask)

## 🎮 Usage

**First Time:**
1. Connect: `python3 chat_client.py localhost 30080`
2. Sign up (option 2)
3. Choose from menu: Private Messages / Broadcast / Groups

**Returning User:**
- Login with credentials
- If disconnected during pod scaling, auto-reconnects in 2-5 seconds

**Menu Options:**

💬 Private Messages  - One-on-one chat
📢 Broadcast         - Message all users
👥 My Groups         - Your group chats
🔍 Browse Groups     - Discover groups
➕ Create Group      - Start new group


Type `bye` to logout.

## 📦 Database Schema

**Key Tables:**
- `users` - Authentication (username, password_hash)
- `messages` - Private & group messages
- `conversations` - Private chat threads
- `groups` / `group_members` - Group chat
- `broadcast_messages` - Broadcast channel
- `sessions` - Login audit log

**Redis Data:**
- `online_users` - Set of active usernames
- `session:{uuid}` - Session tokens (10min TTL)
- `pending_messages:{user}` - Offline message queue
- Pub/Sub `chat_messages` - Cross-pod routing

## 🔧 Deployment Options

### Automated (Recommended)
```bash
./scripts/full-deploy.sh    # Deploy
./scripts/cleanup.sh         # Cleanup
```

### Manual Helm
```bash
# Build images
docker build -t chat-server:latest .
docker build -t chat-autoscaler:latest -f Dockerfile.autoscaler .

# Deploy
helm install chat-app ./helm-chart/chat-app -n chat-app --create-namespace

# Verify
kubectl get pods -n chat-app
```

See [Deployment Guide](docs/deployment.md) for details.

## 📊 Monitoring

**Dashboard:** http://localhost:5001 (after running `./scripts/start-dashboard.sh`)

**Features:**
- Real-time user count
- Pod scaling events
- Message throughput
- Health checks (PostgreSQL, Redis, Autoscaler)

**Watch Autoscaler:**
```bash
kubectl logs -f deployment/chat-autoscaler -n chat-app
```


# Manual testing
python3 chat_client.py localhost 8080 # Terminal 1 (alice)
python3 chat_client.py localhost 8080  # Terminal 2 (bob)
```

See [Testing Guide](docs/testing.md) for comprehensive tests.

## 🔄 Autoscaling

**Logic:** `pods = ceil(online_users / 3)`

**Example:**
- 1-3 users → 1 pod
- 4-6 users → 2 pods
- 7-9 users → 3 pods
- Max: 10 pods

**Scale-down delay:** 60 seconds (prevents thrashing)

## 🛡️ Session Persistence

**What happens during pod scaling:**
1. User chatting on Pod B
2. ⚠️ Pod B scheduled for termination (3s warning)
3. Connection lost
4. 🔄 Client auto-reconnects to Pod A (2s delay)
5. ✅ Session resumes with token (no re-login)
6. 📬 Pending messages delivered
7. Total downtime: 2-5 seconds

**Implementation:**
- Session tokens stored in Redis (10min TTL)
- Auto-reconnection with exponential backoff
- Pending message queue (max 100, 10min retention)
- Kubernetes preStop hook (graceful shutdown)

## 📂 Project Structure
├── README.md              # This file
├── docs/                  # Documentation
│   ├── dashboard.md
│   ├── deployment.md
│   └── testing.md
├── scripts/               # Deployment scripts
│   ├── full-deploy.sh
│   ├── cleanup.sh
│   └── ...
├── helm-chart/            # Kubernetes charts
├── chat_server.py         # Main server
├── chat_client.py         # Client app
├── autoscaler.py          # Autoscaler
├── dashboard.py           # Monitoring
├── *_manager.py           # DB/Redis/Group managers
├── *_thread.py            # Threading components
└── requirements.txt       # Dependencies


## 👥 Contributors

- [Zhiwen Zhu](https://github.com/ZhiwenZhu815112)
- [Alessandro](https://github.com/alessandro1g)
- [Anirudh Raj](https://github.com/Aniraj1611)

## 📝 License

This project is for educational purposes (ENPM631 - University of Maryland).

---

**Questions?** Open an [issue](https://github.com/ZhiwenZhu815112/ENPM631-CHATSERVER/issues) or check the [docs](docs/).