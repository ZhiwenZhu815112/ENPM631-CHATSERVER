import socket
import sys
from read_thread import ReadThread
from write_thread import WriteThread

"""
This is the chat client program with authentication.
Type 'bye' to terminate the program.

@author www.codejava.net (Java version)
Python port with authentication support
"""

class ChatClient:
    def __init__(self, hostname, port):
        self.hostname = hostname
        self.port = port
        self.user_name = None
        self.authenticated = False
        self.contacts = []
        self.current_contact = None

    def execute(self):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((self.hostname, self.port))

            print("Connected to the chat server")

            read_thread = ReadThread(client_socket, self)
            read_thread.start()

            write_thread = WriteThread(client_socket, self)
            write_thread.start()

        except socket.gaierror as ex:
            print(f"Server not found: {ex}")
        except IOError as ex:
            print(f"I/O Error: {ex}")

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


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Syntax: python chat_client.py <hostname> <port-number>")
        sys.exit(0)

    hostname = sys.argv[1]
    port = int(sys.argv[2])

    client = ChatClient(hostname, port)
    client.execute()
