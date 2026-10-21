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


def server():
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print("[S]: Server socket created")
    except OSError as err:
        print(f"[S]: Socket open error: {err}")
        return

    try:
        server_socket.bind((SERVER_HOST, ASSIGNED_PORT))
        server_socket.listen(1)
        print(f"[S]: Server host is {SERVER_HOST}")
        print(f"[S]: Server port is {ASSIGNED_PORT}")

        client_socket, client_address = server_socket.accept()
        print(f"[S]: Got a connection request from {client_address}")
        with client_socket:
            client_socket.sendall(b"Welcome to CS 352!")
    except OSError as err:
        print(f"[S]: Server error: {err}")
    finally:
        server_socket.close()


def client():
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("[C]: Client socket created")
    except OSError as err:
        print(f"[C]: Socket open error: {err}")
        return

    try:
        client_socket.connect((SERVER_HOST, ASSIGNED_PORT))
        data_from_server = client_socket.recv(4096)
        print(
            "[C]: Data received from server: "
            f"{data_from_server.decode('utf-8')}"
        )
    except OSError as err:
        print(f"[C]: Client error: {err}")
    finally:
        client_socket.close()


if __name__ == "__main__":
    server_thread = threading.Thread(name="server", target=server)
    server_thread.start()

    time.sleep(random.random() * 5)

    client_thread = threading.Thread(name="client", target=client)
    client_thread.start()

    server_thread.join()
    client_thread.join()

    time.sleep(5)
    print("Done.")
