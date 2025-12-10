"""
Group Chat Manager - Handles all group chat operations
Supports multi-pod distributed group messaging via Redis pub/sub
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class GroupChatManager:
    def __init__(self, db_manager, redis_manager):
        """
        Initialize group chat manager
        
        Args:
            db_manager: DatabaseManager instance for persistence
            redis_manager: RedisManager instance for distributed state
        """
        self.db_manager = db_manager
        self.redis_manager = redis_manager
    
    # ============== GROUP CREATION & MANAGEMENT ==============
    
    def create_group(self, group_name: str, creator_user_id: int, description: str = "") -> Tuple[bool, str, Optional[int]]:
        """
        Create a new group chat
        
        Returns:
            (success: bool, message: str, group_id: Optional[int])
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Create the group
            cursor.execute("""
                INSERT INTO groups (group_name, description, created_by_user_id, created_at, last_message_at)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING group_id
            """, (group_name, description, creator_user_id))
            
            group_id = cursor.fetchone()[0]
            
            # Add creator as admin member
            cursor.execute("""
                INSERT INTO group_members (group_id, user_id, role, joined_at, is_active)
                VALUES (%s, %s, 'admin', NOW(), TRUE)
            """, (group_id, creator_user_id))
            
            # Add system message
            cursor.execute("""
                SELECT username FROM users WHERE user_id = %s
            """, (creator_user_id,))
            creator_username = cursor.fetchone()[0]
            
            cursor.execute("""
                INSERT INTO messages (group_id, sender_id, sender_username, message_text, message_type)
                VALUES (%s, %s, 'System', %s, 'system')
            """, (group_id, creator_user_id, f"Group '{group_name}' created by {creator_username}"))
            
            conn.commit()
            self.db_manager.return_connection(conn)
            
            # Publish group creation event to Redis
            self.redis_manager.publish_message("group_events", {
                'event_type': 'group_created',
                'group_id': group_id,
                'group_name': group_name,
                'creator_user_id': creator_user_id
            })
            
            return True, f"Group '{group_name}' created successfully", group_id
            
        except Exception as e:
            if conn:
                conn.rollback()
                self.db_manager.return_connection(conn)
            return False, f"Failed to create group: {str(e)}", None
    
    def add_member_to_group(self, group_id: int, user_id: int, added_by_user_id: int, role: str = 'member') -> Tuple[bool, str]:
        """
        Add a user to a group
        
        Returns:
            (success: bool, message: str)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Check if user is already a member
            cursor.execute("""
                SELECT membership_id FROM group_members 
                WHERE group_id = %s AND user_id = %s AND is_active = TRUE
            """, (group_id, user_id))
            
            if cursor.fetchone():
                self.db_manager.return_connection(conn)
                return False, "User is already a member of this group"
            
            # Add member
            cursor.execute("""
                INSERT INTO group_members (group_id, user_id, role, joined_at, is_active)
                VALUES (%s, %s, %s, NOW(), TRUE)
                ON CONFLICT (group_id, user_id) 
                DO UPDATE SET is_active = TRUE, joined_at = NOW(), role = EXCLUDED.role
            """, (group_id, user_id, role))
            
            # Get usernames for system message
            cursor.execute("""
                SELECT u1.username, u2.username, g.group_name
                FROM users u1, users u2, groups g
                WHERE u1.user_id = %s AND u2.user_id = %s AND g.group_id = %s
            """, (user_id, added_by_user_id, group_id))
            
            added_username, adder_username, group_name = cursor.fetchone()
            
            # Add system message
            cursor.execute("""
                INSERT INTO messages (group_id, sender_id, sender_username, message_text, message_type)
                VALUES (%s, %s, 'System', %s, 'system')
            """, (group_id, added_by_user_id, f"{added_username} was added to the group by {adder_username}"))
            
            conn.commit()
            self.db_manager.return_connection(conn)
            
            # Publish member added event to Redis
            self.redis_manager.publish_message("group_events", {
                'event_type': 'member_added',
                'group_id': group_id,
                'user_id': user_id,
                'added_by': added_by_user_id
            })
            
            return True, f"User added to group successfully"
            
        except Exception as e:
            if conn:
                conn.rollback()
                self.db_manager.return_connection(conn)
            return False, f"Failed to add member: {str(e)}"
    
    def remove_member_from_group(self, group_id: int, user_id: int, removed_by_user_id: int) -> Tuple[bool, str]:
        """
        Remove a user from a group (soft delete)
        
        Returns:
            (success: bool, message: str)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Check if user is a member
            cursor.execute("""
                SELECT role FROM group_members 
                WHERE group_id = %s AND user_id = %s AND is_active = TRUE
            """, (group_id, user_id))
            
            result = cursor.fetchone()
            if not result:
                self.db_manager.return_connection(conn)
                return False, "User is not a member of this group"
            
            # Soft delete membership
            cursor.execute("""
                UPDATE group_members 
                SET is_active = FALSE 
                WHERE group_id = %s AND user_id = %s
            """, (group_id, user_id))
            
            # Get usernames for system message
            cursor.execute("""
                SELECT u1.username, u2.username
                FROM users u1, users u2
                WHERE u1.user_id = %s AND u2.user_id = %s
            """, (user_id, removed_by_user_id))
            
            removed_username, remover_username = cursor.fetchone()
            
            # Add system message
            if user_id == removed_by_user_id:
                message = f"{removed_username} left the group"
            else:
                message = f"{removed_username} was removed from the group by {remover_username}"
            
            cursor.execute("""
                INSERT INTO messages (group_id, sender_id, sender_username, message_text, message_type)
                VALUES (%s, %s, 'System', %s, 'system')
            """, (group_id, removed_by_user_id, message))
            
            conn.commit()
            self.db_manager.return_connection(conn)
            
            # Publish member removed event to Redis
            self.redis_manager.publish_message("group_events", {
                'event_type': 'member_removed',
                'group_id': group_id,
                'user_id': user_id,
                'removed_by': removed_by_user_id
            })
            
            return True, "Member removed successfully"
            
        except Exception as e:
            if conn:
                conn.rollback()
                self.db_manager.return_connection(conn)
            return False, f"Failed to remove member: {str(e)}"
    
    # ============== GROUP MESSAGING ==============
    
    def send_group_message(self, group_id: int, sender_id: int, sender_username: str, message_text: str) -> Tuple[bool, Optional[int]]:
        """
        Send a message to a group
        
        Returns:
            (success: bool, message_id: Optional[int])
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            # Verify sender is a member
            cursor.execute("""
                SELECT membership_id FROM group_members 
                WHERE group_id = %s AND user_id = %s AND is_active = TRUE
            """, (group_id, sender_id))
            
            if not cursor.fetchone():
                self.db_manager.return_connection(conn)
                return False, None
            
            # Insert message
            cursor.execute("""
                INSERT INTO messages (group_id, sender_id, sender_username, message_text, timestamp)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING message_id
            """, (group_id, sender_id, sender_username, message_text))
            
            message_id = cursor.fetchone()[0]
            
            # Update group's last_message_at
            cursor.execute("""
                UPDATE groups 
                SET last_message_at = NOW() 
                WHERE group_id = %s
            """, (group_id,))
            
            conn.commit()
            self.db_manager.return_connection(conn)

            # 🔥 PUBLISH GROUP MESSAGE EVENT
            self.redis_manager.publish_message("group_messages", {
                'event_type': 'group_message',
                'group_id': group_id,
                'message_id': message_id,
                'sender_id': sender_id,
                'sender_username': sender_username,
                'message_text': message_text,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return True, message_id
            
        except Exception as e:
            if conn:
                conn.rollback()
                self.db_manager.return_connection(conn)
            print(f"Error sending group message: {e}")
            return False, None
    
    def mark_group_message_read(self, message_id: int, user_id: int) -> bool:
        """
        Mark a group message as read by a user
        
        Returns:
            success: bool
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO group_message_reads (message_id, user_id, read_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (message_id, user_id) DO NOTHING
            """, (message_id, user_id))
            
            conn.commit()
            self.db_manager.return_connection(conn)
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
                self.db_manager.return_connection(conn)
            print(f"Error marking message as read: {e}")
            return False
    
    def mark_group_messages_read(self, group_id: int, user_id: int) -> bool:
        """
        Mark all unread messages in a group as read for a user
        (Called when user enters group chat)
        
        Returns:
            success: bool
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO group_message_reads (message_id, user_id, read_at)
                SELECT m.message_id, %s, NOW()
                FROM messages m
                WHERE m.group_id = %s 
                  AND m.sender_id != %s
                  AND NOT EXISTS (
                      SELECT 1 FROM group_message_reads 
                      WHERE message_id = m.message_id AND user_id = %s
                  )
            """, (user_id, group_id, user_id, user_id))
            
            conn.commit()
            rows_affected = cursor.rowcount
            self.db_manager.return_connection(conn)
            
            if rows_affected > 0:
                print(f"Marked {rows_affected} messages as read for user {user_id} in group {group_id}")
            
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
                self.db_manager.return_connection(conn)
            print(f"Error marking group messages as read: {e}")
            return False
    
    # ============== GROUP QUERIES ==============
    
    def get_all_groups(self) -> List[Tuple]:
        """
        Get all active groups (for group list display)
        
        Returns:
            List of (group_id, group_name, description, member_count, created_by_user_id)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    g.group_id,
                    g.group_name,
                    g.description,
                    (SELECT COUNT(*) FROM group_members 
                     WHERE group_id = g.group_id AND is_active = TRUE) as member_count,
                    g.created_by_user_id
                FROM groups g
                WHERE g.is_active = TRUE
                ORDER BY g.last_message_at DESC
            """)
            
            groups = cursor.fetchall()
            self.db_manager.return_connection(conn)
            return groups
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error getting all groups: {e}")
            return []
    
    def get_user_groups(self, user_id: int) -> List[Tuple]:
        """
        Get all groups that a user is a member of
        
        Returns:
            List of (group_id, group_name, description, role, member_count, unread_count, last_message_at)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    g.group_id,
                    g.group_name,
                    g.description,
                    gm.role,
                    (SELECT COUNT(*) FROM group_members WHERE group_id = g.group_id AND is_active = TRUE) as member_count,
                    COALESCE(
                        (SELECT COUNT(*) 
                         FROM messages m
                         LEFT JOIN group_message_reads gmr ON m.message_id = gmr.message_id AND gmr.user_id = %s
                         WHERE m.group_id = g.group_id 
                           AND m.sender_id != %s
                           AND gmr.read_id IS NULL), 
                        0
                    ) as unread_count,
                    g.last_message_at
                FROM groups g
                JOIN group_members gm ON g.group_id = gm.group_id
                WHERE gm.user_id = %s 
                  AND gm.is_active = TRUE 
                  AND g.is_active = TRUE
                ORDER BY g.last_message_at DESC
            """, (user_id, user_id, user_id))
            
            groups = cursor.fetchall()
            self.db_manager.return_connection(conn)
            return groups
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error getting user groups: {e}")
            return []
    
    def get_group_members(self, group_id: int) -> List[Tuple]:
        """
        Get all members of a group
        
        Returns:
            List of (user_id, username, role, joined_at, is_active)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT u.user_id, u.username, gm.role, gm.joined_at, gm.is_active
                FROM users u
                JOIN group_members gm ON u.user_id = gm.user_id
                WHERE gm.group_id = %s AND gm.is_active = TRUE
                ORDER BY gm.role DESC, u.username ASC
            """, (group_id,))
            
            members = cursor.fetchall()
            self.db_manager.return_connection(conn)
            return members
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error getting group members: {e}")
            return []
    
    def get_group_messages(self, group_id: int, limit: int = 50) -> List[Tuple]:
        """
        Get recent messages from a group
        
        Returns:
            List of (message_id, sender_username, message_text, timestamp, message_type)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT message_id, sender_username, message_text, timestamp, message_type
                FROM messages
                WHERE group_id = %s
                ORDER BY timestamp DESC
                LIMIT %s
            """, (group_id, limit))
            
            messages = cursor.fetchall()
            self.db_manager.return_connection(conn)
            # Return in chronological order (oldest first)
            return list(reversed(messages))
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error getting group messages: {e}")
            return []
    
    def search_groups(self, search_term: str) -> List[Tuple]:
        """
        Search for groups by name
        
        Returns:
            List of (group_id, group_name, description, member_count)
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    g.group_id,
                    g.group_name,
                    g.description,
                    (SELECT COUNT(*) FROM group_members WHERE group_id = g.group_id AND is_active = TRUE) as member_count
                FROM groups g
                WHERE g.is_active = TRUE 
                  AND (g.group_name ILIKE %s OR g.description ILIKE %s)
                ORDER BY g.last_message_at DESC
                LIMIT 20
            """, (f'%{search_term}%', f'%{search_term}%'))
            
            groups = cursor.fetchall()
            self.db_manager.return_connection(conn)
            return groups
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error searching groups: {e}")
            return []
    
    def is_user_in_group(self, user_id: int, group_id: int) -> bool:
        """
        Check if a user is a member of a group
        
        Returns:
            bool: True if user is active member
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT membership_id FROM group_members 
                WHERE user_id = %s AND group_id = %s AND is_active = TRUE
            """, (user_id, group_id))
            
            result = cursor.fetchone() is not None
            self.db_manager.return_connection(conn)
            return result
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error checking group membership: {e}")
            return False
    
    def get_group_info(self, group_id: int) -> Optional[Tuple]:
        """
        Get information about a specific group
        
        Returns:
            (group_id, group_name, description, created_by_user_id, created_at, last_message_at) or None
        """
        conn = None
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    g.group_id,
                    g.group_name,
                    g.description,
                    g.created_by_user_id,
                    g.created_at,
                    g.last_message_at
                FROM groups g
                WHERE g.group_id = %s AND g.is_active = TRUE
            """, (group_id,))
            
            info = cursor.fetchone()
            self.db_manager.return_connection(conn)
            return info
            
        except Exception as e:
            if conn:
                self.db_manager.return_connection(conn)
            print(f"Error getting group info: {e}")
            return None
