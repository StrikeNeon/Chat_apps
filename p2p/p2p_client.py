from socket import (socket, AF_INET,
                    SOCK_STREAM,
                    SOL_SOCKET,
                    SO_REUSEADDR)
from select import select
import random
import string
from threading import Thread


class client():
    def __init__(self, ip, port, username):
        self.connector_socket = socket(AF_INET, SOCK_STREAM)
        self.connector_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.connector_socket.bind((ip, port))
        self.client_name = username
        self.peer_addr = (ip, port)
        self.peer_name = None

    def clean(self):
        try:
            self.connector_socket.close()
        except OSError:
            pass

    def connection_loop(self, ip, port):
        self.connector_socket.connect((ip, port))
        self.connector_socket.send(self.client_name.encode())
        self.peer_name = self.connector_socket.recv(1024).decode()
        print(f"connected to {self.peer_name}")
        while True:
            self.readable, self.writable, self.exceptional = select(
                [self.connector_socket], [self.connector_socket], [])
            print(self.readable)
            for s in self.readable:
                data = s.recv(1024)
                if data:
                    print(f"recieve message from: {self.peer_addr}, {data.decode()}")

            send_msg = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(5))
            # send_msg = input().replace('b', '').encode()

            for s in self.writable:
                print(s)
                self.send_msg(s, send_msg)
                s.close()
                return True

            for s in self.exceptional:
                self.exceptional.remove(s)
                s.close()

    def send_msg(self, socket, message):
        encoded_msg = message.encode()
        socket.send(encoded_msg)
        print(f"msg: {message} send to user {self.connector_socket.getpeername()}")


def connect_to_user(own_ip_port, username, target_ip_port):
    own_conn_args = own_ip_port.split(":")
    target_conn_args = target_ip_port.split(":")
    client_sock = client(own_conn_args[0], int(own_conn_args[1]), username)
    # client_sock.clean()
    thread = Thread(target=client_sock.connection_loop, args=(target_conn_args[0], int(target_conn_args[1])))
    thread.start()
    thread.join()


def make_connections(own_address, username, address_list):
    threads = []
    for address in address_list:
        thread = connect_to_user(own_address, username, address)
        threads.append(thread)


def test():
    thread0 = Thread(target=make_connections, args=("127.0.0.1:2222", "anon0", ["127.0.0.1:5555", "127.0.0.1:8888"]))
    thread1 = Thread(target=make_connections, args=("127.0.0.1:5555", "anon1", ["127.0.0.1:2222", "127.0.0.1:8888"]))
    thread2 = Thread(target=make_connections, args=("127.0.0.1:8888", "anon2", ["127.0.0.1:2222", "127.0.0.1:5555"]))
    thread0.start()
    thread1.start()
    thread2.start()
    thread0.join()
    thread1.join()


test()
