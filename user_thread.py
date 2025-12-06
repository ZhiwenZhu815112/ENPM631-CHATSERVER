import threading
import socket

"""
This thread handles connection for each connected client, so the server
can handle multiple clients at the same time.

@author www.codejava.net (Java version)
Python port with authentication, message storage, and group chat
"""

class UserThread(threading.Thread):
    def __init__(self, client_socket, server):
        super().__init__()
        self.socket = client_socket
        self.server = server
        self.writer = None
        self.db_manager = server.get_db_manager()
        self.user_id = None
        self.session_id = None

    def run(self):
        try:
            input_stream = self.socket.makefile('r', encoding='utf-8')
            output_stream = self.socket.makefile('w', encoding='utf-8')
            self.writer = output_stream

            # Authentication phase
            user_name = self.authenticate_user(input_stream)
            if not user_name:
                self.socket.close()
                return

            # Add user to online users
            self.server.add_online_user(user_name, self)

            # Main menu and navigation loop
            while True:
                # Display main menu
                self.send_main_menu()

                # Wait for menu selection
                menu_choice = input_stream.readline().strip()

                # Handle menu options
                if menu_choice == "1":
                    # Private Messages
                    self.handle_private_messages(input_stream, user_name)
                elif menu_choice == "2":
                    # Broadcast Channel
                    self.handle_broadcast_chat(input_stream, user_name)
                elif menu_choice == "3":
                    # My Groups
                    self.handle_my_groups(input_stream, user_name)
                elif menu_choice == "4":
                    # Browse All Groups
                    self.handle_browse_groups(input_stream, user_name)
                elif menu_choice == "5":
                    # Create New Group
                    self.handle_create_group(input_stream, user_name)
                elif menu_choice == "bye":
                    break
                elif not menu_choice:
                    continue
                else:
                    self.writer.write("INVALID_OPTION:Invalid menu option\n")
                    self.writer.flush()

            # Cleanup
            if self.session_id:
                self.db_manager.end_session(self.session_id)
            self.server.remove_user(user_name, self)
            self.socket.close()

        except IOError as ex:
            print(f"Error in UserThread: {ex}")
            import traceback
            traceback.print_exc()

    def authenticate_user(self, input_stream):
        """
        Handle user authentication (login or signup)
        Returns username if successful, None otherwise
        """
        try:
            # Send AUTH_REQUEST once - client handles retry locally
            self.writer.write("AUTH_REQUEST\n")
            self.writer.flush()

            # Keep handling auth attempts until successful
            while True:
                auth_choice = input_stream.readline().strip()

                if not auth_choice:
                    return None

                if auth_choice == "LOGIN":
                    result = self.handle_login(input_stream)
                    if result:
                        return result
                    # If login fails, client will send SIGNUP next
                elif auth_choice == "SIGNUP":
                    result = self.handle_signup(input_stream)
                    if result:
                        return result
                    # If signup fails, client will retry
                else:
                    self.writer.write("AUTH_FAILED:Invalid choice\n")
                    self.writer.flush()

        except Exception as e:
            print(f"Authentication error: {e}")
            return None

    def handle_login(self, input_stream):
        """Handle user login"""
        self.writer.write("LOGIN_PROMPT\n")
        self.writer.flush()

        username = input_stream.readline().strip()
        password = input_stream.readline().strip()

        success, user_id, message = self.db_manager.authenticate_user(username, password)

        if success:
            self.user_id = user_id
            self.session_id = self.db_manager.create_session(user_id)
            self.writer.write(f"AUTH_SUCCESS:{message}\n")
            self.writer.flush()
            print(f"User {username} logged in successfully")
            return username
        else:
            self.writer.write(f"AUTH_FAILED:{message}\n")
            self.writer.flush()
            return None

    def handle_signup(self, input_stream):
        """Handle user registration"""
        self.writer.write("SIGNUP_PROMPT\n")
        self.writer.flush()

        username = input_stream.readline().strip()
        password = input_stream.readline().strip()

        success, message = self.db_manager.register_user(username, password)

        if success:
            # Auto-login after successful registration
            _, user_id, _ = self.db_manager.authenticate_user(username, password)
            self.user_id = user_id
            self.session_id = self.db_manager.create_session(user_id)
            self.writer.write(f"AUTH_SUCCESS:Registration successful. Welcome {username}!\n")
            self.writer.flush()
            print(f"New user {username} registered and logged in")
            return username
        else:
            self.writer.write(f"AUTH_FAILED:{message}\n")
            self.writer.flush()
            return None

    def send_main_menu(self):
        """Send the main menu to the client"""
        self.writer.write("MAIN_MENU_START\n")
        self.writer.flush()
        
        # Menu header
        menu = """
========================================
        CHAT APPLICATION MENU
========================================
1. 💬 Private Messages
2. 📢 Broadcast Channel
3. 👥 My Groups
4. 🔍 Browse All Groups
5. ➕ Create New Group

Type 'bye' to logout
========================================
"""
        self.writer.write(menu)
        self.writer.write("MAIN_MENU_END\n")
        self.writer.flush()

    def handle_private_messages(self, input_stream, user_name):
        """Handle the private messaging flow (existing functionality)"""
        while True:
            # Send contact list
            contact_list = self.send_contact_list()

            # Wait for contact selection
            selected_contact = input_stream.readline().strip()

            # Handle special commands
            if selected_contact == "back" or not selected_contact:
                return  # Return to main menu
            elif selected_contact == "BROADCAST":
                # Redirect to broadcast
                self.handle_broadcast_chat(input_stream, user_name)
                return

            # Get user_id of selected contact
            recipient_id = None
            for uid, uname, _ in self.db_manager.get_all_users():
                if uname == selected_contact:
                    recipient_id = uid
                    break

            if not recipient_id:
                self.writer.write("CONTACT_NOT_FOUND:Contact not found\n")
                self.writer.flush()
                continue

            # Get or create conversation
            conversation_id = self.db_manager.get_or_create_conversation(self.user_id, recipient_id)
            if not conversation_id:
                self.writer.write("CONVERSATION_ERROR:Could not create conversation\n")
                self.writer.flush()
                continue

            # Send conversation history
            self.send_conversation_history(conversation_id, selected_contact)

            # Enter messaging mode
            self.chat_with_contact(input_stream, user_name, selected_contact, conversation_id)

    def send_contact_list(self):
        """
        Send list of all users (contacts) and broadcast option to the client
        Returns list of usernames (excluding current user)
        """
        all_users = self.db_manager.get_all_users(exclude_user_id=self.user_id)

        # Send contact list
        self.writer.write("CONTACT_LIST_START\n")
        self.writer.flush()

        # Always include BROADCAST option as the first item
        self.writer.write("BROADCAST|broadcast\n")
        self.writer.flush()

        contact_usernames = ["BROADCAST"]
        
        if all_users:
            online_usernames = self.server.get_online_usernames()

            for user_id, username, created_at in all_users:
                is_online = username in online_usernames
                status = "online" if is_online else "offline"
                self.writer.write(f"{username}|{status}\n")
                self.writer.flush()
                contact_usernames.append(username)

        self.writer.write("CONTACT_LIST_END\n")
        self.writer.flush()

        return contact_usernames

    def send_conversation_history(self, conversation_id, contact_name):
        """Send conversation history between current user and selected contact"""
        messages = self.db_manager.get_conversation_messages(conversation_id, limit=50)

        self.writer.write(f"CONVERSATION_START:{contact_name}\n")
        self.writer.flush()

        if messages:
            for sender_username, message_text, timestamp in messages:
                formatted_msg = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {sender_username}: {message_text}"
                self.writer.write(f"{formatted_msg}\n")
                self.writer.flush()

        self.writer.write("CONVERSATION_READY\n")
        self.writer.flush()

    def handle_broadcast_chat(self, input_stream, user_name):
        """
        Handle broadcast messaging mode
        """
        # Send broadcast history
        self.send_broadcast_history()

        while True:
            client_message = input_stream.readline().strip()

            # Check for exit command to return to contact list
            if not client_message or client_message == "back":
                return

            # Save broadcast message to database
            self.db_manager.save_broadcast_message(self.user_id, user_name, client_message)
            import time 
            timestamp = int(time.time()*1000)
            # Send broadcast message to all online users except sender
            online_users = self.server.get_online_usernames()
            delivered_count = 0
            
            for recipient in online_users:
                if recipient != user_name:  # Don't send to self
                    if self.server.send_to_user(recipient, f"BROADCAST:{user_name}:{client_message}:{timestamp}"):
                        delivered_count += 1

            # Confirm to sender
            total_users = len(online_users) - 1  # Exclude sender
            self.writer.write(f"BROADCAST_SENT:Broadcast sent to {delivered_count} online users (of {total_users} total)\n")
            self.writer.flush()

    def send_broadcast_history(self):
        """Send recent broadcast message history"""
        messages = self.db_manager.get_broadcast_messages(limit=50)

        self.writer.write("BROADCAST_START:BROADCAST CHANNEL\n")
        self.writer.flush()

        if messages:
            for sender_username, message_text, timestamp in messages:
                formatted_msg = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {sender_username}: {message_text}"
                self.writer.write(f"{formatted_msg}\n")
                self.writer.flush()

        self.writer.write("CONVERSATION_READY\n")
        self.writer.flush()

    def chat_with_contact(self, input_stream, user_name, contact_name, conversation_id):
        """
        Handle messaging between current user and selected contact
        """
        while True:
            client_message = input_stream.readline().strip()

            # Check for exit command to return to contact list
            # Note: "bye" is treated as a regular message here (user can say "bye" to their friend)
            # To logout, user should type "back" then "bye" at contact selection
            if not client_message or client_message == "back":
                # Return to contact selection
                return

            # Save message to database
            self.db_manager.save_private_message(conversation_id, self.user_id, user_name, client_message)

            # Try to send message to recipient if they're online
            message_delivered = self.server.send_to_user(
                contact_name,
                f"MESSAGE:{user_name}:{client_message}"
            )

            # Confirm to sender
            if message_delivered:
                self.writer.write(f"SENT:Message delivered\n")
            else:
                self.writer.write(f"SENT:Message saved (recipient offline)\n")
            self.writer.flush()

    # ========== GROUP CHAT METHODS ==========

    def handle_my_groups(self, input_stream, user_name):
        """Display and handle user's groups"""
        while True:
            # Get user's groups
            groups = self.db_manager.get_user_groups(self.user_id)

            self.writer.write("MY_GROUPS_START\n")
            self.writer.flush()

            if not groups:
                self.writer.write("NO_GROUPS:You are not a member of any groups yet.\n")
                self.writer.flush()
                self.writer.write("MY_GROUPS_END\n")
                self.writer.flush()
                
                # Wait for user to press enter to go back
                input_stream.readline()
                return

            # Display groups
            for group_id, group_name, description, role, member_count in groups:
                role_badge = "👑" if role == "admin" else "👤"
                desc_text = description if description else "No description"
                self.writer.write(f"{group_id}|{group_name}|{desc_text}|{member_count}|{role_badge}\n")
                self.writer.flush()

            self.writer.write("MY_GROUPS_END\n")
            self.writer.flush()

            # Wait for group selection
            selection = input_stream.readline().strip()

            if selection == "back" or not selection:
                return  # Return to main menu

            # Try to parse as group ID
            try:
                group_id = int(selection)
                
                # Verify user is a member
                if not self.db_manager.is_group_member(group_id, self.user_id):
                    self.writer.write("NOT_MEMBER:You are not a member of this group\n")
                    self.writer.flush()
                    continue

                # Enter group chat
                self.handle_group_chat(input_stream, user_name, group_id)
                
            except ValueError:
                self.writer.write("INVALID_SELECTION:Please enter a valid group ID\n")
                self.writer.flush()

    def handle_browse_groups(self, input_stream, user_name):
        """Display all available groups and allow joining"""
        while True:
            # Get all groups
            all_groups = self.db_manager.get_all_groups()
            user_groups = [g[0] for g in self.db_manager.get_user_groups(self.user_id)]

            self.writer.write("BROWSE_GROUPS_START\n")
            self.writer.flush()

            if not all_groups:
                self.writer.write("NO_GROUPS:No groups available yet. Create one!\n")
                self.writer.flush()
                self.writer.write("BROWSE_GROUPS_END\n")
                self.writer.flush()
                
                # Wait for user to press enter to go back
                input_stream.readline()
                return

            # Display groups
            for group_id, group_name, description, member_count in all_groups:
                is_member = group_id in user_groups
                status = "✅ Member" if is_member else "Join"
                desc_text = description if description else "No description"
                self.writer.write(f"{group_id}|{group_name}|{desc_text}|{member_count}|{status}\n")
                self.writer.flush()

            self.writer.write("BROWSE_GROUPS_END\n")
            self.writer.flush()

            # Wait for selection (join or view)
            selection = input_stream.readline().strip()

            if selection == "back" or not selection:
                return  # Return to main menu

            # Parse command: "join:GROUP_ID" or just "GROUP_ID" to view
            if selection.startswith("join:"):
                try:
                    group_id = int(selection.split(":")[1])
                    success, message = self.db_manager.join_group(group_id, self.user_id)
                    
                    if success:
                        self.writer.write(f"JOIN_SUCCESS:{message}\n")
                    else:
                        self.writer.write(f"JOIN_FAILED:{message}\n")
                    self.writer.flush()
                    
                except (ValueError, IndexError):
                    self.writer.write("INVALID_COMMAND:Invalid join command\n")
                    self.writer.flush()
            else:
                # Try to view/enter group
                try:
                    group_id = int(selection)
                    
                    # Check if user is a member
                    if self.db_manager.is_group_member(group_id, self.user_id):
                        self.handle_group_chat(input_stream, user_name, group_id)
                    else:
                        self.writer.write("NOT_MEMBER:You must join this group first. Use 'join:GROUP_ID'\n")
                        self.writer.flush()
                        
                except ValueError:
                    self.writer.write("INVALID_SELECTION:Please enter a valid group ID\n")
                    self.writer.flush()

    def handle_create_group(self, input_stream, user_name):
        """Handle group creation"""
        self.writer.write("CREATE_GROUP_PROMPT\n")
        self.writer.flush()

        # Get group name
        group_name = input_stream.readline().strip()
        
        if not group_name or group_name == "back":
            return  # Return to main menu

        # Get description
        description = input_stream.readline().strip()
        if description == "back":
            return

        # Create group
        success, group_id, message = self.db_manager.create_group(
            group_name, 
            self.user_id, 
            description if description else None
        )

        if success:
            self.writer.write(f"CREATE_SUCCESS:{message}|{group_id}\n")
            self.writer.flush()
            
            # Ask if user wants to enter the group
            enter_choice = input_stream.readline().strip()
            if enter_choice.lower() == "yes":
                self.handle_group_chat(input_stream, user_name, group_id)
        else:
            self.writer.write(f"CREATE_FAILED:{message}\n")
            self.writer.flush()

    def handle_group_chat(self, input_stream, user_name, group_id):
        """
        Handle group chat messaging
        """
        # Get group info
        group_info = self.db_manager.get_group_info(group_id)
        if not group_info:
            self.writer.write("GROUP_NOT_FOUND:Group not found\n")
            self.writer.flush()
            return

        group_name = group_info[0]

        # Send group chat history
        self.send_group_history(group_id, group_name)

        # Get group members for message broadcasting
        members = self.db_manager.get_group_members(group_id)
        member_usernames = [m[1] for m in members]

        while True:
            client_message = input_stream.readline().strip()

            # Commands
            if not client_message:
                continue
            elif client_message == "back":
                return  # Return to previous menu
            elif client_message == "/members":
                # Show group members
                self.send_group_members(group_id)
                continue
            elif client_message == "/leave":
                # Leave group
                success, message = self.db_manager.leave_group(group_id, self.user_id)
                self.writer.write(f"LEAVE_RESULT:{message}\n")
                self.writer.flush()
                if success:
                    return
                continue

            # Save message to database
            self.db_manager.save_group_message(group_id, self.user_id, user_name, client_message)

            # Broadcast to all group members who are online (except sender)
            delivered_count = 0
            for member_username in member_usernames:
                if member_username != user_name:
                    if self.server.send_to_user(
                        member_username,
                        f"GROUP_MESSAGE:{group_name}:{user_name}:{client_message}"
                    ):
                        delivered_count += 1

            # Confirm to sender
            self.writer.write(f"GROUP_SENT:Message sent to group\n")
            self.writer.flush()

    def send_group_history(self, group_id, group_name):
        """Send group chat history"""
        messages = self.db_manager.get_group_messages(group_id, limit=50)

        self.writer.write(f"GROUP_CHAT_START:{group_name}:{group_id}\n")
        self.writer.flush()

        if messages:
            for sender_username, message_text, timestamp in messages:
                formatted_msg = f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {sender_username}: {message_text}"
                self.writer.write(f"{formatted_msg}\n")
                self.writer.flush()

        self.writer.write("GROUP_CHAT_READY\n")
        self.writer.flush()

    def send_group_members(self, group_id):
        """Send list of group members"""
        members = self.db_manager.get_group_members(group_id)
        
        self.writer.write("GROUP_MEMBERS_START\n")
        self.writer.flush()

        for user_id, username, role, joined_at in members:
            role_badge = "👑 Admin" if role == "admin" else "👤 Member"
            self.writer.write(f"{username}|{role_badge}|{joined_at.strftime('%Y-%m-%d')}\n")
            self.writer.flush()

        self.writer.write("GROUP_MEMBERS_END\n")
        self.writer.flush()

    def send_message(self, message):
        """
        Sends a message to the client.
        """
        if self.writer:
            self.writer.write(message + "\n")
            self.writer.flush()