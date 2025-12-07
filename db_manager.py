import psycopg2
from psycopg2 import pool
import hashlib
import os
from datetime import datetime

"""
Database manager for chat application
Handles all database operations: authentication, message storage, chat history
"""

class DatabaseManager:
    def __init__(self, host="localhost", port=5432, database="chatdb", user="chatuser", password="chatpass"):
        """Initialize database connection pool"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 20,  # min and max connections
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
            if self.connection_pool:
                print("Database connection pool created successfully")
        except Exception as e:
            print(f"Error creating connection pool: {e}")
            raise

    def get_connection(self):
        """Get a connection from the pool"""
        return self.connection_pool.getconn()

    def return_connection(self, conn):
        """Return a connection to the pool"""
        self.connection_pool.putconn(conn)

    @staticmethod
    def hash_password(password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password):
        """
        Register a new user
        Returns: (success: bool, message: str)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if username already exists
            cursor.execute("SELECT username FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "Username already exists"

            # Insert new user
            password_hash = self.hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash)
            )
            conn.commit()
            cursor.close()
            return True, "Registration successful"

        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Registration error: {e}"
        finally:
            if conn:
                self.return_connection(conn)

    def authenticate_user(self, username, password):
        """
        Authenticate user credentials
        Returns: (success: bool, user_id: int or None, message: str)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            password_hash = self.hash_password(password)
            cursor.execute(
                "SELECT user_id FROM users WHERE username = %s AND password_hash = %s",
                (username, password_hash)
            )
            result = cursor.fetchone()
            cursor.close()

            if result:
                return True, result[0], "Login successful"
            else:
                return False, None, "Invalid username or password"

        except Exception as e:
            return False, None, f"Authentication error: {e}"
        finally:
            if conn:
                self.return_connection(conn)

    def create_session(self, user_id):
        """Create a new session for logged-in user"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO sessions (user_id) VALUES (%s) RETURNING session_id",
                (user_id,)
            )
            session_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            return session_id

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error creating session: {e}")
            return None
        finally:
            if conn:
                self.return_connection(conn)

    def end_session(self, session_id):
        """End a user session"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE sessions SET logout_time = CURRENT_TIMESTAMP, is_active = FALSE WHERE session_id = %s",
                (session_id,)
            )
            conn.commit()
            cursor.close()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error ending session: {e}")
        finally:
            if conn:
                self.return_connection(conn)

    def get_all_users(self, exclude_user_id=None):
        """
        Get list of all registered users (for contact list)
        Returns: list of (user_id, username, created_at)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            if exclude_user_id:
                cursor.execute(
                    """
                    SELECT user_id, username, created_at
                    FROM users
                    WHERE user_id != %s
                    ORDER BY username
                    """,
                    (exclude_user_id,)
                )
            else:
                cursor.execute(
                    """
                    SELECT user_id, username, created_at
                    FROM users
                    ORDER BY username
                    """
                )

            users = cursor.fetchall()
            cursor.close()
            return users

        except Exception as e:
            print(f"Error retrieving users: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def get_or_create_conversation(self, user1_id, user2_id):
        """
        Get existing conversation or create new one between two users
        Returns: conversation_id or None
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Ensure participant1_id < participant2_id for consistency
            participant1_id = min(user1_id, user2_id)
            participant2_id = max(user1_id, user2_id)

            # Check if conversation exists
            cursor.execute(
                """
                SELECT conversation_id FROM conversations
                WHERE participant1_id = %s AND participant2_id = %s
                """,
                (participant1_id, participant2_id)
            )
            result = cursor.fetchone()

            if result:
                conversation_id = result[0]
            else:
                # Create new conversation
                cursor.execute(
                    """
                    INSERT INTO conversations (participant1_id, participant2_id)
                    VALUES (%s, %s)
                    RETURNING conversation_id
                    """,
                    (participant1_id, participant2_id)
                )
                conversation_id = cursor.fetchone()[0]
                conn.commit()

            cursor.close()
            return conversation_id

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error getting/creating conversation: {e}")
            return None
        finally:
            if conn:
                self.return_connection(conn)

    def save_private_message(self, conversation_id, sender_id, sender_username, message_text):
        """Save a private message to a conversation"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Insert message
            cursor.execute(
                """
                INSERT INTO messages (conversation_id, sender_id, sender_username, message_text)
                VALUES (%s, %s, %s, %s)
                """,
                (conversation_id, sender_id, sender_username, message_text)
            )

            # Update conversation's last_message_at
            cursor.execute(
                """
                UPDATE conversations
                SET last_message_at = CURRENT_TIMESTAMP
                WHERE conversation_id = %s
                """,
                (conversation_id,)
            )

            conn.commit()
            cursor.close()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error saving private message: {e}")
        finally:
            if conn:
                self.return_connection(conn)

    def get_conversation_messages(self, conversation_id, limit=50):
        """
        Retrieve messages from a specific conversation
        Returns: list of (sender_username, message_text, timestamp)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT sender_username, message_text, timestamp
                FROM messages
                WHERE conversation_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (conversation_id, limit)
            )
            messages = cursor.fetchall()
            cursor.close()

            # Reverse to show oldest first
            return list(reversed(messages))

        except Exception as e:
            print(f"Error retrieving conversation messages: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def get_user_conversations(self, user_id):
        """
        Get all conversations for a user with last message info
        Returns: list of (conversation_id, other_user_id, other_username, last_message_at)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    c.conversation_id,
                    CASE
                        WHEN c.participant1_id = %s THEN c.participant2_id
                        ELSE c.participant1_id
                    END as other_user_id,
                    CASE
                        WHEN c.participant1_id = %s THEN u2.username
                        ELSE u1.username
                    END as other_username,
                    c.last_message_at
                FROM conversations c
                JOIN users u1 ON c.participant1_id = u1.user_id
                JOIN users u2 ON c.participant2_id = u2.user_id
                WHERE c.participant1_id = %s OR c.participant2_id = %s
                ORDER BY c.last_message_at DESC
                """,
                (user_id, user_id, user_id, user_id)
            )

            conversations = cursor.fetchall()
            cursor.close()
            return conversations

        except Exception as e:
            print(f"Error retrieving user conversations: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def save_broadcast_message(self, sender_id, sender_username, message_text):
        """Save a broadcast message"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Insert broadcast message
            cursor.execute(
                """
                INSERT INTO broadcast_messages (sender_id, sender_username, message_text)
                VALUES (%s, %s, %s)
                """,
                (sender_id, sender_username, message_text)
            )

            conn.commit()
            cursor.close()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error saving broadcast message: {e}")
        finally:
            if conn:
                self.return_connection(conn)

    def get_broadcast_messages(self, limit=50):
        """
        Retrieve recent broadcast messages
        Returns: list of (sender_username, message_text, timestamp)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT sender_username, message_text, timestamp
                FROM broadcast_messages
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,)
            )
            messages = cursor.fetchall()
            cursor.close()

            # Reverse to show oldest first
            return list(reversed(messages))

        except Exception as e:
            print(f"Error retrieving broadcast messages: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def create_group(self, group_name, creator_id, description=None):
        """
        Create a new group
        Returns: (success: bool, group_id: int or None, message: str)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if group name already exists
            cursor.execute("SELECT group_id FROM groups WHERE group_name = %s AND is_active = TRUE", (group_name,))
            if cursor.fetchone():
                cursor.close()
                return False, None, "Group name already exists"

            # Create group
            cursor.execute(
                """
                INSERT INTO groups (group_name, creator_id, description)
                VALUES (%s, %s, %s)
                RETURNING group_id
                """,
                (group_name, creator_id, description)
            )
            group_id = cursor.fetchone()[0]

            # Add creator as admin member
            cursor.execute(
                """
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (%s, %s, 'admin')
                """,
                (group_id, creator_id)
            )

            conn.commit()
            cursor.close()
            return True, group_id, "Group created successfully"

        except Exception as e:
            if conn:
                conn.rollback()
            return False, None, f"Error creating group: {e}"
        finally:
            if conn:
                self.return_connection(conn)

    def get_user_groups(self, user_id):
        """
        Get all groups that a user is a member of
        Returns: list of (group_id, group_name, description, role, member_count)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    g.group_id,
                    g.group_name,
                    g.description,
                    gm.role,
                    (SELECT COUNT(*) FROM group_members WHERE group_id = g.group_id) as member_count
                FROM groups g
                JOIN group_members gm ON g.group_id = gm.group_id
                WHERE gm.user_id = %s AND g.is_active = TRUE
                ORDER BY g.created_at DESC
                """,
                (user_id,)
            )

            groups = cursor.fetchall()
            cursor.close()
            return groups

        except Exception as e:
            print(f"Error retrieving user groups: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def get_all_groups(self):
        """
        Get all active groups with member counts
        Returns: list of (group_id, group_name, description, member_count)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    g.group_id,
                    g.group_name,
                    g.description,
                    (SELECT COUNT(*) FROM group_members WHERE group_id = g.group_id) as member_count
                FROM groups g
                WHERE g.is_active = TRUE
                ORDER BY g.created_at DESC
                """
            )

            groups = cursor.fetchall()
            cursor.close()
            return groups

        except Exception as e:
            print(f"Error retrieving all groups: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def join_group(self, group_id, user_id):
        """
        Add a user to a group
        Returns: (success: bool, message: str)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if user is already a member
            cursor.execute(
                "SELECT membership_id FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )
            if cursor.fetchone():
                cursor.close()
                return False, "You are already a member of this group"

            # Check if group exists and is active
            cursor.execute(
                "SELECT group_id FROM groups WHERE group_id = %s AND is_active = TRUE",
                (group_id,)
            )
            if not cursor.fetchone():
                cursor.close()
                return False, "Group not found or inactive"

            # Add user to group
            cursor.execute(
                """
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (%s, %s, 'member')
                """,
                (group_id, user_id)
            )

            conn.commit()
            cursor.close()
            return True, "Successfully joined group"

        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Error joining group: {e}"
        finally:
            if conn:
                self.return_connection(conn)

    def leave_group(self, group_id, user_id):
        """
        Remove a user from a group
        Returns: (success: bool, message: str)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Check if user is a member
            cursor.execute(
                "SELECT role FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )
            result = cursor.fetchone()
            if not result:
                cursor.close()
                return False, "You are not a member of this group"

            # Remove user from group
            cursor.execute(
                "DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )

            # Check if group is now empty, deactivate if so
            cursor.execute(
                "SELECT COUNT(*) FROM group_members WHERE group_id = %s",
                (group_id,)
            )
            member_count = cursor.fetchone()[0]
            
            if member_count == 0:
                cursor.execute(
                    "UPDATE groups SET is_active = FALSE WHERE group_id = %s",
                    (group_id,)
                )

            conn.commit()
            cursor.close()
            return True, "Successfully left group"

        except Exception as e:
            if conn:
                conn.rollback()
            return False, f"Error leaving group: {e}"
        finally:
            if conn:
                self.return_connection(conn)

    def get_group_members(self, group_id):
        """
        Get all members of a group
        Returns: list of (user_id, username, role, joined_at)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    u.user_id,
                    u.username,
                    gm.role,
                    gm.joined_at
                FROM group_members gm
                JOIN users u ON gm.user_id = u.user_id
                WHERE gm.group_id = %s
                ORDER BY gm.joined_at
                """,
                (group_id,)
            )

            members = cursor.fetchall()
            cursor.close()
            return members

        except Exception as e:
            print(f"Error retrieving group members: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def is_group_member(self, group_id, user_id):
        """
        Check if a user is a member of a group
        Returns: bool
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT membership_id FROM group_members WHERE group_id = %s AND user_id = %s",
                (group_id, user_id)
            )
            result = cursor.fetchone()
            cursor.close()
            return result is not None

        except Exception as e:
            print(f"Error checking group membership: {e}")
            return False
        finally:
            if conn:
                self.return_connection(conn)

    def save_group_message(self, group_id, sender_id, sender_username, message_text):
        """Save a message to a group"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO group_messages (group_id, sender_id, sender_username, message_text)
                VALUES (%s, %s, %s, %s)
                """,
                (group_id, sender_id, sender_username, message_text)
            )

            conn.commit()
            cursor.close()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error saving group message: {e}")
        finally:
            if conn:
                self.return_connection(conn)

    def get_group_messages(self, group_id, limit=50):
        """
        Retrieve recent messages from a group
        Returns: list of (sender_username, message_text, timestamp)
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT sender_username, message_text, timestamp
                FROM group_messages
                WHERE group_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (group_id, limit)
            )
            messages = cursor.fetchall()
            cursor.close()

            # Reverse to show oldest first
            return list(reversed(messages))

        except Exception as e:
            print(f"Error retrieving group messages: {e}")
            return []
        finally:
            if conn:
                self.return_connection(conn)

    def get_group_info(self, group_id):
        """
        Get information about a group
        Returns: (group_name, description, creator_id, created_at) or None
        """
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT group_name, description, creator_id, created_at
                FROM groups
                WHERE group_id = %s AND is_active = TRUE
                """,
                (group_id,)
            )
            result = cursor.fetchone()
            cursor.close()
            return result

        except Exception as e:
            print(f"Error retrieving group info: {e}")
            return None
        finally:
            if conn:
                self.return_connection(conn)

    def close_all_connections(self):
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("All database connections closed")
