from threading import Thread
import socket
import json
import loguru
from time import sleep
from datetime import datetime
from Crypto.Cipher import PKCS1_OAEP
from Crypto.PublicKey import RSA
from binascii import hexlify


logger = loguru.logger


class client():
    def __init__(self, ip, port, username, password):
        self.room_service = ("127.0.0.1", 6661)
        self.ip = ip
        self.port = port
        self.username = username
        self.password = password
        self.connected = False
        self.private_key, self.public_key = self.get_keys()
        self.cypher = PKCS1_OAEP.new(key=self.public_key)
        self.decypher = PKCS1_OAEP.new(key=self.private_key)

    def get_keys(self):
        try:
            #  Generating private key (RsaKey object) of key length of 1024 bits
            pr_key = RSA.generate(1024)
            #  Generating the public key (RsaKey object) from the private key
            pu_key = pr_key.publickey()
            with open('private_pem.pem', 'w') as pr:
                pr.write(pr_key.export_key().decode())
            with open('public_pem.pem', 'w') as pu:
                pu.write(pu_key.export_key().decode())
            return pr_key, pu_key

        except FileNotFoundError:
            pr_key = RSA.import_key(open('private_pem.pem', 'r').read())
            pu_key = RSA.import_key(open('public_pem.pem', 'r').read())
            return pr_key, pu_key

    def make_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.bind(('', self.port))
        logger.debug(f"made socket |{client_socket}")
        return client_socket

    def login(self):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        greeting = {"action": "login", "username": self.username, "password": self.password, "time":datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("login data sent sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        if decoded_response.get("status") == 200:
            logger.debug(f"response recieved, closing {decoded_response}")
            self.client_socket.close()
        return decoded_response.get("token")

    def greet(self, room, token):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        greeting = {"action": "GREETING", "username": self.username, "password": self.password, "target_room": room, "token": token, "time":datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("greeting sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        logger.debug(f"response recieved, closing {decoded_response}")
        self.client_socket.close()
        return decoded_response

    def register(self, info_dict):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        greeting = {"action": "REG", "username": self.username, "password": self.password, "info": info_dict, "time":datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("registration data sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        if decoded_response.get("status", None) == 200:
            logger.debug(f"user registered, closing {decoded_response}")
            self.client_socket.close()
            return decoded_response
        else:
            logger.debug(f"user not registered, closing {decoded_response}")
            self.client_socket.close()
            return decoded_response

    def main_loop(self, room_no):
        self.client_socket = self.make_socket()
        self.client_socket.connect((self.room_service[0], room_no))

        greeting = {"action": "GREETING", "username": self.username, "user_ip": [self.ip, self.port], "time":datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("greeting sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        if decoded_response.get("status") == 200:
            logger.info("connected")

            self.connected = True
            input_thread = Thread(target=self.send_loop, args=())
            output_thread = Thread(target=self.recieve_loop, args=())
            input_thread.start()
            output_thread.start()
            input_thread.join()
            output_thread.join()
        else:
            logger.error(f"not connected, {decoded_response}")

    def send_loop(self):
        while self.connected:
            message = input("MGS: ")
            if message == "QUIT":
                structured_message = {"action": "QUIT", "time":datetime.timestamp(datetime.now())}
                self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
                self.connected = False
                self.client_socket.close()
                return
            else:
                # encrypted_message = self.cypher.encrypt(bytes(message, encoding="utf-8"))
                structured_message = {"action": "MESSAGE", "at_user": "all", "from_user": (self.ip, self.port), "message": message, "time":datetime.timestamp(datetime.now())}
                self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))

    def recieve_loop(self):
        while self.connected:
            try:
                message = self.client_socket.recv(1024)
                logger.debug(message.decode("UTF-8"))
                decoded_message = json.loads(message.decode("UTF-8"))
                if decoded_message.get("action", None) == "presence":
                    structured_message = {"action": "presence", "response": "here", "time":datetime.timestamp(datetime.now())}
                    self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
                # decrypted_message = self.decypher.decrypt(decoded_message.get('message'))
                print(f"message from: {decoded_message.get('from_user')}| {decoded_message.get('message')}")
            except json.decoder.JSONDecodeError:
                # logger.error("malformed message, exiting")
                # logger.debug(message.decode("UTF-8"))
                # self.connected = False
                # self.client_socket.close()
                # return
                pass
            except ConnectionAbortedError:
                logger.warning("connection closed")
            sleep(0.2)


# client_port = input("input port: ")
client_port = 9991
client = client("localhost", int(client_port), "anon", "password")
registered = client.register({"aboutme": "bruh"})

token = client.login()
if token:
# room_no = input("connect to room: ")
    room_no = 1234
    response = client.greet(int(room_no), token)
    if response.get("status") == 200:
        logger.info(f"connection to room {room_no} allowed")
        client.main_loop(int(room_no))
    elif response.get("status") == 201:
        logger.info(f"created room {room_no}")
        client.main_loop(int(room_no))
    elif response.get("status") > 300:
        logger.info(f"failed, {response.get('status')} {response.get('alert')}")
