from socket import (socket, AF_INET,
                    SOCK_STREAM,
                    SOL_SOCKET,
                    SO_REUSEADDR)
from select import select
import random
import string
from threading import Thread


class server():

    def __init__(self, port, ip="127.0.0.1"):
        self.server_socket = socket(AF_INET, SOCK_STREAM)
        self.server_socket.setblocking(0)
        self.server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.server_socket.bind((ip, port))
        self.server_socket.listen()
        self.inputs = [self.server_socket]
        self.outputs = []
        self.message_queues = {}

    def recieve_msgs(self):
        while self.inputs:
            self.readable, self.writable, self.exceptional = select(
                self.inputs, [], self.inputs)
            print(self.readable, self.writable)
            for s in self.readable:
                if s is self.server_socket:
                    connection, client_address = s.accept()
                    connection.setblocking(0)
                    self.inputs.append(connection)
                    print(self.inputs)
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


class connector():
    def __init__(self, ip, port):
        self.connector_socket = socket(AF_INET, SOCK_STREAM)
        self.connector_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        print("binding")
        self.connector_socket.bind((ip, port))
        print("bound")

    def connect(self, ip, port):
        print("connecting")
        self.connector_socket.connect((ip, port))
        print("connected")
        while True:
            print("reading sockets")
            self.readable, self.writable, self.exceptional = select(
                [self.connector_socket], [self.connector_socket], [])
            print(self.readable, self.writable)
            for s in self.readable:
                data = s.recv(1024)
                if data:
                    print(f"recieves from: {s}")
                    print(data.decode())

            send_msg = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(5))
            # send_msg = input().replace('b', '').encode()

            for s in self.writable:
                s.send(send_msg.encode())
                print(f"msg: {send_msg} send to server {s}")
                return True

            for s in self.exceptional:
                self.connector_socket.remove(s)
                s.close()


def setup_client_2(own_ip_port, target_ip_port):
    own_conn_args = own_ip_port.split(":")
    target_conn_args = target_ip_port.split(":")
    server_sock = connector(own_conn_args[0], int(own_conn_args[1]))
    thread = Thread(target=server_sock.connect, args=(target_conn_args[0], int(target_conn_args[1])))
    thread.start()
    thread.join()


def test_2():
    thread1 = Thread(target=setup_client_2, args=("127.0.0.1:5555", "127.0.0.1:8888"))
    thread2 = Thread(target=setup_client_2, args=("127.0.0.1:8888", "127.0.0.1:5555"))
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()


test_2()
