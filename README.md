# Private Chat Application with Kubernetes Autoscaling

> **NEW**: Now with Helm Chart for one-command Kubernetes deployment! 🚀

A multi-threaded private messaging application in Python with PostgreSQL authentication, Redis state management, and custom Kubernetes autoscaling.

## 🚀 Quick Start with Helm (Recommended)

```bash
# Clone the repository
git clone <your-repo-url>
cd chatp

# For Minikube users
minikube start --cpus=4 --memory=4096
docker build -t chat-server:latest .
docker build -t chat-autoscaler:latest -f Dockerfile.autoscaler .
minikube image load chat-server:latest
minikube image load chat-autoscaler:latest

# Deploy with Helm
helm install my-chat ./helm-chart/chat-app

# Wait for pods to be ready
kubectl wait --for=condition=ready pod --all -n chat-app --timeout=300s

# Connect client
python3 chat_client.py $(minikube ip) 30080
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

## 📚 Documentation

- **Quick Start**: [QUICKSTART_HELM.md](QUICKSTART_HELM.md) - 5-minute deployment guide
- **Helm Deployment**: [HELM_DEPLOYMENT.md](HELM_DEPLOYMENT.md) - Detailed Helm Chart guide
- **Kubernetes Guide**: [KUBERNETES.md](KUBERNETES.md) - Full K8s deployment
- **Bug Fixes**: [BUGFIXES_AND_TESTING.md](BUGFIXES_AND_TESTING.md) - Testing procedures

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

## Quick Start with Docker (Recommended)

### Prerequisites
- Docker
- Docker Compose

### Steps

1. **Start the services:**
```bash
cd chatp
docker-compose up -d
```

This will:
- Start PostgreSQL database on port 5432
- Initialize database schema automatically
- Start chat server on port 8080

2. **Run the client (on host machine):**
```bash
python chat_client.py localhost 8080
```

3. **Stop the services:**
```bash
docker-compose down
```

To remove data volumes:
```bash
docker-compose down -v
```

## Manual Installation (Without Docker)

### Prerequisites
- Python 3.8+
- PostgreSQL 12+

### Setup

1. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

2. **Setup PostgreSQL database:**
```bash
# Create database and user
psql -U postgres
CREATE DATABASE chatdb;
CREATE USER chatuser WITH PASSWORD 'chatpass';
GRANT ALL PRIVILEGES ON DATABASE chatdb TO chatuser;
\q

# Initialize schema
psql -U chatuser -d chatdb -f schema.sql
```

3. **Start the server:**
```bash
python chat_server.py 8080
```

4. **Start client(s):**
```bash
python chat_client.py localhost 8080
```

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

## Testing Instructions

### Automated Setup (Recommended)

Use the provided test script for quick setup:

```bash
cd chatp
./test.sh
```

This will:
- ✅ Check prerequisites (Docker, Python)
- ✅ Clean up existing containers
- ✅ Start PostgreSQL and Chat Server
- ✅ Wait for services to be ready
- ✅ Display testing instructions

---

### Manual Testing Steps

#### Step 1: Start the Server

```bash
cd chatp
docker-compose up -d --build
```

Wait 10-15 seconds for services to initialize, then verify:

```bash
docker-compose ps
```

You should see both `chat_server` and `chat_postgres` with status "Up".

---

#### Step 2: Test User Registration (First Client)

**Terminal 1:**
```bash
cd chatp
python3 chat_client.py localhost 8080
```

**Expected Output:**
```
Connected to the chat server

Waiting for authentication...

=== Chat Application Authentication ===
1. Login
2. Sign Up
Choose an option (1 or 2):
```

**Actions:**
1. Type `2` and press Enter (Sign Up)
2. Username: `alice`
3. Password: `password123` (hidden)
4. Confirm password: `password123`

**Expected Result:**
```
Registration successful. Welcome alice!

============================================================
  CHAT HISTORY (Last 50 messages)
============================================================
============================================================
  End of chat history
============================================================

