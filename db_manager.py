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

    def close_all_connections(self):
        """Close all connections in the pool"""
        if self.connection_pool:
            self.connection_pool.closeall()
            print("All database connections closed")
