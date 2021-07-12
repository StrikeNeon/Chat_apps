from threading import Thread
import socket
import sys
import select
import queue
import json
import loguru


logger = loguru.logger

class client():
    def __init__(self, ip, port, username):
        self.room_service = ("127.0.0.1", 6661)
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.bind((ip, port))
        self.username = username

    def greet(self, room):
        self.client_socket.connect(self.room_service)
        greeting = {"username": self.username, "target_room": room}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        return decoded_response

    def main_loop(self):
        while True:
            message = self.client_socket.recv(1024)
            decoded_message = json.loads(message.decode("UTF-8"))
            print(f"message from: {decoded_message.get('from_user')}| {decoded_message.get('message')}")
            message = input("Me : ")
            if message == "QUIT":
                structured_message = {"OPS": "QUIT"}
                self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
                return
            structured_message = {"OPS": "MESSAGE", "at_user": "all", "from_user": self.username, "message": message}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))


client = client("127.0.0.1", 9999, "anon")
room_no = input("connect to room: ")
response = client.greet(int(room_no))
if response.get("status") == "success":
    logger.info(f"connected to room {room_no}")
    client.main_loop()
if response.get("status") == "warning":
    logger.info(f"created room {room_no}")
    client.main_loop()
if response.get("status") == "warning":
    logger.info(f"failed, {response.get('message')}")