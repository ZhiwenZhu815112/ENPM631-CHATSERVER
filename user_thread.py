import threading
import socket

"""
This thread handles connection for each connected client, so the server
can handle multiple clients at the same time.

@author www.codejava.net (Java version)
Python port with authentication and message storage
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

            # Main contact selection and messaging loop
            while True:
                # Send contact list (always includes BROADCAST)
                contact_list = self.send_contact_list()

                # Contact list always has at least BROADCAST, so we no longer need NO_CONTACTS handling

                # Wait for contact selection
                selected_contact = input_stream.readline().strip()

                # Handle special commands
                if selected_contact == "bye":
                    break
                elif not selected_contact:
                    # Empty input = refresh contact list
                    continue
                elif selected_contact == "BROADCAST":
                    # Handle broadcast messaging
                    self.handle_broadcast_chat(input_stream, user_name)
                    continue

                # Note: Don't validate against cached contact_list - check database instead
                # This allows users to message people who logged in after the list was shown

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

                # Enter messaging mode with selected contact
                self.chat_with_contact(input_stream, user_name, selected_contact, conversation_id)

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

            # Send broadcast message to all online users except sender
            online_users = self.server.get_online_usernames()
            delivered_count = 0
            
            for recipient in online_users:
                if recipient != user_name:  # Don't send to self
                    if self.server.send_to_user(recipient, f"BROADCAST:{user_name}:{client_message}"):
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

    def send_message(self, message):
        """
        Sends a message to the client.
        """
        if self.writer:
            self.writer.write(message + "\n")
            self.writer.flush()
