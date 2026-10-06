"""CS 352 Project 1 - Fall 2026.

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
        #data_from_client = client_socket.recv(4096).decode('utf-8').splitlines()
        data_from_client = receive_lines(client_socket).decode('utf-8').splitlines()
        data_from_server = []
        print(f"[S]: Data from client:\n" + "\n".join(data_from_client))
        for line in data_from_client: 
            tmp = line.split("|", maxsplit=1) 
            transformed = "".join(reversed(tmp[1])).swapcase()
            actual_length = len(transformed.encode("utf-8"))
            if random.random() < 0.10:
                reported_length = actual_length + random.randint(1, 1000)
            else:
                reported_length = actual_length
            #tmp[1] = reversed(tmp[1])
            # print(f"[S]: tmp = {tmp[1]}")
            new_line = tmp[0] + f"|{reported_length}|" + transformed + '\n'
            print(f"[S]: Reformatted line: {new_line.strip('\n')}")
            data_from_server.append(new_line)
        data_sent = "".join(data_from_server)
        print(f"[S]: Reformatted data: {data_sent.strip('\n')}")
        data_sent = data_sent.encode("utf-8")
        print(f"[S]: Sending to client:\n{data_sent.decode('utf-8')}")
        # also can do: 
        # data_sent = ''.join(reversed(data_from_client)).swapcase()
        with client_socket:
            client_socket.sendall(data_sent)
            client_socket.shutdown(socket.SHUT_WR)
    except OSError as err:
        print(f"[S]: Server error: {err}")
    finally:
        server_socket.close()

def receive_lines(sock: socket.socket):
    lines_received = b''
    while True: 
        data = sock.recv(1024)
        if not data: 
            break
        lines_received += data

    return lines_received


if __name__ == "__main__":
    server_thread = threading.Thread(name="server", target=server)
    server_thread.start()

    #time.sleep(random.random() * 5)

    server_thread.join()

    #time.sleep(5)
    print("Done.")
