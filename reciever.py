from socket import (socket, AF_INET,
                    SOCK_STREAM,
                    SOL_SOCKET,
                    SO_REUSEADDR,
                    getaddrinfo)
import threading


# TODO:end connection with 'exit'
def connect(socket):
    while True:
        r_msg = socket.recv(1024)
        if not r_msg:
            break
        if r_msg == '':
            pass
        else:
            print(r_msg.decode())


def receive(socket):
    while True:
        s_msg = input().replace('b', '').encode('utf-8')
        if s_msg == '':
            pass
        if s_msg.decode() == 'exit':
            print("wan exit")
            break
        else:
            socket.sendall(s_msg)


def setup(ip, port):
    s = socket(AF_INET, SOCK_STREAM)
    s.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    try:
        s.connect((ip, port))
        thread1 = threading.Thread(target=connect, args=([s]))
        thread2 = threading.Thread(target=receive, args=([s]))
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
    except ConnectionRefusedError:
        return
