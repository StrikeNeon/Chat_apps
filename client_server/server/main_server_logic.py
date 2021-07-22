from threading import Thread, Event
import socket
import json
import loguru
import schedule
from time import sleep
from room_logic import room_socket
from mongo_utils import mongo_manager


db_manager = mongo_manager()


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


class room_server():
    def __init__(self, ip=None, limit=10, port=6661):
        db_manager.flush_room_zero()
        self.base_logger = loguru.logger

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
        self.users = {}
        self.running = True

    def register_user(self, greeting_data, conn):
        if not greeting_data.get('username') or not greeting_data.get('password'):
            added = None
        else:
            added = db_manager.add_user(greeting_data.get('username'), greeting_data.get('password'), greeting_data.get('info'))
        if not added:
            error_response = json.dumps(({"status": 403, "alert": "already taken"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        else:
            error_response = json.dumps(({"status":200, "alert": "registered user"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    def login_user(self, greeting_data, conn):
        if not greeting_data.get('username') or not greeting_data.get('password'):
            error_response = json.dumps(({"status": 400, "alert": "greeting data malformed"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        user_check = db_manager.check_user(greeting_data.get('username'), greeting_data.get('password'))
        if user_check:
            error_response = json.dumps(({"status": 200, "alert": f"logged {greeting_data.get('username')} in", "token": "token"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        else:
            error_response = json.dumps(({"status": 400, "alert": "username or password is incorrect"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    def find_user(self, greeting_data, conn):
        if not greeting_data.get('username'):
            error_response = json.dumps(({"status": 400, "alert": "greeting data malformed"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        user_check = db_manager.find_user(greeting_data.get('username'))
        if user_check:
            error_response = json.dumps(({"status": 200, "alert": f"user {greeting_data.get('username')} found", "location": user_check}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        else:
            error_response = json.dumps(({"status": 202, "alert": "user wasn't found"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    def greet(self, greeting_data, conn):
        if not greeting_data.get('username') or not greeting_data.get("target_room"):
            error_response = json.dumps(({"status": 400, "alert": "data malformed"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        if not greeting_data.get('token'):
            error_response = json.dumps(({"status": 403, "alert": "not logged in"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"non logged in user attempted to enter roo|{conn}, data: {greeting_data}")
        self.base_logger.info(f'greetings from {greeting_data.get("username")} {greeting_data}')
        location = greeting_data.get("target_room")
        if location == self.base_port:
            error_response = json.dumps(({"status": 403, "alert": "no"}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"{conn.getpeername()} tried to override base socket")
        else:
            room_data = db_manager.room_collection.find_one({"ROOM": location})
            self.base_logger.debug(f"queried data for {location}| {room_data}")
            if not room_data:
                self.base_logger.debug("no room found, creating")
                room_response = json.dumps(({"status": 201, "alert": "no room found, opening new"}))
                conn.send(room_response.encode("UTF-8"))
                room_thread = Thread(target=self.open_room, args=([location]))
                room_thread.start()
                self.rooms.append((room_thread, location))
                conn.close()
            else:
                if greeting_data.get('username') not in room_data.get("Blacklist"):
                    error_response = json.dumps(({"status": 200, "alert": "connection allowed"}))
                    result_of_check = self.base_socket.connect_ex((self.base_ip, location))
                    if result_of_check == 0:  # port open
                        self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                    else:
                        self.base_logger.info(f"recreated room {location}")
                        room_thread = Thread(target=self.open_room, args=([location]))
                        room_thread.start()
                        self.rooms.append((room_thread, location))
                    self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                    self.users[greeting_data.get('username')] = location
                    db_manager.add_user_to_room(conn.getpeername(), greeting_data.get('username'), location, self.users)
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                else:
                    error_response = json.dumps(({"status": 404, "alert": "no room found"}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                    self.base_logger.warning("user blacklisted")

    def room_service(self):
        self.base_logger.debug("main loop started")
        while self.running:
            try:
                conn, add = self.base_socket.accept()

                self.base_logger.info(f"Received connection from {conn.getpeername()}")
                self.base_logger.info(f'Connection Established. Connected From: {conn.getpeername()}')
                greeting_data = json.loads((conn.recv(1024)).decode("UTF-8"))
                operation = greeting_data.get("OPS", None)
                if operation:
                    if operation == "login":
                        self.login_user(greeting_data, conn)
                    if operation == "GREETING":
                        self.greet(greeting_data, conn)
                    elif operation == "REG":
                        self.register_user(greeting_data, conn)
                    elif operation == "find":
                        self.find_user(greeting_data, conn)
                else:
                    error_response = json.dumps(({"status": 400, "alert": "no operation specified"}))
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
        room = room_socket(self.base_ip, port)
        if not db_manager.room_collection.find_one({"ROOM": port}):
            self.base_logger.debug("creating_room")
            db_manager.add_room(port)
        room.room_loop()
        room.close()
        self.base_logger.info(f"room {port} closed")
        db_manager.remove_room(port)

    def shutdown(self):
        self.running = False
        self.base_socket.close()
