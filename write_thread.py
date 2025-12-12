import threading
import socket
import sys
import getpass
import time
import select
import platform

"""
This thread is responsible for reading user's input and send it
to the server.
It runs in an infinite loop until the user types 'bye' to quit.

@author www.codejava.net (Java version)
Python port with authentication support
"""

class WriteThread(threading.Thread):
    def __init__(self, client_socket, client):
        super().__init__()
        self.daemon = True  # Daemon thread - will exit when main thread exits
        self.socket = client_socket
        self.client = client
        self.writer = None

        try:
            self.writer = self.socket.makefile('w', encoding='utf-8')
        except IOError as ex:
            print(f"Error getting streams: {ex}")
            import traceback
            traceback.print_exc()

    def run(self):
        # Wait for ReadThread to handle authentication
        # Don't print anything - let ReadThread handle all UI

        max_wait = 300  # Wait up to 5 minutes for authentication (user might be slow typing)
        waited = 0
        while not self.client.is_authenticated() and waited < max_wait:
            time.sleep(1)
            waited += 1

        if not self.client.is_authenticated():
            # Silently exit - ReadThread will show error if needed
            return

        user_name = self.client.get_user_name()
        if not user_name:
            return

        # Main input loop: send both contact selections and messages
        while True:
            try:
                # Use select to make input non-blocking, check socket health
                import select
                import sys

                # Check if stdin has input (with 0.5s timeout)
                ready, _, _ = select.select([sys.stdin], [], [], 0.5)

                if ready:
                    text = sys.stdin.readline().rstrip('\n')

                    # Send the input (could be contact name, message, or command)
                    # Let the server decide what to do with it based on context
                    self.writer.write(text + "\n")
                    self.writer.flush()

                    # If user typed 'bye', stop auto-reconnection
                    if text.strip().lower() == "bye":
                        self.client.stop_reconnection()
                        break
                else:
                    # No input, check if socket is still alive
                    try:
                        # Try to write empty data to check socket health
                        self.socket.getpeername()  # This will fail if disconnected
                    except:
                        # Socket disconnected, exit to trigger reconnect
                        break

            except EOFError:
                self.client.stop_reconnection()
                break
            except KeyboardInterrupt:
                # On Ctrl+C, send bye and exit
                try:
                    self.writer.write("bye\n")
                    self.writer.flush()
                except:
                    pass
                self.client.stop_reconnection()
                break
            except IOError:
                # Socket closed by server (user logged out or disconnected)
                # Don't stop reconnection here - let auto-reconnect handle it
                break

        try:
            self.socket.close()
        except IOError as ex:
            print(f"Error closing connection: {ex}")