No other users connected
[alice]:
```

**Send a test message:**
```
[alice]: Hello, this is my first message!
```

**✅ Success Indicators:**
- No protocol messages displayed (e.g., `SIGNUP_PROMPT`, `AUTH_REQUEST`)
- Clean prompts and confirmation message
- Password input is hidden
- Ready to chat with `[alice]:` prompt

**Leave this terminal open!**

---

#### Step 3: Test Chat History (Second Client)

**Terminal 2:**
```bash
cd chatp
python3 chat_client.py localhost 8080
```

**Actions:**
1. Type `2` (Sign Up)
2. Username: `bob`
3. Password: `password456`
4. Confirm password: `password456`

**Expected Result:**
```
Registration successful. Welcome bob!

============================================================
  CHAT HISTORY (Last 50 messages)
============================================================
[2025-11-07 XX:XX:XX] alice: Hello, this is my first message!
============================================================
  End of chat history
============================================================

Connected users: {'alice'}

New user connected: bob
[bob]:
```

**✅ Key Test:** Bob should see Alice's previous message in the chat history!

**Send a message:**
```
[bob]: Hi Alice! I can see your message in the history!
```

**Check Terminal 1 (Alice):** You should see Bob's message appear immediately.

---

#### Step 4: Test Login Flow (Third Client)

**Terminal 3:**
```bash
cd chatp
python3 chat_client.py localhost 8080
```

**Actions:**
1. Type `1` (Login)
2. Username: `alice`
3. Password: `password123`

**Expected Result:**
```
Login successful

============================================================
  CHAT HISTORY (Last 50 messages)
============================================================
[2025-11-07 XX:XX:XX] alice: Hello, this is my first message!
[2025-11-07 XX:XX:XX] bob: Hi Alice! I can see your message in the history!
============================================================
  End of chat history
============================================================

Connected users: {'bob', 'alice'}

New user connected: alice
[alice]:
```

**✅ Key Test:** Alice sees ALL previous messages when logging in again!

---

#### Step 5: Test Failed Login → Signup Redirect

**Terminal 4:**
```bash
cd chatp
python3 chat_client.py localhost 8080
```

**Actions:**
1. Type `1` (Login)
2. Username: `charlie`
3. Password: `wrongpassword`

**Expected Result:**
```
Invalid username or password
Redirecting to sign up...

=== Sign Up ===
Choose a username:
```

**✅ Key Test:** Failed login automatically redirects to signup!

**Complete signup:**
1. Username: `charlie`
2. Password: `password789`
3. Confirm: `password789`

---

#### Step 6: Test Message Broadcasting

With **all 4 terminals** still open (Alice x2, Bob, Charlie):

**In Charlie's terminal, type:**
```
[charlie]: Hello everyone from Charlie!
```

**Check ALL other terminals:**
- Alice (Terminal 1): Should see Charlie's message
- Bob (Terminal 2): Should see Charlie's message
- Alice (Terminal 3): Should see Charlie's message

**✅ Key Test:** Message appears in all connected clients!

---

#### Step 7: Test Disconnect

**In any terminal, type:**
```
bye
```

**Expected:**
- That client disconnects
- All other clients see: `<username> has quitted.`

---

#### Step 8: Test Database Persistence

**Close all clients** (type `bye` in each).

**Restart the server:**
```bash
docker-compose restart chat_server
```

**Wait 5 seconds, then reconnect:**
```bash
python3 chat_client.py localhost 8080
```

**Login as Bob:**
1. Type `1` (Login)
2. Username: `bob`
3. Password: `password456`

**✅ Key Test:** You should see ALL previous messages in the chat history!

This proves messages are persisted in the PostgreSQL database.

---

### Testing Checklist

Use this checklist to verify all features:

- [ ] Server starts successfully with Docker
- [ ] User can sign up with new account
- [ ] User can login with existing account
- [ ] Failed login redirects to signup
- [ ] Chat history displays on login
- [ ] Messages broadcast to all connected users
- [ ] User disconnect notifications work
- [ ] Messages persist after server restart
- [ ] No protocol messages leak to user interface
- [ ] Password input is hidden (using getpass)

---

### Quick 2-Minute Test

For a rapid verification:

```bash
# Terminal 1: Start server
cd chatp
./test.sh

# Terminal 2: Alice
python3 chat_client.py localhost 8080
# Type: 2, alice, pass123, pass123
# Message: "Test 1"

