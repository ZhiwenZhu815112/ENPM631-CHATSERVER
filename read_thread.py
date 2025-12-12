import queue
import threading
import socket
import getpass

"""
This thread is responsible for reading server's input and printing it
to the console.
It runs in an infinite loop until the client disconnects from the server.

@author www.codejava.net (Java version)
Python port with chat history display, authentication, and group chat UI
"""

class ReadThread(threading.Thread):
    def __init__(self, client_socket, client):
        super().__init__()
        self.incoming_queue = queue.Queue()
        self.socket = client_socket
        self.client = client
        self.reader = None
        self.writer = None

        try:
            self.reader = self.socket.makefile('r', encoding='utf-8')
            self.writer = self.socket.makefile('w', encoding='utf-8')
        except IOError as ex:
            print(f"Error getting input stream: {ex}")
            import traceback
            traceback.print_exc()

    def run(self):
        # First, handle authentication
        if not self.handle_authentication():
            print("Authentication failed. Exiting...")
            try:
                self.socket.close()
            except:
                pass
            return

        # Main loop: message-driven, always wait for server
        while True:
            try:
                response = self.reader.readline().strip()

                if not response:
                    # Connection closed - return to trigger reconnection
                    return
                
                # Handle incoming notifications (can arrive anytime)
                while response.startswith("MESSAGE:") or response.startswith("BROADCAST:") or response.startswith("GROUP_MESSAGE:"):
                    if response.startswith("MESSAGE:"):
                        parts = response.split(":", 2)
                        if len(parts) == 3:
                            sender = parts[1]
                            text = parts[2]
                            print(f"\n💬 New message from {sender}: {text}")
                    elif response.startswith("BROADCAST:"):
                        parts = response.split(":", 3)
                        if len(parts) >= 3:
                            sender = parts[1]
                            text = parts[2]
                            print(f"\n📢 [BROADCAST] {sender}: {text}")
                    elif response.startswith("GROUP_MESSAGE:"):
                        parts = response.split(":", 3)
                        if len(parts) >= 4:
                            group_name = parts[1]
                            sender = parts[2]
                            text = parts[3]
                            print(f"\n👥 [{group_name}] {sender}: {text}")
                            print(f"[{self.client.get_user_name()}]: ", end='', flush=True)
                    
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                    
                    response = self.reader.readline().strip()
                    if not response:
                        # Connection closed - return to trigger reconnection
                        return
                
                # Route based on server's protocol message
                if response.startswith("PENDING_MESSAGES_START"):
                    # Handle pending messages from reconnection
                    self.display_pending_messages(response)

                elif response == "MAIN_MENU_START":
                    # Display main menu
                    self.display_main_menu()
                    
                elif response == "CONTACT_LIST_START":
                    # Private messages - display contacts
                    self.display_contact_list()
                    # Continue waiting for next protocol message
                    
                elif response.startswith("CONVERSATION_START:"):
                    # Private conversation started
                    contact_name = response.split(":", 1)[1]
                    self.client.set_current_contact(contact_name)
                    self.display_conversation_header(contact_name)
                    # Continue in message loop
                    
                elif response.startswith("BROADCAST_START"):
                    # Broadcast channel
                    self.display_broadcast_channel()
                    # Continue in message loop
                    
                elif response == "MY_GROUPS_START":
                    # My groups
                    self.display_my_groups()
                    # Continue waiting for selection result
                    
                elif response == "BROWSE_GROUPS_START":
                    # Browse all groups
                    self.display_browse_groups()
                    # Continue waiting for selection result
                    
                elif response == "CREATE_GROUP_PROMPT":
                    # Create group
                    self.display_create_group_prompt()
                    # Continue waiting for result
                    
                elif response.startswith("GROUP_CHAT_START:"):
                    # Entering a group chat
                    parts = response.split(":", 2)
                    group_name = parts[1] if len(parts) > 1 else "Unknown Group"
                    self.display_group_chat_header(group_name)
                    # Continue in message loop
                    
                elif response.startswith("SENT:"):
                    # Message sent confirmation
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)
                    
                elif response.startswith("BROADCAST_SENT:"):
                    # Broadcast sent confirmation
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)
                    
                elif response.startswith("GROUP_SENT:"):
                    # Group message sent confirmation
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)
                    
                elif response.startswith("JOIN_SUCCESS:"):
                    message = response.split(":", 1)[1]
                    print(f"\n✅ {message}")
                    
                elif response.startswith("JOIN_FAILED:") or response.startswith("NOT_MEMBER:") or response.startswith("INVALID"):
                    message = response.split(":", 1)[1] if ":" in response else response
                    print(f"\n❌ {message}")
                    
                elif response.startswith("CREATE_SUCCESS:"):
                    parts = response.split(":", 2)
                    if len(parts) >= 2:
                        message = parts[1]
                        print(f"\n✅ {message}")
                        print("Would you like to enter the group now? (yes/no)")
                        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)
                        
                elif response.startswith("CREATE_FAILED:"):
                    message = response.split(":", 1)[1]
                    print(f"\n❌ {message}")
                    
                elif response == "GROUP_MEMBERS_START":
                    self.display_group_members()
                    
                elif response.startswith("LEAVE_RESULT:"):
                    result = response.split(":", 1)[1]
                    print(f"\n{result}")
                    
                elif response == "NO_CONTACTS:":
                    print("\nNo contacts available yet.")
                    print(f"[{self.client.get_user_name()}]: Press Enter to continue...", end='', flush=True)
                    
                # Ignore other messages or handle as needed
                    
            except IOError as ex:
                print(f"Error communicating with server: {ex}")
                import traceback
                traceback.print_exc()
                break

    def display_main_menu(self):
        """Display the main menu sent by server"""
        self.client.set_in_contact_selection(False)  # Disable number conversion
        while True:
            line = self.reader.readline().strip()
            if line == "MAIN_MENU_END":
                break
            print(line)
        print(f"\n[{self.client.get_user_name()}] Select option: ", end='', flush=True)

    def display_contact_list(self):
        """Display contact list"""
        print("\n" + "="*60)
        print("  CONTACTS")
        print("="*60)

        contacts = []
        while True:
            line = self.reader.readline().strip()
            if line == "CONTACT_LIST_END":
                break

            if "|" in line:
                username, status = line.split("|", 1)
                if username == "BROADCAST":
                    print(f"{len(contacts) + 1}. 📢 BROADCAST CHANNEL")
                else:
                    status_symbol = "🟢" if status == "online" else "⚪"
                    print(f"{len(contacts) + 1}. {username} {status_symbol} {status}")
                contacts.append(username)

        print("="*60)
        self.client.set_contacts(contacts)
        self.client.set_in_contact_selection(True)  # Enable number conversion
        print("Enter contact name, 'back' for main menu, or 'bye' to exit:")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def display_conversation_header(self, contact_name):
        """Display conversation header and history"""
        self.client.set_in_contact_selection(False)  # Disable number conversion in chat
        print("\n" + "="*60)
        print(f"  CONVERSATION WITH {contact_name}")
        print("="*60)

        # Display history
        while True:
            line = self.reader.readline().strip()
            if line == "CONVERSATION_READY":
                break
            print(line)

        print("="*60)
        print("Type 'back' to return to contacts, or start chatting:")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def display_broadcast_channel(self):
        """Display broadcast history"""
        self.client.set_in_contact_selection(False)  # Disable number conversion in broadcast
        print("\n" + "="*60)
        print("  BROADCAST CHANNEL")
        print("="*60)

        # Read history
        while True:
            line = self.reader.readline().strip()
            if line == "CONVERSATION_READY":
                break
            print(line)

        print("="*60)
        print("Type 'back' to return to main menu, or start chatting:")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def display_my_groups(self):
        """Display my groups"""
        self.client.set_in_contact_selection(False)  # Groups use IDs, not list numbers
        next_line = self.reader.readline().strip()

        if next_line.startswith("NO_GROUPS:"):
            message = next_line.split(":", 1)[1]
            print(f"\n{message}")
            self.reader.readline()  # MY_GROUPS_END
            print(f"\n[{self.client.get_user_name()}]: Press Enter to return to main menu...", end='', flush=True)
            return

        print("\n" + "="*60)
        print("  👥 MY GROUPS")
        print("="*60)

        line = next_line
        while line != "MY_GROUPS_END":
            if "|" in line:
                parts = line.split("|")
                if len(parts) == 5:
                    group_id, name, desc, members, role = parts
                    print(f"{group_id}. {role} {name} ({members} members)")
                    print(f"   {desc}")
            line = self.reader.readline().strip()

        print("="*60)
        print("Enter group ID to open, or 'back' to return to main menu:")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def display_browse_groups(self):
        """Display all groups"""
        self.client.set_in_contact_selection(False)  # Groups use IDs, not list numbers
        next_line = self.reader.readline().strip()

        if next_line.startswith("NO_GROUPS:"):
            message = next_line.split(":", 1)[1]
            print(f"\n{message}")
            self.reader.readline()  # BROWSE_GROUPS_END
            print(f"\n[{self.client.get_user_name()}]: Press Enter to return to main menu...", end='', flush=True)
            return

        print("\n" + "="*60)
        print("  🔍 ALL GROUPS")
        print("="*60)

        line = next_line
        while line != "BROWSE_GROUPS_END":
            if "|" in line:
                parts = line.split("|")
                if len(parts) == 5:
                    group_id, name, desc, members, status = parts
                    print(f"{group_id}. {name} ({members} members) - {status}")
                    print(f"   {desc}")
            line = self.reader.readline().strip()

        print("="*60)
        print("Enter 'join:GROUP_ID' to join, GROUP_ID to open, or 'back' for main menu:")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def display_create_group_prompt(self):
        """Display create group prompt"""
        self.client.set_in_contact_selection(False)  # Disable number conversion
        print("\n" + "="*60)
        print("  ➕ CREATE NEW GROUP")
        print("="*60)
        print("Enter group name (or 'back' to cancel):")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

        # Server will wait for name, then description
        # After we get the name response, we need to prompt for description
        # But this will be handled by the next message from server

    def display_group_chat_header(self, group_name):
        """Display group chat header and history"""
        self.client.set_in_contact_selection(False)  # Disable number conversion in group chat
        print("\n" + "="*60)
        print(f"  👥 GROUP: {group_name}")
        print("="*60)

        # Display history
        while True:
            line = self.reader.readline().strip()
            if line == "GROUP_CHAT_READY":
                break
            print(line)

        print("="*60)
        print("Commands: 'back' (return), '/members' (show members), '/leave' (leave group)")
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def display_group_members(self):
        """Display group members list"""
        print("\n" + "-"*40)
        print("GROUP MEMBERS:")
        while True:
            line = self.reader.readline().strip()
            if line == "GROUP_MEMBERS_END":
                break
            if "|" in line:
                parts = line.split("|")
                if len(parts) == 3:
                    username, role, joined = parts
                    print(f"  {role} {username} (joined {joined})")
        print("-"*40)
        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

    def handle_authentication(self):
        """Handle the complete authentication flow with reconnection support"""
        try:
            # Wait for AUTH_REQUEST from server
            auth_request = self.reader.readline().strip()
            if auth_request != "AUTH_REQUEST":
                print(f"Unexpected server response: {auth_request}")
                return False

            # Check if we have a session token to resume
            session_token = self.client.get_session_token()
            if session_token and self.client.get_user_name():
                # Silently resume session - don't show technical details

                # Send RESUME_SESSION command
                self.writer.write(f"RESUME_SESSION:{session_token}\n")
                self.writer.flush()

                # Wait for result
                response = self.reader.readline().strip()

                if response.startswith("SESSION_RESUMED"):
                    # Clear the "Reconnecting..." message
                    print(f"\r✓ Connected          \n", end='', flush=True)

                    # Read session token (should be same)
                    token_line = self.reader.readline().strip()
                    if token_line.startswith("SESSION_TOKEN:"):
                        new_token = token_line.split(":", 1)[1]
                        self.client.set_session_token(new_token)

                    self.client.set_authenticated(True)
                    # Don't call receive_pending_messages here - let main loop handle it
                    # The server will send PENDING_MESSAGES_START if there are any
                    return True

                elif response.startswith("AUTH_FAILED"):
                    message = response.split(":", 1)[1] if ":" in response else "Session expired"
                    print(f"⚠️ {message}")
                    print("Please log in again.\n")
                    # Fall through to normal login

            # Show authentication menu
            print("\n=== Chat Application Authentication ===")
            print("1. Login")
            print("2. Sign Up")

            while True:
                try:
                    choice = input("Choose an option (1 or 2): ").strip()

                    if choice == "1":
                        if self.do_login():
                            return True
                    elif choice == "2":
                        return self.do_signup()
                    else:
                        print("Invalid choice. Please enter 1 or 2.")
                except EOFError:
                    return False
                except KeyboardInterrupt:
                    return False

        except Exception as e:
            print(f"Authentication error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def display_pending_messages(self, first_line):
        """Display pending messages from server (called from main loop)"""
        try:
            # first_line is "PENDING_MESSAGES_START:count"
            count = int(first_line.split(":", 1)[1])
            if count > 0:
                print(f"\n📬 You have {count} message(s) received while offline:\n")

                for i in range(count):
                    msg_line = self.reader.readline().strip()
                    if msg_line.startswith("PENDING_MSG:"):
                        message = msg_line.split(":", 1)[1]
                        print(f"  {message}")

                # Read end marker
                self.reader.readline()  # PENDING_MESSAGES_END
                print()
            else:
                # No messages, just read the end marker
                self.reader.readline()  # PENDING_MESSAGES_END

        except Exception as e:
            print(f"Error displaying pending messages: {e}")

    def do_login(self):
        """Handle login process"""
        try:
            # Send LOGIN to server
            self.writer.write("LOGIN\n")
            self.writer.flush()

            # Wait for LOGIN_PROMPT
            prompt = self.reader.readline().strip()
            if prompt != "LOGIN_PROMPT":
                print(f"Unexpected server response: {prompt}")
                return False

            # Get credentials from user
            print("\n=== Login ===")
            username = input("Username: ").strip()
            password = getpass.getpass("Password: ")

            # Send credentials to server
            self.writer.write(username + "\n")
            self.writer.flush()
            self.writer.write(password + "\n")
            self.writer.flush()

            # Wait for result
            response = self.reader.readline().strip()

            if response.startswith("AUTH_SUCCESS"):
                message = response.split(":", 1)[1] if ":" in response else "Login successful"
                print(f"\n{message}\n")
                self.client.set_user_name(username)
                self.client.set_authenticated(True)

                # Read session token for reconnection
                token_line = self.reader.readline().strip()
                if token_line.startswith("SESSION_TOKEN:"):
                    token = token_line.split(":", 1)[1]
                    self.client.set_session_token(token)
                    print(f"✓ Session established (reconnection enabled)\n")

                return True
            elif response.startswith("AUTH_FAILED"):
                message = response.split(":", 1)[1] if ":" in response else "Login failed"
                print(f"\n{message}")
                retry = input("Try again? (y/n): ").strip().lower()
                if retry == 'y':
                    return self.do_login()
                else:
                    print("Redirecting to sign up...\n")
                    return self.do_signup()
            else:
                print(f"Unexpected server response: {response}")
                return False

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def do_signup(self):
        """Handle signup process"""
        try:
            # Send SIGNUP to server
            self.writer.write("SIGNUP\n")
            self.writer.flush()

            # Wait for SIGNUP_PROMPT
            prompt = self.reader.readline().strip()
            if prompt != "SIGNUP_PROMPT":
                print(f"Unexpected server response: {prompt}")
                return False

            # Get credentials from user with password confirmation loop
            while True:
                print("\n=== Sign Up ===")
                username = input("Choose a username: ").strip()

                # Validate username
                if not username:
                    print("Username cannot be empty. Please try again.")
                    continue

                password = getpass.getpass("Choose a password: ")

                # Validate password is not empty
                if not password:
                    print("Password cannot be empty. Please try again.")
                    continue

                password_confirm = getpass.getpass("Confirm password: ")

                # Check password match
                if password != password_confirm:
                    print("Passwords do not match. Please try again.")
                    continue

                # Passwords match and are not empty, break out of loop
                break

            # Send credentials to server
            self.writer.write(username + "\n")
            self.writer.flush()
            self.writer.write(password + "\n")
            self.writer.flush()

            # Wait for result
            response = self.reader.readline().strip()

            if response.startswith("AUTH_SUCCESS"):
                message = response.split(":", 1)[1] if ":" in response else "Registration successful"
                print(f"\n{message}\n")
                self.client.set_user_name(username)
                self.client.set_authenticated(True)

                # Read session token for reconnection
                token_line = self.reader.readline().strip()
                if token_line.startswith("SESSION_TOKEN:"):
                    token = token_line.split(":", 1)[1]
                    self.client.set_session_token(token)
                    print(f"✓ Session established (reconnection enabled)\n")

                return True
            elif response.startswith("AUTH_FAILED"):
                message = response.split(":", 1)[1] if ":" in response else "Registration failed"
                print(f"\n{message}")
                retry = input("Try again? (y/n): ").strip().lower()
                if retry == 'y':
                    return self.do_signup()
                else:
                    return False
            else:
                print(f"Unexpected server response: {response}")
                return False

        except Exception as e:
            print(f"Signup error: {e}")
            return False