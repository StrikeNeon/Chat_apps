from threading import Thread, Event
import socket
import select
import queue
import json
from pymongo import MongoClient, ReturnDocument
import loguru
import schedule
from time import sleep


def run_continuously(interval=1):
    """Continuously run, while executing pending jobs at each
    elapsed time interval.
    @return cease_continuous_run: threading. Event which can
    be set to cease continuous run. Please note that it is
    *intended behavior that run_continuously() does not run
    missed jobs*. For example, if you've registered a job that
    should run every minute and you set a continuous run
    interval of one hour then your job won't be run 60 times
    at each interval but only once.
    """
    cease_continuous_run = Event()

    class ScheduleThread(Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


class mongo_manager():
    def __init__(self):
        self.client = MongoClient('127.0.0.1:27017')

        self.db = self.client['chat_apps']
        self.room_collection = self.db['client-server_rooms']
        self.user_collection = self.db['client-server_users']
        self.archive_collection = self.db['client-server_archival']

        self.db_logger = loguru.logger

    def add_room(self, room):
        added_room = self.room_collection.insert_one({"ROOM": room, "Blacklist": [], "Whitelist": [], "Users": {}}).inserted_id
        self.db_logger.info(f"created room records, room № {room}")
        return added_room

    def remove_room(self, room):
        self.room_collection.delete_one({"ROOM": room})
        self.db_logger.info(f"deleted records, room № {room}")

    def add_user(self, username, password, user_data):
        user_check = self.user_collection.find_one({"username": username})
        if not user_check:
            added = self.user_collection.insert_one({"username": username, "password": password, "info": user_data, "contacts": []})
            return added
        else:
            return None

    def remove_user(self, username):
        self.user_collection.delete_one({"username": username})

    def check_user(self, username, password):
        user_check = self.user_collection.find_one({"username": username})
        if user_check:
            self.db_logger.debug(f"found user {username}")
            if user_check.get("username") == username and user_check.get("password") == password:
                return True
            else:
                self.db_logger.info(f"failed, recorded name: {user_check.get('username')} supplied name: {username}, recorded password: {user_check.get('password')} supplied password: {password}")

    def add_user_to_room(self, user_ip, username, room_port, users):
        users[username] = {"user_location": user_ip, "username": username}
        updated = self.room_collection.find_one_and_update({"ROOM": room_port}, {'$set': {"Users": users}}, return_document=ReturnDocument.AFTER)
        return users, updated

    def remove_user_from_room(self, user_ip, room_port, users):
        for user in users.values():
            if tuple(user.get("user_location")) == user_ip:
                to_delete = user.get("username")
                break
        users.pop(to_delete)
        self.db_logger.debug(f"after cleaning {users}")
        self.room_collection.find_one_and_update({"ROOM": room_port}, {'$set': {"Users": users}})
        self.room_collection.find_one_and_update({"ROOM": 0}, {'$set': {"Users": users}})
        return users, to_delete

    def delete_user(self, username):
        self.user_collection.delete_one({"username": username})
        self.db_logger.info(f"deleted user {username}")

    def add_to_contacts(self, username, other_username):
        updated = self.user_collection.find_one_and_update({"username": username}, {'$push': {"contacts": other_username}}, return_document=ReturnDocument.AFTER)
        return updated

    def remove_from_contacts(self, username, other_username):
        updated = self.user_collection.find_one_and_update({"username": username}, {'$pull': {"contacts": other_username}}, return_document=ReturnDocument.AFTER)
        return updated

    def recount_users(self, users):
        updated = self.room_collection.find_one_and_update({"ROOM": 0}, {'$set': {"Users": users}}, return_document=ReturnDocument.AFTER)
        return updated


class room_socket():
    def __init__(self, ip, port, limit=10):
        self.room_logger = loguru.logger
        self.db_manager = mongo_manager()
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
        self.users = {}
        self.active = True

    def close(self):
        self.room_socket.close()

    def log_online_users(self):
        if len(self.inputs) > 0:
            self.room_logger.info(f"users online: {len(self.inputs)-1}|  {self.inputs[1:]}")
        else:
            self.room_logger.error("Inputs ceased existing, but the loop still runs")

    def cleanup(self):
        self.room_logger.debug("checking activity")
        if len(self.inputs) == 1:
            self.room_logger.info("room empty, unmaking")
            self.active = False
            return

    def presence(self):
        timeout = 5
        closing = []
        self.room_logger.debug("sending presences")
        for check_socket in self.inputs:
            if check_socket is not self.room_socket:
                presence_message = {"OPS": "presence"}
                try:
                    check_socket.send(json.dumps(presence_message).encode("UTF-8"))
                    data = check_socket.recv(1024)
                except ConnectionError:
                    closing.append(check_socket)
                    continue
                while not data:
                    if timeout == 0:
                        closing.append(check_socket)
                    sleep(1)
                    timeout -= 1
                decoded_data = json.loads(data.decode("UTF-8"))
                if decoded_data.get("response", None) == "here":
                    continue
                else:
                    closing.append(check_socket)
        for closing_socket in closing:
            self.inputs.remove(closing_socket)

    def room_loop(self):
        schedule.every(5).minutes.do(self.log_online_users)
        schedule.every(5).minutes.do(self.presence)
        schedule.every(1).minutes.do(self.cleanup)
        stop_run_continuously = run_continuously()
        while self.active:
            readable, writable, exceptional = select.select(self.inputs, self.outputs, self.inputs)
            # Handle inputs
            for s in readable:
                self.recieve_data(s)
            # TODO figure out that weird queue block error
            # Handle outputs
            for s in writable:
                self.send_data(s)

            # Handle "exceptional conditions"
            for s in exceptional:
                self.handle_error(s)
            sleep(0.2)
        self.room_logger.debug("room loop exited")
        stop_run_continuously.set()
        self.room_logger.debug("event running stopped")
        self.room_logger.info(f"room {self.room_port} closing")
        return

    def send_data(self, s):
        self.room_logger.debug(f"sending message to {s.getpeername()}")
        try:
            next_msg = self.message_queues[s.getpeername()].get_nowait()
            if next_msg.get("at_user") == "all":
                next_msg = self.message_queues["all"].get_nowait()
                for connection in self.inputs:
                    if connection != self.room_socket:
                        self.room_logger.debug(f"sent to {s}")
                        connection.send(json.dumps(next_msg).encode("UTF-8"))
            else:
                for connection in self.inputs:
                    if connection != self.room_socket:
                        if connection.getpeername() == next_msg.get("at_user"):
                            self.room_logger.debug(f"sent to {s}")
                            connection.send(json.dumps(next_msg).encode("UTF-8"))
        except queue.Empty:
            # No messages waiting so stop checking for writability.
            self.room_logger.warning(f"socket {s.getpeername()} queue empty")
            self.outputs.remove(s)
        except OSError:
            # No messages waiting so stop checking for writability.
            self.room_logger.warning(f"socket {s.getpeername()} probably disconnected")
            self.outputs.remove(s)

    def recieve_data(self, s):
        if s is self.room_socket:
            # A "readable" server socket is ready to accept a connection
            connection, client_address = s.accept()
            connection.setblocking(0)
            data = connection.recv(1024)
            decoded_data = json.loads(data.decode("UTF-8"))
            operation = decoded_data.get("OPS", None)
            if not operation:
                error_response = json.dumps(({"error": "no operation specified"}))
                connection.send(error_response.encode("UTF-8"))

            if operation == "GREETING":
                username = decoded_data.get("username", None)
                user_ip = decoded_data.get("user_ip", None)
                if user_ip[0] == "localhost":
                    user_ip[0] = "127.0.0.1"
                if tuple(user_ip) != connection.getpeername():
                    self.room_logger.warning(f"ip mismatch on user {username}, ip {connection.getpeername()}, ip supplied {user_ip}")
                    error_response = json.dumps(({"status": "error", "message": ")"}))
                    connection.send(error_response.encode("UTF-8"))
                if user_ip and username not in self.users.keys():
                    self.users, updated = db_manager.add_user_to_room(user_ip, username, self.room_ip, self.users)
                    self.inputs.append(connection)
                    # Give the connection a queue for data we want to send
                    self.message_queues[connection.getpeername()] = queue.Queue()
                    self.room_logger.info(f"new connection {connection.getpeername()}")
                    error_response = json.dumps(({"status":"success","message": "user connected"}))
                    connection.send(error_response.encode("UTF-8"))
                else:
                    error_response = json.dumps(({"status": "error", "message": "non unique username"}))
                    connection.send(error_response.encode("UTF-8"))

        else:
            try:
                data = s.recv(1024)
            except ConnectionResetError:
                self.room_logger.info(f"user {s.getpeername()} quit")
                updated, deleted_user = db_manager.remove_user_from_room(s.getpeername(), self.room_ip, self.users)
                del self.message_queues[deleted_user]
                self.inputs.remove(s)
                self.room_logger.debug(f"user {s.getpeername()} queue deleted")
                self.room_logger.debug(f"socket {s.getpeername()} closed")
            try:
                decoded_data = json.loads(data.decode("UTF-8"))
                self.room_logger.info(f"recieved message from {s.getpeername()}, {decoded_data}")
                operation = decoded_data.get("OPS", None)
                if not operation:
                    error_response = json.dumps(({"status":"error","message": "no operation specified"}))
                    s.send(error_response.encode("UTF-8"))
                if operation == "QUIT":
                    self.room_logger.info(f"user {s.getpeername()} quit")
                elif operation == "MESSAGE":
                    at_user = decoded_data.get("at_user", None)
                    if not at_user:
                        error_response = json.dumps(({"status":"error", "message": "sent to noone"}))
                        s.send(error_response.encode("UTF-8"))
                    if at_user == "all":
                        for user in self.message_queues.keys():
                            self.message_queues[user].put(decoded_data)
                            self.room_logger.debug(f"queue for {at_user} {self.message_queues[user].queue}")
                    else:
                        # A readable client socket has data
                        self.message_queues[at_user].put(decoded_data)
                    # Add output channel for response
                    if s not in self.outputs:
                        self.outputs.append(s)
            except json.decoder.JSONDecodeError:
                self.room_logger.info(f"malformed message recieved from {connection.getpeername()}")
                error_response = json.dumps(({"status": "error", "message": "malformed"}))
                s.send(error_response.encode("UTF-8"))
            except UnboundLocalError:
                pass

    def handle_error(self, s):
        # Stop listening for input on the connection
        updated, deleted_user = db_manager.remove_user_from_room(s.getpeername(), self.room_ip, self.users)
        self.inputs.remove(s)
        if s in self.outputs:
            self.outputs.remove(s)
        s.close()

        # Remove message queue
        del self.message_queues[deleted_user]


class room_server():
    def __init__(self, ip=None, limit=10, port=6661):
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
        self.rooms = []
        self.users = []

    def room_service(self):
        self.base_logger.debug("main loop started")
        while True:
            try:
                conn, add = self.base_socket.accept()

                self.base_logger.info(f"Received connection from {conn.getpeername()}")
                self.base_logger.info(f'Connection Established. Connected From: {conn.getpeername()}')
                greeting_data = json.loads((conn.recv(1024)).decode("UTF-8"))
                operation = greeting_data.get("OPS", None)
                if operation:
                    if operation == "GREETING":
                        if not greeting_data.get('username') or not greeting_data.get('password') or not greeting_data.get("target_room"):
                            error_response = json.dumps(({"status": "error", "message": "data malformed"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
                        self.base_logger.info(f'greetings from {greeting_data.get("username")} {greeting_data}')
                        user_validation = db_manager.check_user(greeting_data.get('username'), greeting_data.get('password'))
                        if user_validation:
                            location = greeting_data.get("target_room")
                            if location == self.base_port:
                                error_response = json.dumps(({"status": "error", "message": "no"}))
                                conn.send(error_response.encode("UTF-8"))
                                conn.close()
                                self.base_logger.warning(f"{conn.getpeername()} tried to override base socket")
                            else:
                                room_data = db_manager.room_collection.find_one({"ROOM": location})
                                self.base_logger.debug(f"queried data for {location}| {room_data}")
                                if not room_data:
                                    self.base_logger.debug("no room found, creating")
                                    room_response = json.dumps(({"status": "warning", "message": "no room found, opening new"}))
                                    conn.send(room_response.encode("UTF-8"))
                                    room_thread = Thread(target=self.open_room, args=([location]))
                                    room_thread.start()
                                    self.rooms.append((room_thread, location))
                                    conn.close()
                                else:
                                    if greeting_data.get('username') not in room_data.get("Blacklist"):
                                        error_response = json.dumps(({"status": "success", "message": "connection allowed"}))
                                        result_of_check = self.base_socket.connect_ex((self.base_ip, location))
                                        if result_of_check == 0:  # port open
                                            self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                                        else:
                                            self.base_logger.info(f"recreated room {location}")
                                            room_thread = Thread(target=self.open_room, args=([location]))
                                            room_thread.start()
                                            self.rooms.append((room_thread, location))
                                        self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                                        self.users.append([greeting_data.get('username'), location])
                                        db_manager.recount_users(self.users)
                                        conn.send(error_response.encode("UTF-8"))
                                        conn.close()
                                    else:
                                        error_response = json.dumps(({"status": "error", "message": "no room found"}))
                                        conn.send(error_response.encode("UTF-8"))
                                        conn.close()
                                        self.base_logger.warning("user blacklisted")
                        else:
                            error_response = json.dumps(({"status": "error", "message": "username or password is incorrect"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                    elif operation == "REG":
                        if not greeting_data.get('username') or not greeting_data.get('password'):
                            added = None
                        else:
                            added = db_manager.add_user(greeting_data.get('username'), greeting_data.get('password'), greeting_data.get('info'))
                        if not added:
                            error_response = json.dumps(({"status": "error", "message": "already taken"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                        else:
                            error_response = json.dumps(({"status":"success", "message": "registered user"}))
                            conn.send(error_response.encode("UTF-8"))
                            conn.close()
                else:
                    error_response = json.dumps(({"status":"error", "message": "no operation specified"}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                    self.base_logger.warning("no operation specified")
            except KeyboardInterrupt:
                try:
                    conn.close()
                    self.base_socket.close()
                    return
                except UnboundLocalError:
                    self.base_socket.close()
                    return
        for room in self.rooms:  # server closed, close all rooms
            room.join()

    def open_room(self, port):
        try:
            room = room_socket(self.base_ip, port)
            if not db_manager.room_collection.find_one({"ROOM": port}):
                self.base_logger.debug("creating_room")
                db_manager.add_room(port)
            room.room_loop()
            room.close()
            self.base_logger.info(f"room {port} closed")
            db_manager.remove_room(port)
        except Exception as ex:
            self.base_logger.error(ex)

    def shutdown(self):
        self.base_socket.close()


server = room_server(ip="127.0.0.1")
db_manager = mongo_manager()
room_thread = Thread(target=server.room_service, args=())
room_thread.start()
room_thread.join()
