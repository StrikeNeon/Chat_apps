from threading import Thread
import socket
import sys
import select
import queue
import json
from pymongo import MongoClient
import loguru
import schedule


class room_socket():
    def __init__(self, collection, ip, port, limit=10):
        self.room_logger = loguru.logger
        self.db_collection = collection
        self.room_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.room_ip = ip

        self.room_port = port

        self.room_socket.bind((self.room_ip, self.room_port))
        self.room_logger.info("Binding successful!")
        self.room_logger.info(f"Base server bound to: {self.room_ip}:{self.room_port}")

        self.room_socket.listen(limit)
        self.inputs = [self.room_socket]
        self.outputs = []
        self.message_queues = {}
        self.room_logger.info(f"Base server limit set at {limit}")
        self.message_queues["all"] = queue.Queue()

    def log_online_users(self):
        self.room_logger.info(f"users online: {len(self.inputs)}|  {self.inputs}")

    def cleanup(self):
        if len(self.inputs) == 1:
            self.room_logger.info("room empty, unmaking")
            self.room_socket.close()
            self.inputs.pop[0]

    def room_loop(self):
        schedule.every(10).minutes.do(self.log_online_users)
        schedule.every(10).minutes.do(self.cleanup)
        while self.inputs:
            schedule.run_pending()
            readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
            # Handle inputs
            for s in readable:

                if s is self.room_socket:
                    # A "readable" server socket is ready to accept a connection
                    connection, client_address = s.accept()
                    connection.setblocking(0)
                    self.inputs.append(connection)
                    self.room_logger.info(f"new connection {connection.getpeername()}")

                    # Give the connection a queue for data we want to send
                    self.message_queues[connection.getpeername()] = queue.Queue()
                else:
                    try:
                        data = s.recv(5120)
                    except ConnectionResetError:
                        data = None
                    if data:
                        try:
                            decoded_data = json.loads(data.decode("UTF-8"))
                            self.room_logger.info(f"recieved message from {s.getpeername()}, {decoded_data}")
                            operation = decoded_data.get("OPS", None)
                            if not operation:
                                error_response = json.dumps(({"error": "no operation specified"}))
                                self.message_queues[s.getpeername()].put(error_response.encode("UTF-8"))
                                continue
                            if operation == "QUIT":
                                del self.message_queues[s.getpeername()]
                                s.close()
                                self.inputs.remove(s)
                            elif operation == "MESSAGE":
                                at_user = decoded_data.get("at_user", None)
                                if not at_user:
                                    error_response = json.dumps(({"error": "sent to noone"}))
                                    self.message_queues[s.getpeername()].put(error_response.encode("UTF-8"))
                                    continue
                                # A readable client socket has data
                                self.message_queues[at_user].put(decoded_data)
                                self.room_logger.debug(f"queue for {at_user} {self.message_queues[at_user].queue}")
                                # Add output channel for response
                                if s not in self.outputs:
                                    self.outputs.append(s)
                        except json.decoder.JSONDecodeError:
                            self.room_logger.info(f"malformed message recieved from {connection.getpeername()}")
                    else:
                        pass
            # Handle outputs
            for s in writable:
                try:
                    next_msg = self.message_queues[s.getpeername()].get_nowait()
                    self.room_logger.info(f"sending message to {s.getpeername()}, {next_msg}")
                except queue.Empty:
                    # No messages waiting so stop checking for writability.
                    self.outputs.remove(s)
                except OSError:
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
        self.remove_room(self.room_port)
        self.room_socket.close()
        self.room_logger.info(f"room {self.room_port} closed")


class room_server():
    def __init__(self, ip=None, limit=1, port=6661):
        self.base_logger = loguru.logger
        self.client = MongoClient('127.0.0.1:27017')

        self.db = self.client['chat_apps']
        self.collection = self.db['client-server']

        self.base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if not ip:
            self.base_host_name = socket.gethostname()
            self.base_ip = socket.gethostbyname(self.base_host_name)
        else:
            self.base_ip = ip

        self.base_port = port

        self.base_socket.bind((self.base_ip, self.base_port))
        self.base_logger.info("Binding successful!")
        self.base_logger.info(f"Base server bound to: {self.base_ip}:{self.base_port}")

        self.base_socket.listen(limit)
        self.base_logger.info(f"Base server limit set at {limit}")

    def room_service(self):
        self.base_logger.debug("main loop started")
        while True:
            try:
                conn, add = self.base_socket.accept()

                self.base_logger.info(f"Received connection from {conn.getpeername()}")
                self.base_logger.info(f'Connection Established. Connected From: {conn.getpeername()}')
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
                    self.base_logger.warning(f"{conn.getpeername()} tried to override base socket")
                else:
                    room_data = self.collection.find_one({"ROOM": location})
                    self.base_logger.debug(room_data)
                    if not room_data:
                        room_response = json.dumps(({"status": "warning", "message": "no room found, opening new"}))
                        conn.send(room_response.encode("UTF-8"))
                        self.open_room(location)
                        conn.close()
                    else:
                        if conn.getpeername() not in room_data.get("Blacklist"):
                            error_response = json.dumps(({"status": "success", "message": "connection allowed"}))
                            result_of_check = self.base_socket.connect_ex((self.base_ip, location))
                            if result_of_check == 0: # port open
                                self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                            else:
                                self.base_logger.info(f"recreated room {location}")
                                self.open_room(location)
                            self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                        else:
                            error_response = json.dumps(({"status":"error", "message": "no room found"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                            self.base_logger.warning("user blacklisted")
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
        self.base_logger.info(f"created room records, room № {room}")
        return added_room

    def remove_room(self, room):
        added_room = self.collection.delete_one({"ROOM": room})
        self.base_logger.info(f"deleted records, room № {room}")
        return added_room

    def open_room(self, port):
        room = room_socket(self.collection, self.base_ip, port)
        room_thread = Thread(target=room.room_loop, args=())
        room_thread.start()
        if not self.collection.find({"ROOM":port}):
            self.add_room(port)
        room_thread.join()
        self.remove_room(port)

    def shutdown(self):
        self.base_socket.close()


server = room_server(ip="127.0.0.1")
room_thread = Thread(target=server.room_service, args=())
room_thread.start()
room_thread.join()
