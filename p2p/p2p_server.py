from socket import (socket, AF_INET,
                    SOCK_STREAM,
                    SOL_SOCKET,
                    SO_REUSEADDR)
from select import select
import random
import string


class reception_server():
    # This serves active users in rooms
    def __init__(self, port=6660, ip="127.0.0.1"):
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        self.server_socket.setblocking(0)
        self.server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server_socket.bind((ip, port))
        self.server_socket.listen()
        self.inputs = [self.server_socket]
        self.outputs = []
        self.message_queues = {}

    # TODO recieve encoded json with user name, ip:port and room request
    # If this room exists - serve json with active users ip if you are not in room blacklist\room whitelist
    # If not - add base room structure, set user as host status, serve room created message
    def serve_keys(self):
        while self.inputs:
            self.readable, self.writable, self.exceptional = select(
                self.inputs, [], self.inputs)
            for s in self.readable:
                if s is self.server_socket:
                    connection, client_address = s.accept()
                    connection.setblocking(0)
                    self.inputs.append(connection)
                else:
                    data = s.recv(1024)
                    if data:
                        print(f"recieves from: {s}")
                        print(data.decode())

            send_msg = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(5))
            # send_msg = input().replace('b', '').encode()

            for s in self.writable:
                s.send(send_msg.encode())
                print(f"msg: {send_msg} send to server {s}")

            for s in self.exceptional:
                self.inputs.remove(s)
                s.close()