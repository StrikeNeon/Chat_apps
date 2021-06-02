import sys
from reciever import setup as rec_setup
from sender import setup as send_setup
import threading


def main():
    your_port = input("your port ")
    thread1 = threading.Thread(target=send_setup, args=([int(your_port)]))
    thread1.start()

    ip_port = input("connect to [ip:port] ")
    conn_args = ip_port.split(":")
    if len(conn_args) != 2:
        print(f"usage: {conn_args[0]}{conn_args[1]}")
        sys.exit(0)
        thread1.join()
    thread2 = threading.Thread(target=rec_setup, args=([conn_args[0], int(conn_args[1])]))
    thread2.start()

    thread1.join()
    thread2.join()


main()
