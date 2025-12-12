# Private Chat Application with Kubernetes Autoscaling

> **LATEST**: Now with **Session Persistence & Auto-Reconnection** for seamless user experience during pod scaling! 🚀

A production-ready, multi-threaded private messaging application in Python with PostgreSQL authentication, Redis state management, custom Kubernetes autoscaling, and intelligent reconnection capabilities.

---

## 📋 Table of Contents

- [Key Features](#-key-features)
- [What's New - Session Persistence](#-whats-new---session-persistence--auto-reconnection)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Testing](#-testing-the-reconnection-feature)
- [Monitoring Dashboard](#-monitoring-dashboard)
- [Detailed Features](#-detailed-features)
- [Project Structure](#-project-structure)
- [Usage Guide](#-usage-guide)

---

## ⭐ Key Features

### Core Functionality
- 🔐 **User Authentication** - Secure login/signup with SHA-256 password hashing
- 💬 **Multi-Channel Messaging** - Private messages, broadcast channel, and group chats
- 📜 **Message History** - Persistent storage with PostgreSQL
- 👥 **Group Chat** - Create groups, invite members, and manage group conversations
- 🔄 **Real-time Notifications** - Instant message delivery across pods

### Cloud-Native & Scalability
- 📊 **Custom Kubernetes Autoscaler** - Scales 1-10 pods based on online users (3 users per pod)
- ⚡ **Helm Chart Deployment** - One-command installation
- 🐳 **Multi-Pod Architecture** - Distributed state with Redis Pub/Sub
- 💾 **Persistent Storage** - PostgreSQL + Redis for data and state management

### Production Features ⭐ NEW
- 🔄 **Session Persistence** - Survive pod restarts without re-authentication
- 🚀 **Auto-Reconnection** - Seamless reconnection in 2-5 seconds during scale-down
- 📬 **Pending Messages** - Messages delivered even when temporarily disconnected

---

## 🆕 What's New - Session Persistence & Auto-Reconnection

```
┌─────────────────────────────────────────────────────────────┐
│ User Experience During Pod Scale-Down                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│ 1. User chatting normally on Pod B                           │
│    └─> Pod B scheduled for termination                       │
│                                                               │
│ 2. ⚠️  "SERVER MAINTENANCE: Reconnecting in seconds..."      │
│    └─> preStop hook notifies user (3s warning)               │
│                                                               │
│ 3. Connection lost (Pod B terminated)                        │
│    └─> Client detects disconnection                          │
│                                                               │
│ 4. 🔄 Auto-reconnection starts (2 second delay)              │
│    └─> Client connects to available pod (Pod A)              │
│                                                               │
│ 5. ✅ Session resumed using token (no login needed)          │
│    └─> Redis validates session token                         │
│                                                               │
│ 6. 📬 Pending messages delivered                             │
│    └─> Messages received while offline pushed to client      │
│                                                               │
│ 7. User continues chatting seamlessly                        │
│    └─> Total downtime: 2-5 seconds                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Technical Implementation

**1. Session Persistence** (`redis_manager.py`)
- UUID-based session tokens (10-minute expiry)
- Stored in Redis for global access across pods
- Automatic heartbeat refresh

**2. Auto-Reconnection** (`chat_client.py`, `read_thread.py`, `write_thread.py`)
- Client detects connection loss
- Automatic reconnection with exponential backoff
- Session token sent instead of credentials
- Transparent to user

**3. Pending Messages** (`redis_manager.py`, `chat_server.py`)
- Messages for offline users cached in Redis (max 100)
- Delivered on reconnection
- 10-minute retention

**4. Graceful Shutdown** (`chat-deployment.yaml`)
- Kubernetes `preStop` hook
- Notifies users 3 seconds before termination
- 30-second graceful period

---

## 🚀 Quick Start

### Prerequisites

```bash
# Required
- Docker Desktop or Minikube
- kubectl
- helm 3.x
- Python 3.11+
```

### Script Deployment (Automated)

```bash
# Terminal 1: Full deployment
./full-deploy.sh

# Terminal 2: Start monitoring dashboard
./start-dashboard.sh

# Terminal 3+: Connect clients
python3 chat_client.py localhost 30080  # alice
python3 chat_client.py localhost 30080  # bob
python3 chat_client.py localhost 30080  # carol

# Monitor autoscaling
kubectl logs -f deployment/chat-autoscaler -n chat-app
```

### Cleanup

```bash
# Basic cleanup (keeps Docker images)
./cleanup.sh

# Full cleanup (removes everything)
./cleanup.sh --images --force
```

---

## 🏗 Architecture

### High-Level Overview

```
┌────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Chat Server  │  │ Chat Server  │  │ Chat Server  │     │
│  │   Pod 1      │  │   Pod 2      │  │   Pod N      │     │
│  │ (3 users)    │  │ (3 users)    │  │ (3 users)    │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│  ┌─────────────────────────┴─────────────────────┐         │
│  │  Redis - State & Message Routing               │         │
│  │  • Online users (global)                       │         │
│  │  • Session tokens (10min TTL)                  │         │
│  │  • Pending messages queue                      │         │
│  │  • Pub/Sub for cross-pod messaging             │         │
│  └─────────────────────────┬─────────────────────┘         │
│                            │                                │
│  ┌─────────────────────────┴─────────────────────┐         │
│  │  PostgreSQL - Persistent Storage               │         │
│  │  • Users & authentication                      │         │
│  │  • Messages (private/broadcast/group)          │         │
│  │  • Groups & memberships                        │         │
│  │  • Sessions (audit log)                        │         │
│  └────────────────────────────────────────────────┘         │
│                                                              │
│  ┌────────────────────────────────────────────────┐         │
│  │  Custom Autoscaler                              │         │
│  │  • Monitors online users (Redis)                │         │
│  │  • Formula: Pods = ceil(users / 3)              │         │
│  │  • Range: 1-10 pods                             │         │
│  │  • Scale-down delay: 60s                        │         │
│  └────────────────────────────────────────────────┘         │
│                                                              │
│  ┌────────────────────────────────────────────────┐         │
│  │  Web Dashboard (Flask)                          │         │
│  │  • Real-time monitoring                         │         │
│  │  • User analytics                               │         │
│  │  • Health checks                                │         │
│  └────────────────────────────────────────────────┘         │
└────────────────────────────────────────────────────────────┘
         ↑                                ↑
    NodePort:30080                  Port-Forward:5000
         │                                │
    Python Client                   Browser Dashboard
```

### Database Schema

**users**
- `user_id` (PK), `username` (unique), `password_hash`, `created_at`

**messages**
- `message_id` (PK), `conversation_id` (FK), `sender_id`, `message_text`, `timestamp`

**conversations**
- `conversation_id` (PK), `participant1_id`, `participant2_id`

**broadcast_messages**
- `broadcast_id` (PK), `sender_id`, `message_text`, `timestamp`

**groups**
- `group_id` (PK), `group_name`, `description`, `creator_id`, `created_at`

**group_members**
- `group_id` (FK), `user_id` (FK), `role`, `joined_at`

**sessions**
- `session_id` (PK), `user_id` (FK), `login_time`, `logout_time`, `is_active`

### Redis Data Structures

**Session Management**
```
session:{uuid}           → {username, user_id, created_at, last_active}  [10min TTL]
user_session:{username}  → session_token                                  [10min TTL]
```

**Online Users**
```
online_users                    → Set of usernames
online_user:{username}          → {server_id, login_time, user_id}        [30min TTL]
```

**Pending Messages**
```
pending_messages:{username}     → List of {content, timestamp}            [10min TTL, max 100]
```

**Pub/Sub Channels**
```
chat_messages  → {target_username, message, sender_server_id}
```

---

## 📊 Monitoring Dashboard

### Quick Start

```bash
# Install dependencies
pip install -r dashboard-requirements.txt

# Start dashboard
./start-dashboard.sh

# Access at http://127.0.0.1:5001
```

### Dashboard Features

- **Real-time Metrics**
  - Online users (live count)
  - Active pods and their status
  - Message throughput
  - Autoscaling events

- **Health Monitoring**
  - PostgreSQL connection status
  - Redis availability
  - Autoscaler health
  - Pod readiness

- **Visualizations**
  - User activity over time (Chart.js)
  - Pod scaling timeline
  - Message volume graphs

- **REST API**
  - `GET /api/status` - System health
  - `GET /api/metrics` - Current metrics
  - `GET /api/health` - Component health checks

For detailed dashboard documentation, see [DASHBOARD_README.md](DASHBOARD_README.md)

---

## 📦 Detailed Features

### Messaging Capabilities

**Private Messages**
- One-on-one conversations
- Message history (last 50 messages)
- Online/offline status indicators
- Real-time delivery

**Broadcast Channel**
- Send messages to all online users
- View broadcast history
- Username display for all messages

**Group Chat**
- Create named groups with descriptions
- Invite/remove members
- Group message history
- Role-based permissions (creator/member)
- Search and join public groups

### Session & Authentication

**User Management**
- Secure signup with password confirmation
- SHA-256 password hashing
- Session tracking (login/logout times)
- Concurrent login prevention

**Session Persistence** ⭐ NEW
- Redis-based session tokens
- 10-minute session validity
- Automatic session renewal
- Cross-pod session recovery

### Scalability & High Availability

**Custom Autoscaler**
- Monitors Redis for user count
- Formula: `pods = ceil(users / 3)`
- Scale-up: Immediate
- Scale-down: 60-second delay
- Range: 1-10 pods

**Distributed Architecture**
- Stateless chat servers
- Redis for global state
- PostgreSQL for persistence
- Cross-pod message routing (Pub/Sub)

**Graceful Operations** ⭐ NEW
- preStop hooks notify users
- 30-second termination grace period
- Automatic client reconnection
- Zero message loss

---

## 📖 Usage Guide

### First Time User

1. **Connect to server**
   ```bash
   python3 chat_client.py localhost 30080
   ```

2. **Sign up**
   - Choose option `2` (Sign Up)
   - Enter username and password
   - Confirm password

3. **Start chatting**
   - Select from menu: Private Messages, Broadcast, Groups

### Returning User

1. **Login**
   - Choose option `1` (Login)
   - Enter credentials
   - View chat history (last 50 messages)

2. **Session Recovery** ⭐ NEW
   - If disconnected, client auto-reconnects
   - Session resumes automatically (no re-login)
   - Pending messages delivered

### Menu Navigation

```
========================================
        CHAT APPLICATION MENU
========================================
1. 💬 Private Messages      # One-on-one chat
2. 📢 Broadcast Channel      # Message all users
3. 👥 My Groups              # Your groups
4. 🔍 Browse All Groups      # Discover groups
5. ➕ Create New Group       # Start new group

Type 'bye' to logout
```

### Commands

- **Navigation**: Enter menu number (1-5)
- **Back**: Type `back` to return to previous screen
- **Exit**: Type `bye` to disconnect
- **Messages**: Type normally and press Enter

---
