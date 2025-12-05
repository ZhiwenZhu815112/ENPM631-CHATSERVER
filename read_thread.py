import threading
import socket
import getpass

"""
This thread is responsible for reading server's input and printing it
to the console.
It runs in an infinite loop until the client disconnects from the server.

@author www.codejava.net (Java version)
Python port with chat history display and authentication handling
"""

class ReadThread(threading.Thread):
    def __init__(self, client_socket, client):
        super().__init__()
        self.socket = client_socket
        self.client = client
        self.reader = None
        self.writer = None
        self.in_history_mode = False

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

        # Main loop: contact selection and messaging
        skip_contact_selection = False
        while True:
            try:
                # Handle contact list and selection (unless we just did it)
                if not skip_contact_selection:
                    result = self.handle_contact_selection()
                    if result is False:
                        break
                    elif result == "NO_CONTACTS":
                        # No contacts available, just continue to next iteration
                        continue
                else:
                    skip_contact_selection = False

                # Handle conversation and messaging
                conv_result = self.handle_conversation()
                if conv_result is False:
                    break
                elif conv_result is True:
                    # User typed 'back' and contact list was already shown inline
                    # Skip contact selection on next iteration and go straight to next conversation
                    skip_contact_selection = True
                    continue

            except IOError as ex:
                print(f"Error communicating with server: {ex}")
                import traceback
                traceback.print_exc()
                break

    def handle_contact_selection(self):
        """Display contact list and handle selection"""
        try:
            response = self.reader.readline()

            # Check for disconnection (readline returns empty string when connection closed)
            if response == '':
                print("\n\n👋 Disconnected from server. Goodbye!")
                import sys
                sys.exit(0)

            response = response.strip()

            # Handle incoming messages while waiting (before contact list)
            incoming_sender = None
            while response.startswith("MESSAGE:") or response.startswith("BROADCAST:"):
                if response.startswith("MESSAGE:"):
                    # Incoming message: MESSAGE:sender:text
                    parts = response.split(":", 2)
                    if len(parts) == 3:
                        sender = parts[1]
                        text = parts[2]
                        print(f"\n💬 {sender}: {text}")
                        incoming_sender = sender  # Remember the sender
                elif response.startswith("BROADCAST:"):
                    # Incoming broadcast: BROADCAST:sender:text
                    parts = response.split(":", 3)
                    if len(parts) >= 3:
                        sender = parts[1]
                        text = parts[2]
                        print(f"\n📢 [BROADCAST] {sender}: {text}")
                # Read next line
                response = self.reader.readline().strip()
                if not response:  # Check for disconnection
                    print("\n\nDisconnected from server. Goodbye!")
                    return False

            # Check for no contacts message
            if response.startswith("NO_CONTACTS"):
                message = response.split(":", 1)[1] if ":" in response else "No contacts available"
                print(f"\n{message}")
                print(f"[{self.client.get_user_name()}]: ", end='', flush=True)
                return "NO_CONTACTS"  # Signal to skip conversation handling

            # Wait for contact list
            if response != "CONTACT_LIST_START":
                print(f"Unexpected response: {response}")
                return False

            # Display contact list
            print("\n" + "="*60)
            print("  CONTACTS")
            print("="*60)

            contacts = []
            while True:
                line = self.reader.readline().strip()
                if line == "CONTACT_LIST_END":
                    break

                # Parse contact: username|status
                if "|" in line:
                    username, status = line.split("|", 1)
                    if username == "BROADCAST":
                        print(f"{len(contacts) + 1}. 📢 BROADCAST CHANNEL")
                    else:
                        status_symbol = "🟢" if status == "online" else "⚪"
                        print(f"{len(contacts) + 1}. {username} {status_symbol} {status}")
                    contacts.append(username)

            print("="*60)

            # Store contacts for write thread
            self.client.set_contacts(contacts)

            # If we received messages, suggest the sender
            if incoming_sender:
                print(f"\n💡 Select '{incoming_sender}' to reply to their message")

            # Prompt for selection
            print("Enter contact name (or press Enter to refresh, 'bye' to exit):")
            print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

            return True

        except Exception as e:
            print(f"Error handling contact selection: {e}")
            return False

    def handle_conversation(self):
        """Handle conversation display and incoming messages"""
        try:
            # Check for and display any pending messages before conversation starts
            pending_messages = []

            # Read first response
            response = self.reader.readline()

            # Check for disconnection immediately (readline returns empty when connection closed)
            if not response:
                print("\n\n👋 Goodbye! Disconnected from server.")
                import sys
                sys.exit(0)  # Force exit

            response = response.strip()

            # Collect all pending incoming messages
            while response.startswith("MESSAGE:") or response.startswith("BROADCAST:"):
                if response.startswith("MESSAGE:"):
                    parts = response.split(":", 2)
                    if len(parts) == 3:
                        sender = parts[1]
                        message_text = parts[2]
                        pending_messages.append((sender, message_text))
                        print(f"\n💬 New message from {sender}: {message_text}")
                        print(f"    Type '{sender}' to reply!")
                elif response.startswith("BROADCAST:"):
                    parts = response.split(":", 3)
                    if len(parts) >= 3:
                        sender = parts[1]
                        message_text = parts[2]
                        pending_messages.append((f"[BROADCAST] {sender}", message_text))
                        print(f"\n📢 New broadcast from {sender}: {message_text}")
                        print(f"    Type 'BROADCAST' to join the channel!")

                # Read next line
                response = self.reader.readline()
                if not response:
                    import sys
                    sys.exit(0)
                response = response.strip()

            # After displaying pending messages, show prompt again if any messages were displayed
            if pending_messages:
                print(f"\n[{self.client.get_user_name()}]: ", end='', flush=True)

            # Check if user refreshed (pressed Enter) - server sends new contact list
            if response == "CONTACT_LIST_START":
                # User refreshed, display the new contact list
                print("\n" + "="*60)
                print("  CONTACTS (Refreshed)")
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
                print("\nEnter contact name (or press Enter to refresh, 'bye' to exit):")
                print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                # Return True to continue - next iteration will wait for selection again
                return True

            # Handle various server responses
            if response.startswith("INVALID_CONTACT"):
                print("\n❌ Invalid contact selection. Please try again.")
                return True  # Continue to next iteration

            if response.startswith("CONTACT_NOT_FOUND"):
                print("\n❌ Contact not found. Please try again.")
                return True

            if response.startswith("CONVERSATION_ERROR"):
                print("\n❌ Error creating conversation. Please try again.")
                return True

            if not response.startswith("CONVERSATION_START") and not response.startswith("BROADCAST_START"):
                print(f"Unexpected response: {response}")
                return False

            # Extract contact name or broadcast channel
            if response.startswith("BROADCAST_START"):
                contact_name = "BROADCAST CHANNEL"
                header = "📢 BROADCAST CHANNEL"
            else:
                contact_name = response.split(":", 1)[1] if ":" in response else "Unknown"
                header = f"CONVERSATION WITH {contact_name}"
            
            self.client.set_current_contact(contact_name)

            # Display conversation header
            print("\n" + "="*60)
            print(f"  {header}")
            print("="*60)

            # Display conversation history
            while True:
                line = self.reader.readline().strip()
                if line == "CONVERSATION_READY":
                    break
                print(line)

            print("="*60)
            print("Type 'back' to return to contacts, or start chatting:")
            print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

            # Handle incoming messages in conversation
            while True:
                message = self.reader.readline()

                # Check for disconnection
                if not message:
                    print("\n\n👋 Connection closed by server.")
                    import sys
                    sys.exit(0)

                message = message.strip()

                # Handle different message types
                if message.startswith("MESSAGE:"):
                    # Incoming message from other user: MESSAGE:sender:text
                    parts = message.split(":", 2)
                    if len(parts) == 3:
                        sender = parts[1]
                        text = parts[2]
                        print(f"\n{sender}: {text}")
                        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                elif message.startswith("BROADCAST:"):
                    # Incoming broadcast message: BROADCAST:sender:text
                    parts = message.split(":", 3)
                    if len(parts) >= 3:
                        sender = parts[1]
                        text = parts[2]
                        print(f"\n📢 {sender}: {text}")
                        print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                elif message.startswith("SENT:"):
                    # Confirmation that our message was sent
                    # Show prompt again so user can continue typing
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                elif message.startswith("BROADCAST_SENT:"):
                    # Confirmation that our broadcast was sent
                    status = message.split(":", 1)[1] if ":" in message else "Broadcast sent"
                    print(f"\n✅ {status}")
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                elif message == "CONTACT_LIST_START":
                    # User typed 'back' - server is sending new contact list
                    # Display it and exit this conversation
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
                            status_symbol = "🟢" if status == "online" else "⚪"
                            print(f"{len(contacts) + 1}. {username} {status_symbol} {status}")
                            contacts.append(username)

                    print("="*60)
                    self.client.set_contacts(contacts)
                    print("\nEnter contact name (or press Enter to refresh, 'bye' to exit):")
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

                    # Return True to indicate we should continue with another conversation
                    # The main loop will call handle_conversation again
                    # which will wait for the next CONVERSATION_START after user selects
                    return True

                else:
                    # Unknown message
                    print(f"\nServer: {message}")
                    print(f"[{self.client.get_user_name()}]: ", end='', flush=True)

        except Exception as e:
            print(f"Error handling conversation: {e}")
            import traceback
            traceback.print_exc()
            return False

    def handle_authentication(self):
        """Handle the complete authentication flow"""
        try:
            # Wait for AUTH_REQUEST from server
            auth_request = self.reader.readline().strip()
            if auth_request != "AUTH_REQUEST":
                print(f"Unexpected server response: {auth_request}")
                return False

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
                        # If login fails, it will redirect to signup
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
                return True
            elif response.startswith("AUTH_FAILED"):
                message = response.split(":", 1)[1] if ":" in response else "Login failed"
                print(f"\n{message}")
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
                    continue  # Loop again, don't send to server yet

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
                return True
            elif response.startswith("AUTH_FAILED"):
                message = response.split(":", 1)[1] if ":" in response else "Registration failed"
                print(f"\n{message}")
                retry = input("Try again? (y/n): ").strip().lower()
                if retry == 'y':
                    return self.do_signup()  # Now it's safe to retry
                else:
                    return False
            else:
                print(f"Unexpected server response: {response}")
                return False

        except Exception as e:
            print(f"Signup error: {e}")
            return False
