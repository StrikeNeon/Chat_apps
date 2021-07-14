from threading import Thread
import socket
import sys
import select
import json
import loguru
from time import sleep


logger = loguru.logger


class client():
    def __init__(self, ip, port, username):
        self.room_service = ("127.0.0.1", 6661)
        self.ip = ip
        self.port = port
        self.username = username
        self.connected = False
        self.test_queue = ["QUIT", "test", "anon"]

    def make_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.bind(('', self.port))
        logger.debug(f"made socket |{client_socket}")
        return client_socket

    def greet(self, room):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        greeting = {"username": self.username, "target_room": room}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("greeting sent")
        response = self.client_socket.recv(2048)
        decoded_response = json.loads(response.decode("UTF-8"))
        logger.debug("response recieved, closing")
        self.client_socket.close()
        return decoded_response

    def main_loop(self, room_no):
        self.client_socket = self.make_socket()
        self.client_socket.connect((self.room_service[0], room_no))
        logger.info("connected")
        self.connected = True
        input_thread = Thread(target=self.send_loop, args=())
        output_thread = Thread(target=self.recieve_loop, args=())
        input_thread.start()
        output_thread.start()
        input_thread.join()
        output_thread.join()
        self.client_socket.close()
        logger.info("connection closed")

    def send_loop(self):
        while self.connected:
            message = self.test_queue.pop()
            logger.debug(message)
            if message == "QUIT":
                structured_message = {"OPS": "QUIT"}
                self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
                self.connected = False
            structured_message = {"OPS": "MESSAGE", "at_user": "all", "from_user": (self.ip, self.port), "message": message}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
            sleep(1)

    def recieve_loop(self):
        while self.connected:
            try:
                message = self.client_socket.recv(5120)
                logger.debug(message.decode("UTF-8"))
                decoded_message = json.loads(message.decode("UTF-8"))
                if decoded_message.get("OPS", None) == "presence":
                    structured_message = {"OPS": "MESSAGE", "response": "here"}
                    self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
                print(f"message from: {decoded_message.get('from_user')}| {decoded_message.get('message')}")
            except json.decoder.JSONDecodeError:
                logger.info("malformed message")
            sleep(1)


# client_port = input("input port: ")
client_port = 9993
client = client("localhost", int(client_port), "anon")
# room_no = input("connect to room: ")
room_no = 1234
response = client.greet(int(room_no))
if response.get("status") == "success":
    logger.info(f"connection to room {room_no} allowed")
    client.main_loop(int(room_no))
if response.get("status") == "warning":
    logger.info(f"created room {room_no}")
    client.main_loop(int(room_no))
if response.get("status") == "error":
    logger.info(f"failed, {response.get('message')}")
