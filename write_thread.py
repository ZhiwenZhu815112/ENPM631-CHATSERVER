import threading
import socket
import sys
import time
import select
import os

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
        self.daemon = True  # CHANGED BACK: Make it daemon - we can't reliably stop it
        self.socket = client_socket
        self.client = client
        self.writer = None
        self.running = True
        self._authenticated_event = threading.Event()
        
        try:
            self.writer = self.socket.makefile('w', encoding='utf-8')
        except IOError as ex:
            print(f"Error getting streams: {ex}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """Signal thread to stop"""
        self.running = False

    def run(self):
        # Wait for ReadThread to handle authentication
        max_wait = 300
        waited = 0
        while not self.client.is_authenticated() and waited < max_wait and self.running:
            time.sleep(0.1)
            waited += 0.1
            
        if not self.client.is_authenticated() or not self.running:
            return
            
        user_name = self.client.get_user_name()
        if not user_name:
            return

        # Main input loop
        while self.running:
            try:
                # Check if socket is still connected before reading input
                try:
                    self.socket.getpeername()
                except:
                    # Socket disconnected - exit immediately
                    break
                
                # Very short timeout to check socket frequently
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                
                if ready:
                    text = sys.stdin.readline().rstrip('\n')
                    
                    # Ignore empty input during reconnection
                    if not text.strip():
                        continue
                    
                    # Check running flag and socket before sending
                    if not self.running:
                        break
                    
                    # Try to send, but catch all socket errors
                    try:
                        self.socket.getpeername()  # Verify still connected
                        self.writer.write(text + "\n")
                        self.writer.flush()
                    except:
                        # Socket closed during send - exit silently
                        break
                    
                    # If user typed 'bye', stop auto-reconnection
                    if text.strip().lower() == "bye":
                        self.client.stop_reconnection()
                        self.running = False
                        break
                        
            except (EOFError, KeyboardInterrupt):
                self.client.stop_reconnection()
                self.running = False
                break
            except:
                # Any error - exit silently to trigger reconnect
                break
        
        # Cleanup
        try:
            if self.writer:
                self.writer.close()
        except:
            pass