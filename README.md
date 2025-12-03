# Private Chat Application with Kubernetes Autoscaling

> **NEW**: Now with Helm Chart for one-command Kubernetes deployment! 🚀

A multi-threaded private messaging application in Python with PostgreSQL authentication, Redis state management, and custom Kubernetes autoscaling.

## 🚀 Quick Start with Helm (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd chatp

# Build necessary image first
minikube start --cpus=4 --memory=4096
docker build -t chat-server:latest .
docker build -t chat-autoscaler:latest -f Dockerfile.autoscaler .

# Deploy with Helms
helm install my-chat ./helm-chart/chat-app

# Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n chat-app --timeout=300s

# Connect client
python3 chat_client.py localhost 30080
```

See [QUICKSTART_HELM.md](QUICKSTART_HELM.md) for complete instructions.

## ✨ Key Features

- ⭐ **Custom Autoscaler** - No KEDA required, scales based on online users
- ⭐ **Helm Chart** - One-command deployment
- 🔐 **User Authentication** - Login and signup with password hashing
- 💬 **Private Messaging** - One-on-one conversations
- 📊 **Kubernetes Horizontal Scaling** - Automatically scales from 1 to 10 pods
- 💾 **PostgreSQL + Redis** - Persistent storage and distributed state
- 🔄 **Real-time Notifications** - Instant message delivery
- 🐳 **Containerized** - Docker and Kubernetes ready

---

## Features (Detailed)

- **User Authentication**: Login and signup system with password hashing
- **Private Messaging**: One-on-one conversations with real-time delivery
- **Chat History**: View last 50 messages when logging in
- **Persistent Storage**: All messages stored in PostgreSQL database
- **Multi-threaded**: Supports multiple concurrent users
- **Containerized**: Docker and Kubernetes ready
- **Session Management**: Track active user sessions with Redis
- **Auto-scaling**: Custom Kubernetes autoscaler based on user count

## Project Structure

```
chatp/
├── chat_server.py      # Main server application
├── user_thread.py      # Server-side thread handling each client
├── chat_client.py      # Client application
├── read_thread.py      # Client thread for receiving messages
├── write_thread.py     # Client thread for sending messages
├── db_manager.py       # Database connection and operations
├── schema.sql          # PostgreSQL database schema
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker image for server
├── docker-compose.yml  # Docker orchestration
└── README.md           # This file
```

## Architecture

### Database Schema

**users table:**
- `user_id` (Primary Key)
- `username` (Unique)
- `password_hash` (SHA-256)
- `created_at` (Timestamp)

**messages table:**
- `message_id` (Primary Key)
- `user_id` (Foreign Key)
- `username`
- `message_text`
- `timestamp`
- `message_type` (broadcast/private)

**sessions table:**
- `session_id` (Primary Key)
- `user_id` (Foreign Key)
- `login_time`
- `logout_time`
- `is_active`

## Usage

### First Time User

1. Connect to server
2. Choose option `2` (Sign Up)
3. Enter username and password
4. Start chatting

### Returning User

1. Connect to server
2. Choose option `1` (Login)
3. Enter credentials
4. View chat history (last 50 messages)
5. Start chatting

### Commands

- Type any message to broadcast to all users
- Type `bye` to disconnect

---