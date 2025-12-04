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
