from threading import Thread
import socket
import sys
import select
import Queue
import json
from pymongo import MongoClient
import loguru
# TODO this is a placeholder, check phone


class room_socket():
    def __init__(self, collection, port, limit=10):
        self.room_logger = loguru.logger
        self.db_collection = collection
        self.room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.room_socket.setblocking(0)
        self.room_host_name = socket.gethostname()
        self.room_ip = socket.gethostbyname(self.base_host_name)

        self.room_port = port

        self.room_socket.bind((self.base_host_name, self.room_port))
        self.room_logger.info("Binding successful!")
        self.room_logger.info(f"Base server bound to: {self.base_ip}:{self.room_port}")

        self.room_socket.listen(limit)
        self.inputs = [self.room_socket]
        self.outputs = []
        self.message_queues = {}
        self.room_logger.info(f"Base server limit set at {limit}")
        self.message_queues["all"] = Queue.Queue()

    def room_loop(self):
        while self.inputs:
            readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
            # Handle inputs
            for s in readable:

                if s is self.room_socket:
                    # A "readable" server socket is ready to accept a connection
                    connection, client_address = s.accept()
                    connection.setblocking(0)
                    self.inputs.append(connection)

                    # Give the connection a queue for data we want to send
                    self.message_queues[connection.getpeername()] = Queue.Queue()
                else:
                    data = s.recv(1024)
                    if data:
                        decoded_data = json.loads(data.decode("UTF-8"))
                        operation = decoded_data.get("OPS", None)
                        if not operation:
                            error_response = json.dumps(({"error": "no operation specified"}))
                            s.send(error_response.encode("UTF-8"))
                            continue
                        if operation == "QUIT":
                            del self.message_queues[s.getpeername()]
                            s.close()
                        elif operation == "MESSAGE":
                            to_user = decoded_data.get("at_user", None)
                            if not to_user:
                                error_response = json.dumps(({"error": "no operation specified"}))
                                s.send(error_response.encode("UTF-8"))
                                continue
                            # A readable client socket has data
                            self.message_queues[s.getpeername()].put(data)
                            # Add output channel for response
                            if s not in self.outputs:
                                self.outputs.append(s.getpeername())
                    else:
                        pass
            # Handle outputs
            for s in writable:
                try:
                    next_msg = self.message_queues[s.getpeername()].get_nowait()
                except Queue.Empty:
                    # No messages waiting so stop checking for writability.
                    self.outputs.remove(s.getpeername())
                else:
                    if s.getpeername() == next_msg.get("at_user") or next_msg.get("at_user") == "all":
                        s.send(json.dumps(next_msg).encode("UTF-8"))

        pass


class room_server():
    def __init__(self, limit=1, port=6661):
        self.base_logger = loguru.logger
        self.client = MongoClient('127.0.0.1:27017')

        self.db = self.client['chat_apps']
        self.collection = self.db['client-server']

        self.base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.base_host_name = socket.gethostname()
        self.base_ip = socket.gethostbyname(self.base_host_name)

        self.base_port = port

        self.base_socket.bind((self.base_host_name, self.base_port))
        self.base_logger.info("Binding successful!")
        self.base_logger.info(f"Base server bound to: {self.base_ip}:{self.base_port}")

        self.base_socket.listen(limit)
        self.base_logger.info(f"Base server limit set at {limit}")

    def room_service(self):
        while True:
            conn, add = self.base_socket.accept()

            self.base_logger.info(f"Received connection from {add[0]}")
            self.base_logger.info(f'Connection Established. Connected From: {add[0]}')
            greeting_data = json.loads((conn.recv(1024)).decode("UTF-8"))
            if not greeting_data.get('username') or not greeting_data.get("target_room"):
                error_response = json.dumps(({"error": "no target room supplied"}))
                conn.send(error_response.encode("UTF-8"))
                conn.close()
                self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
            self.base_logger.info(f'greetings from {greeting_data.get("username")} {greeting_data}')

            location = greeting_data.get("target_room")
            result_of_check = self.base_socket.connect_ex((("127.0.0.1", location)))
            if result_of_check == 0:
                self.open_room(greeting_data.get("target_room"))
                conn.close()
            else:
                room_data = self.collection.find_one({"ROOM": location})
                if self.base_socket.getpeername() not in room_data.get("Blacklist"):
                    error_response = json.dumps(({"success": "connection allowed"}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                else:
                    error_response = json.dumps(({"error": "no room found"}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()

    def open_room(self, port):
        room = room_socket(self.collection, port)
        room_thread = Thread(target=room.room_loop, args=())
        room_thread.start()
        room_thread.join()