# Terminal 3: Bob
python3 chat_client.py localhost 8080
# Type: 2, bob, pass456, pass456
# Check: See "Test 1" in history? ✅
# Message: "Test 2"

# Terminal 2: Check Alice sees "Test 2" ✅

# Terminal 4: Login as Alice
python3 chat_client.py localhost 8080
# Type: 1, alice, pass123
# Check: See BOTH messages? ✅

# If all checks pass: System is working! ✅
```

---

### Expected vs Problematic Output

**✅ GOOD (Clean Authentication):**
```
Connected to the chat server

Waiting for authentication...

=== Chat Application Authentication ===
1. Login
2. Sign Up
Choose an option (1 or 2): 2

=== Sign Up ===
Choose a username: alice
Choose a password: [hidden]
Confirm password: [hidden]

Registration successful. Welcome alice!
```

**❌ BAD (Protocol Leak - If You See This, Report It):**
```
Connected to the chat server
AUTH_REQUEST          ← Should NOT appear!
=== Chat Application Authentication ===
1. Login
2. Sign Up
Choose an option (1 or 2): 2
SIGNUP_PROMPT         ← Should NOT appear!
```

If you see protocol messages (`AUTH_REQUEST`, `SIGNUP_PROMPT`, `LOGIN_PROMPT`), the system has a bug.

## Authentication Flow

```
Client connects → Server sends AUTH_REQUEST
                ↓
User chooses Login or Signup
                ↓
    ┌───────────┴───────────┐
    │                       │
  LOGIN                  SIGNUP
    │                       │
    ├─ Enter credentials    ├─ Enter new credentials
    ├─ Validate against DB  ├─ Check username availability
    ├─ Create session       ├─ Hash and store password
    └─ Send chat history    ├─ Auto-login
                            └─ Send chat history
                ↓
        Start chatting
```

## Environment Variables

Configure database connection (useful for Docker):

- `DB_HOST` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5432)
- `DB_NAME` - Database name (default: chatdb)
- `DB_USER` - Database user (default: chatuser)
- `DB_PASS` - Database password (default: chatpass)

## Security Features

1. **Password Hashing**: SHA-256 hashing (consider bcrypt for production)
2. **Session Tracking**: Monitor active user sessions
3. **Input Validation**: Username uniqueness enforced
4. **SQL Injection Prevention**: Parameterized queries with psycopg2

## Docker Commands

### View logs
```bash
docker-compose logs -f chat_server
docker-compose logs -f postgres
```

### Restart services
```bash
docker-compose restart
```

### Check service status
```bash
docker-compose ps
```

### Access PostgreSQL container
```bash
docker exec -it chat_postgres psql -U chatuser -d chatdb
```

### Rebuild after code changes
```bash
docker-compose up -d --build
```

## Development

### Database Queries

Connect to database:
```bash
psql -U chatuser -d chatdb
```

Useful queries:
```sql
-- View all users
SELECT * FROM users;

-- View recent messages
SELECT username, message_text, timestamp
FROM messages
ORDER BY timestamp DESC
LIMIT 10;

-- View active sessions
SELECT s.session_id, u.username, s.login_time
FROM sessions s
JOIN users u ON s.user_id = u.user_id
WHERE s.is_active = TRUE;
```

## Troubleshooting

### Client can't connect to server
- Ensure server is running: `docker-compose ps`
- Check firewall settings
- Verify port 8080 is not in use

### Database connection errors
- Wait for PostgreSQL to be ready (healthcheck in docker-compose)
- Check database credentials
- Verify PostgreSQL is running: `docker-compose logs postgres`

### Password not working
- Passwords are case-sensitive
- Ensure no trailing spaces in username/password

## Future Enhancements

- [ ] Private messaging between users
- [ ] Message search functionality
- [ ] User profiles and avatars
- [ ] File sharing
- [ ] Encryption for passwords (bcrypt)
- [ ] Rate limiting
- [ ] Admin panel
- [ ] Message editing/deletion
- [ ] Typing indicators
- [ ] Read receipts

## License

Educational project based on original Java code by www.codejava.net

## Contributors

- Original Java version: www.codejava.net
- Python port with authentication: ENPM631 Project
