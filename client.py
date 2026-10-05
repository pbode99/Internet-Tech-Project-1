"""CS 352 Project 1 starter code - Fall 2026.

This file intentionally contains a server and client in separate threads.
Follow the project handout to study it, remove the delays, and then create
separate client.py and server.py programs.
"""

import random
import socket
import threading
import time


# Replace this value with the TCP port assigned to your team.
ASSIGNED_PORT = 30011
SERVER_HOST = "127.0.0.1"



def client():
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("[C]: Client socket created")
    except OSError as err:
        print(f"[C]: Socket open error: {err}")
        return

    # TODO: read input from in-proj.txt
    try:
        client_socket.connect((SERVER_HOST, ASSIGNED_PORT))
        with client_socket: 
            client_socket.sendall(b"1|HELLO\n2|Eva, This Prof is amazing\n")
            print(f"[C]: Sent data through socket")
            data_from_server = client_socket.recv(4096)
            print(
                "[C]: Data received from server: \n"
                f"{data_from_server.decode('utf-8')}"
        )
    except OSError as err:
        print(f"[C]: Client error: {err}")
    finally:
        client_socket.close()
    # TODO: verify the line numbers and received length
    # TODO: Write all lines to out-proj.txt


if __name__ == "__main__":
    #time.sleep(random.random() * 5)

    client_thread = threading.Thread(name="client", target=client)
    client_thread.start()
    
    client_thread.join()

    #time.sleep(5)
    print("Done.")
