from threading import Thread
import socket
import sys
import select
import queue
import json
from pymongo import MongoClient
import loguru


class room_socket():
    def __init__(self, collection, port, limit=10):
        self.room_logger = loguru.logger
        self.db_collection = collection
        self.room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        self.message_queues["all"] = queue.queue()

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
                    self.message_queues[connection.getpeername()] = queue.queue()
                else:
                    data = s.recv(1024)
                    if data:
                        decoded_data = json.loads(data.decode("UTF-8"))
                        operation = decoded_data.get("OPS", None)
                        if not operation:
                            error_response = json.dumps(({"error": "no operation specified"}))
                            self.message_queues[s.getpeername()].put(error_response.encode("UTF-8"))
                            continue
                        if operation == "QUIT":
                            del self.message_queues[s.getpeername()]
                            s.close()
                        elif operation == "MESSAGE":
                            at_user = decoded_data.get("at_user", None)
                            if not at_user:
                                error_response = json.dumps(({"error": "sent to noone"}))
                                self.message_queues[s.getpeername()].put(error_response.encode("UTF-8"))
                                continue
                            # A readable client socket has data
                            self.message_queues[at_user].put(decoded_data)
                            # Add output channel for response
                            if s not in self.outputs:
                                self.outputs.append(s)
                    else:
                        pass
            # Handle outputs
            for s in writable:
                try:
                    next_msg = self.message_queues[s.getpeername()].get_nowait()
                except queue.Empty:
                    # No messages waiting so stop checking for writability.
                    self.outputs.remove(s)
                else:
                    if s.getpeername() == next_msg.get("at_user") or next_msg.get("at_user") == "all":
                        s.send(json.dumps(next_msg).encode("UTF-8"))

            # Handle "exceptional conditions"
            for s in exceptional:
                # Stop listening for input on the connection
                self.inputs.remove(s)
                if s in self.outputs:
                    self.outputs.remove(s)
                s.close()

                # Remove message queue
                del self.message_queues[s.getpeername()]


class room_server():
    def __init__(self, limit=0, port=6661):
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
        self.base_logger.debug("main loop started")
        while True:
            try:
                conn, add = self.base_socket.accept()

                self.base_logger.info(f"Received connection from {add[0]}")
                self.base_logger.info(f'Connection Established. Connected From: {add[0]}')
                greeting_data = json.loads((conn.recv(1024)).decode("UTF-8"))
                if not greeting_data.get('username') or not greeting_data.get("target_room"):
                    error_response = json.dumps(({"status":"error", "message": "data malformed"}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                    self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
                self.base_logger.info(f'greetings from {greeting_data.get("username")} {greeting_data}')

                location = greeting_data.get("target_room")
                if location == self.base_port:
                    error_response = json.dumps(({"status":"error", "message": "no"}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                else:
                    result_of_check = self.base_socket.connect_ex((("127.0.0.1", location)))
                    if result_of_check == 0:
                        room_response = json.dumps(({"status": "warning", "message": "no room found, opening new"}))
                        conn.send(room_response.encode("UTF-8"))
                        self.open_room(location)
                        self.add_room(location)
                        conn.close()
                    else:
                        room_data = self.collection.find_one({"ROOM": location})
                        if room_data and self.base_socket.getpeername() not in room_data.get("Blacklist"):
                            error_response = json.dumps(({"status": "success", "message": "connection allowed"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                        else:
                            error_response = json.dumps(({"status":"error", "message": "no room found"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
            except KeyboardInterrupt:
                try:
                    conn.close()
                    self.base_socket.close()
                    return
                except UnboundLocalError:
                    self.base_socket.close()
                    return

    def add_room(self, room):
        added_room = self.collection.insert_one({"ROOM": room, "Blacklist": [], "Whitelist": []})
        return added_room

    def open_room(self, port):
        room = room_socket(self.collection, port)
        room_thread = Thread(target=room.room_loop, args=())
        room_thread.start()
        room_thread.join()


server = room_server()
server.room_service()
