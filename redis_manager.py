import redis
import json
import os
from datetime import datetime

"""
Redis manager for chat application
Handles online user state management across multiple server instances
"""

class RedisManager:
    def __init__(self, host="localhost", port=6379, password=None, db=0):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                password=password if password else None,
                db=db,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            print("Redis connection established successfully")
        except Exception as e:
            print(f"Error connecting to Redis: {e}")
            raise

    def add_online_user(self, username, server_id, user_info=None):
        """
        Register a user as online
        Args:
            username: Username
            server_id: Identifier for this server instance (e.g., pod name)
            user_info: Optional dictionary with additional info (user_id, etc.)
        """
        try:
            key = f"online_user:{username}"
            data = {
                "server_id": server_id,
                "login_time": datetime.utcnow().isoformat(),
            }
            if user_info:
                data.update(user_info)

            self.redis_client.set(key, json.dumps(data))
            # Set expiry to 30 minutes (auto-cleanup for disconnected users)
            self.redis_client.expire(key, 1800)

            # Also add to online users set for quick lookup
            self.redis_client.sadd("online_users", username)

            return True
        except Exception as e:
            print(f"Error adding online user to Redis: {e}")
            return False

    def remove_online_user(self, username):
        """Remove a user from online list"""
        try:
            key = f"online_user:{username}"
            self.redis_client.delete(key)
            self.redis_client.srem("online_users", username)
            return True
        except Exception as e:
            print(f"Error removing online user from Redis: {e}")
            return False

    def is_user_online(self, username):
        """
        Check if a user is currently online
        Also cleans up stale entries where the detail key has expired
        """
        try:
            # Check if user is in the online set
            in_set = self.redis_client.sismember("online_users", username)
            if not in_set:
                return False

            # Verify the detail key exists
            key = f"online_user:{username}"
            exists = self.redis_client.exists(key)

            if not exists:
                # Detail key expired but still in set - clean it up
                print(f"Cleaning up stale user entry: {username}")
                self.redis_client.srem("online_users", username)
                return False

            return True
        except Exception as e:
            print(f"Error checking user online status: {e}")
            return False

    def get_online_usernames(self):
        """
        Get list of all currently online usernames
        Filters out stale entries where detail key has expired
        """
        try:
            usernames = self.redis_client.smembers("online_users")
            valid_usernames = []

            for username in usernames:
                key = f"online_user:{username}"
                if self.redis_client.exists(key):
                    valid_usernames.append(username)
                else:
                    # Clean up stale entry
                    print(f"Cleaning up stale user entry: {username}")
                    self.redis_client.srem("online_users", username)

            return valid_usernames
        except Exception as e:
            print(f"Error getting online usernames: {e}")
            return []

    def get_user_info(self, username):
        """Get online user information"""
        try:
            key = f"online_user:{username}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting user info from Redis: {e}")
            return None

    def get_user_server_id(self, username):
        """Get the server_id (pod) where the user is connected"""
        try:
            user_info = self.get_user_info(username)
            if user_info:
                return user_info.get("server_id")
            return None
        except Exception as e:
            print(f"Error getting user server ID: {e}")
            return None

    def refresh_user_heartbeat(self, username):
        """Refresh the expiry time for an online user (heartbeat)"""
        try:
            key = f"online_user:{username}"
            if self.redis_client.exists(key):
                self.redis_client.expire(key, 1800)  # Extend for another 30 minutes
                return True
            return False
        except Exception as e:
            print(f"Error refreshing user heartbeat: {e}")
            return False

    def publish_message(self, channel, message):
        """
        Publish a message to a Redis pub/sub channel
        Used for inter-pod communication
        """
        try:
            self.redis_client.publish(channel, json.dumps(message))
            return True
        except Exception as e:
            print(f"Error publishing message: {e}")
            return False

    def subscribe_to_channel(self, channel):
        """
        Subscribe to a Redis pub/sub channel
        Returns a pubsub object
        """
        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            print(f"Error subscribing to channel: {e}")
            return None

    def close(self):
        """Close Redis connection"""
        try:
            self.redis_client.close()
            print("Redis connection closed")
        except Exception as e:
            print(f"Error closing Redis connection: {e}")

    # ========== Session Persistence for Reconnection ==========

    def create_session(self, username, user_id):
        """
        Create a persistent session for reconnection
        Returns a unique session token
        """
        try:
            import uuid
            session_token = str(uuid.uuid4())
            session_key = f"session:{session_token}"

            session_data = {
                "username": username,
                "user_id": user_id,
                "created_at": datetime.utcnow().isoformat(),
                "last_active": datetime.utcnow().isoformat()
            }

            # Store session with 1 hour expiry (allows time for reconnection)
            session_ttl = 3600  # 1 hour
            self.redis_client.setex(session_key, session_ttl, json.dumps(session_data))

            # Also store reverse mapping: username -> session_token
            user_session_key = f"user_session:{username}"
            self.redis_client.setex(user_session_key, session_ttl, session_token)

            print(f"Created session {session_token} for user {username}")
            return session_token
        except Exception as e:
            print(f"Error creating session: {e}")
            return None

    def get_session(self, session_token):
        """
        Retrieve session data by token
        Returns session dict or None if expired/not found
        """
        try:
            session_key = f"session:{session_token}"
            data = self.redis_client.get(session_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting session: {e}")
            return None

    def get_session_by_username(self, username):
        """Get active session token for a username"""
        try:
            user_session_key = f"user_session:{username}"
            session_token = self.redis_client.get(user_session_key)
            if session_token:
                return session_token
            return None
        except Exception as e:
            print(f"Error getting session by username: {e}")
            return None

    def update_session_heartbeat(self, session_token):
        """Refresh session expiry time"""
        try:
            session_key = f"session:{session_token}"
            session_ttl = 3600  # 1 hour

            if self.redis_client.exists(session_key):
                # Extend expiry by 1 more hour
                self.redis_client.expire(session_key, session_ttl)

                # Update last_active timestamp
                session_data = self.get_session(session_token)
                if session_data:
                    session_data['last_active'] = datetime.utcnow().isoformat()
                    self.redis_client.setex(session_key, session_ttl, json.dumps(session_data))

                    # Also extend user_session mapping
                    username = session_data.get('username')
                    if username:
                        user_session_key = f"user_session:{username}"
                        self.redis_client.expire(user_session_key, session_ttl)
                return True
            return False
        except Exception as e:
            print(f"Error updating session heartbeat: {e}")
            return False

    def delete_session(self, session_token):
        """Delete a session (on clean logout)"""
        try:
            session_data = self.get_session(session_token)
            if session_data:
                username = session_data.get('username')
                session_key = f"session:{session_token}"
                self.redis_client.delete(session_key)

                # Delete user_session mapping
                if username:
                    user_session_key = f"user_session:{username}"
                    self.redis_client.delete(user_session_key)

                    # Delete pending messages
                    pending_key = f"pending_messages:{username}"
                    self.redis_client.delete(pending_key)

                print(f"Deleted session {session_token} for user {username}")
                return True
            return False
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False

    def save_pending_message(self, username, message):
        """
        Save a message for a disconnected user
        Messages are stored in a list and retrieved on reconnection
        """
        try:
            pending_key = f"pending_messages:{username}"

            message_data = {
                "content": message,
                "timestamp": datetime.utcnow().isoformat()
            }

            # Add to list (right push)
            self.redis_client.rpush(pending_key, json.dumps(message_data))

            # Set expiry to match session TTL (1 hour)
            self.redis_client.expire(pending_key, 3600)

            # Limit to last 100 messages to prevent memory issues
            list_length = self.redis_client.llen(pending_key)
            if list_length > 100:
                # Trim to keep only last 100
                self.redis_client.ltrim(pending_key, -100, -1)

            print(f"Saved pending message for {username}")
            return True
        except Exception as e:
            print(f"Error saving pending message: {e}")
            return False

    def get_pending_messages(self, username, clear=True):
        """
        Retrieve all pending messages for a user
        Args:
            username: Username
            clear: If True, delete messages after retrieval
        Returns:
            List of message dicts
        """
        try:
            pending_key = f"pending_messages:{username}"

            # Get all messages
            messages_json = self.redis_client.lrange(pending_key, 0, -1)

            messages = []
            for msg_json in messages_json:
                try:
                    messages.append(json.loads(msg_json))
                except:
                    pass

            # Clear if requested
            if clear:
                self.redis_client.delete(pending_key)

            if messages:
                print(f"Retrieved {len(messages)} pending messages for {username}")

            return messages
        except Exception as e:
            print(f"Error getting pending messages: {e}")
            return []

    def get_users_per_pod(self):
        """
        Get distribution of users across pods
        Returns dict: {pod_name: user_count}
        """
        try:
            usernames = self.redis_client.smembers("online_users")
            pod_users = {}

            for username in usernames:
                key = f"online_user:{username}"
                data = self.redis_client.get(key)
                if data:
                    user_info = json.loads(data)
                    server_id = user_info.get('server_id', 'unknown')
                    pod_users[server_id] = pod_users.get(server_id, 0) + 1

            return pod_users
        except Exception as e:
            print(f"Error getting users per pod: {e}")
            return {}
