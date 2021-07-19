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
                                        self.users[greeting_data.get('username')] = location
                                        db_manager.add_user_to_room(conn.getpeername(), greeting_data.get('username'), location, self.users)
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
