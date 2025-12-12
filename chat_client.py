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
        self.session_token = None
        self.should_reconnect = True
        self.client_socket = None
        self.read_thread = None
        self.write_thread = None
        self.reconnecting = False

    def execute(self):
        """Main execution with auto-reconnection support"""
        first_connect = True
        
        while self.should_reconnect:
            try:
                self.connect()
                first_connect = False
                
                # If we reach here, connection was closed normally
                if not self.should_reconnect:
                    break
                
                # Connection lost - attempt to reconnect
                if self.session_token and self.user_name:
                    print("\n🔄 Reconnecting...", end='', flush=True)
                    time.sleep(2)
                else:
                    # No session to resume, exit
                    break
                    
            except socket.gaierror as ex:
                print(f"Server not found: {ex}")
                break
            except IOError as ex:
                # Silent retry for IO errors (network blip)
                if self.session_token and self.user_name:
                    if first_connect:
                        print(f"Connection failed: {ex}")
                        break
                    else:
                        print("\n🔄 Reconnecting...", end='', flush=True)
                        time.sleep(2)
                else:
                    break
            except KeyboardInterrupt:
                print("\n👋 Disconnected by user")
                self.should_reconnect = False
                break

    def connect(self):
        """Establish connection to server"""
        # Clean up old threads and socket before reconnecting
        if self.reconnecting:
            self.cleanup_old_connection()
        
        self.reconnecting = True
        
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.hostname, self.port))
            
            # Only print connection message on first connect (not reconnect)
            if not self.user_name:
                print("✓ Connected to the chat server")
            
            # Create new threads
            self.read_thread = ReadThread(self.client_socket, self)
            self.read_thread.start()
            
            self.write_thread = WriteThread(self.client_socket, self)
            self.write_thread.start()
            
            # Reset reconnecting flag
            self.reconnecting = False
            
            # Wait for read thread to complete
            self.read_thread.join()
            
        except Exception as e:
            self.reconnecting = False
            raise e

    def cleanup_old_connection(self):
        """Properly stop old threads and close socket before reconnecting"""

        # Signal threads to stop
        if self.read_thread:
            self.read_thread.stop()
        if self.write_thread:
            self.write_thread.stop()
    
        # Force close socket - this will make both threads exit
        if self.client_socket:
            try:
                self.client_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.client_socket.close()
            except:
                pass
    
        # Brief wait for read thread (write thread is daemon, will be abandoned)
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=1.0)
        
        # Don't wait for write_thread - it's stuck on stdin and will be orphaned
        # The new write_thread will take over stdin handling
        
        # Clear references
        self.read_thread = None
        self.write_thread = None
        self.client_socket = None
        
        # Flush stdin to clear any pending input
        self.flush_stdin()

    def flush_stdin(self):
        """Flush any pending input from stdin"""
        import sys
        import select
        
        # Clear any buffered input
        while select.select([sys.stdin], [], [], 0)[0]:
            sys.stdin.readline()  # Discard the line
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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Syntax: python chat_client.py <hostname> <port-number>")
        sys.exit(0)

    hostname = sys.argv[1]
    port = int(sys.argv[2])
    
    client = ChatClient(hostname, port)
    client.execute()