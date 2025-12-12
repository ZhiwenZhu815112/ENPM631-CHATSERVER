import socket
import sys
import time
from read_thread import ReadThread
from write_thread import WriteThread

"""
This is the chat client program with authentication and auto-reconnection.
Type 'bye' to terminate the program.

@author www.codejava.net (Java version)
Python port with authentication support and reconnection
"""

class ChatClient:
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.user_name = None
        self.authenticated = False
        self.contacts = []
        self.current_contact = None
        self.session_token = None  # For reconnection
        self.should_reconnect = True
        self.client_socket = None
        self.read_thread = None
        self.write_thread = None
        self.in_contact_selection = False  # Track if in contact selection mode

    def execute(self):
        """Main execution with auto-reconnection support"""
        while self.should_reconnect:
            try:
                self.connect()
                # If we reach here, connection was closed normally
                if not self.should_reconnect:
                    break

                # Connection lost - attempt to reconnect
                if self.session_token and self.user_name:
                    print("\n⏳ Reconnecting...", end='', flush=True)
                    time.sleep(2)  # Wait before reconnecting
                else:
                    # No session to resume, exit
                    break

            except socket.gaierror as ex:
                print(f"Server not found: {ex}")
                break
            except IOError as ex:
                # Silent retry for IO errors (network blip)
                if self.session_token and self.user_name:
                    print("\n⏳ Reconnecting...", end='', flush=True)
                    time.sleep(2)
                else:
                    break
            except KeyboardInterrupt:
                print("\nDisconnected by user")
                self.should_reconnect = False
                break

    def connect(self):
        """Establish connection to server"""
        # Signal old write_thread to stop if it exists
        if self.write_thread:
            self.write_thread.stop()

        # Close old socket if it exists to ensure old threads exit
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass

        # If reconnecting, wait for old write_thread to finish (max 1 second)
        if self.write_thread and self.write_thread.is_alive():
            self.write_thread.join(timeout=1.0)
            if self.write_thread.is_alive():
                # Old thread still running - this shouldn't happen but log it
                print("Warning: Old write thread still running")

        # Reset client state for clean reconnection
        self.contacts = []
        self.current_contact = None
        self.in_contact_selection = False

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.hostname, self.port))

        # Only print connection message on first connect (not reconnect)
        if not self.user_name:
            print("✓ Connected to the chat server")

        self.read_thread = ReadThread(self.client_socket, self)
        self.read_thread.start()

        self.write_thread = WriteThread(self.client_socket, self)
        self.write_thread.start()

        # Wait for read thread to complete (write thread is daemon, will auto-exit)
        self.read_thread.join()
        # Don't wait for write_thread - it's a daemon and will exit when read_thread exits

    def set_user_name(self, user_name):
        self.user_name = user_name

    def get_user_name(self):
        return self.user_name

    def set_authenticated(self, status):
        self.authenticated = status

    def is_authenticated(self):
        return self.authenticated

    def set_contacts(self, contacts):
        self.contacts = contacts

    def get_contacts(self):
        return self.contacts

    def set_current_contact(self, contact):
        self.current_contact = contact

    def get_current_contact(self):
        return self.current_contact

    def set_session_token(self, token):
        """Store session token for reconnection"""
        self.session_token = token

    def get_session_token(self):
        """Get stored session token"""
        return self.session_token

    def stop_reconnection(self):
        """Stop auto-reconnection (on clean exit)"""
        self.should_reconnect = False

    def set_in_contact_selection(self, status):
        """Set whether user is in contact selection mode"""
        self.in_contact_selection = status

    def is_in_contact_selection(self):
        """Check if user is in contact selection mode"""
        return self.in_contact_selection


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Syntax: python chat_client.py <hostname> <port-number>")
        sys.exit(0)

    hostname = sys.argv[1]
    port = int(sys.argv[2])

    client = ChatClient(hostname, port)
    client.execute()
