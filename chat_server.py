import socket
import sys
import os
import threading
import json
from user_thread import UserThread
from db_manager import DatabaseManager
from redis_manager import RedisManager

"""
This is the chat server program with database authentication.
Press Ctrl + C to terminate the program.

@author www.codejava.net (Java version)
Python port with PostgreSQL authentication
"""

class ChatServer:
    def __init__(self, port, db_host="localhost", db_port=5432, db_name="chatdb", db_user="chatuser", db_pass="chatpass",
                 redis_host="localhost", redis_port=6379, redis_pass=None):
        self.port = port
        self.user_threads = set()
        # Local cache: Maps username -> UserThread for users connected to THIS pod
        self.online_users = {}

        # Server ID (pod name in Kubernetes, hostname otherwise)
        self.server_id = os.getenv("HOSTNAME", f"server-{os.getpid()}")

        # Initialize database manager
        self.db_manager = DatabaseManager(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_pass
        )

        # Initialize Redis manager for distributed state
        self.redis_manager = RedisManager(
            host=redis_host,
            port=redis_port,
            password=redis_pass
        )

        # Start Redis pub/sub listener for inter-pod messaging
        self.pubsub_thread = None
        self._start_message_listener()

    def _start_message_listener(self):
        """Start listening for messages from other pods via Redis pub/sub"""
        def listen_for_messages():
            try:
                pubsub = self.redis_manager.subscribe_to_channel("chat_messages")
                if pubsub:
                    print(f"[{self.server_id}] Subscribed to chat_messages channel")
                    for message in pubsub.listen():
                        if message['type'] == 'message':
                            try:
                                data = json.loads(message['data'])
                                target_username = data.get('target_username')
                                msg_content = data.get('message')
                                sender_server = data.get('sender_server_id')

                                # Only deliver if user is connected to THIS pod
                                if target_username in self.online_users and sender_server != self.server_id:
                                    user_thread = self.online_users[target_username]
                                    user_thread.send_message(msg_content)
                                    print(f"[{self.server_id}] Relayed message to {target_username} from pod {sender_server}")
                            except Exception as e:
                                print(f"Error processing pub/sub message: {e}")
            except Exception as e:
                print(f"Error in message listener: {e}")

        self.pubsub_thread = threading.Thread(target=listen_for_messages, daemon=True)
        self.pubsub_thread.start()

    def execute(self):
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind(('', self.port))
            server_socket.listen()

            print(f"Chat Server is listening on port {self.port}")
            print(f"Database connected and ready")

            while True:
                client_socket, address = server_socket.accept()
                print(f"New connection from {address}")

                new_user = UserThread(client_socket, self)
                self.user_threads.add(new_user)
                new_user.start()

        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.db_manager.close_all_connections()
        except IOError as ex:
            print(f"Error in the server: {ex}")
            import traceback
            traceback.print_exc()
        finally:
            self.db_manager.close_all_connections()

    def send_to_user(self, recipient_username, message):
        """
        Send a message to a specific user by username
        Uses Redis pub/sub to route messages across pods
        Returns True if user is online (in Redis), False otherwise
        """
        # Check if user is online (in Redis global state)
        if not self.redis_manager.is_user_online(recipient_username):
            return False

        # If user is on THIS pod, send directly
        if recipient_username in self.online_users:
            user_thread = self.online_users[recipient_username]
            user_thread.send_message(message)
            print(f"[{self.server_id}] Direct message sent to {recipient_username}")
            return True
        else:
            # User is on a different pod, publish to Redis
            msg_data = {
                'target_username': recipient_username,
                'message': message,
                'sender_server_id': self.server_id
            }
            success = self.redis_manager.publish_message("chat_messages", msg_data)
            if success:
                print(f"[{self.server_id}] Published message for {recipient_username} to Redis")
            return success

    def add_online_user(self, username, user_thread):
        """
        Register a user as online with their UserThread
        Updates both local cache and Redis global state
        """
        # Add to local cache (this pod)
        self.online_users[username] = user_thread

        # Add to Redis (global state across all pods)
        user_info = {
            'user_id': getattr(user_thread, 'user_id', None)
        }
        self.redis_manager.add_online_user(username, self.server_id, user_info)

        print(f"[{self.server_id}] User {username} is now online")

    def remove_user(self, username, user_thread):
        """
        When a client is disconnected, removes the user from online list
        Updates both local cache and Redis global state
        """
        # Remove from local cache
        if username in self.online_users:
            del self.online_users[username]

        # Remove from Redis
        self.redis_manager.remove_online_user(username)

        if user_thread in self.user_threads:
            self.user_threads.remove(user_thread)

        print(f"[{self.server_id}] The user {username} quitted")

    def get_online_usernames(self):
        """
        Get list of currently online usernames
        Queries Redis for global state across all pods
        """
        return self.redis_manager.get_online_usernames()

    def is_user_online(self, username):
        """
        Check if a user is currently online
        Queries Redis for global state across all pods
        """
        return self.redis_manager.is_user_online(username)

    def has_users(self):
        """
        Returns true if there are other users connected
        """
        return len(self.online_users) > 0


    def get_db_manager(self):
        """Return the database manager instance"""
        return self.db_manager


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Syntax: python chat_server.py <port-number>")
        sys.exit(0)

    port = int(sys.argv[1])

    # Get database config from environment variables (for Docker/Kubernetes)
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "chatdb")
    db_user = os.getenv("DB_USER", "chatuser")
    db_pass = os.getenv("DB_PASS", "chatpass")

    # Get Redis config from environment variables (for Kubernetes)
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_pass = os.getenv("REDIS_PASSWORD", None)
    if redis_pass == "":
        redis_pass = None

    server = ChatServer(port, db_host, db_port, db_name, db_user, db_pass,
                       redis_host, redis_port, redis_pass)
    server.execute()
