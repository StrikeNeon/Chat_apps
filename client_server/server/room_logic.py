from threading import Thread, Event
import socket
import select
import queue
import json
import loguru
import schedule
from time import sleep
from mongo_utils import mongo_manager
from datetime import datetime

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

    def log_online_users(self):
        if len(self.inputs) > 0:
            self.room_logger.info(f"users online: {len(self.inputs)-1}|  {self.inputs[1:]}")
        else:
            self.room_logger.error("Inputs ceased existing, but the loop still runs")

    def cleanup(self):
        self.room_logger.debug("checking activity")
        if len(self.inputs) == 1:
            self.inputs.pop(0)
            self.room_logger.info("room empty, unmaking")
            self.active = False
            self.room_logger.info("active status unset")

    def presence(self):
        timeout = 5
        closing = []
        self.room_logger.debug("sending presences")
        for check_socket in self.inputs:
            if check_socket is not self.room_socket:
                presence_message = {"action": "presence"}
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
        self.schedule_event = run_continuously()
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
        self.schedule_event.set()
        self.room_logger.debug("event running stopped")
        self.room_logger.info(f"room {self.room_port} closing")
        self.room_socket.close()

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
            operation = decoded_data.get("action", None)
            if not operation:
                error_response = json.dumps(({"status":400, "alert": "no operation specified", "time":datetime.timestamp(datetime.now())}))
                connection.send(error_response.encode("UTF-8"))

            if operation == "GREETING":
                username = decoded_data.get("username", None)
                user_ip = decoded_data.get("user_ip", None)
                if user_ip[0] == "localhost":
                    user_ip[0] = "127.0.0.1"
                if tuple(user_ip) != connection.getpeername():
                    self.room_logger.warning(f"ip mismatch on user {username}, ip {connection.getpeername()}, ip supplied {user_ip}")
                    error_response = json.dumps(({"status": 403, "alert": ")", "time":datetime.timestamp(datetime.now())}))
                    connection.send(error_response.encode("UTF-8"))
                else:
                    if decoded_data.get("token"):
                        verification = db_manager.verify_token(decoded_data.get("token"))
                        if not verification or verification["username"] != decoded_data.get("username"):
                            error_response = json.dumps(({"status": 403, "alert": "token error", "time":datetime.timestamp(datetime.now())}))
                            connection.send(error_response.encode("UTF-8"))
                            pass
                    else:
                        error_response = json.dumps(({"status": 403, "alert": "no token supplied", "time":datetime.timestamp(datetime.now())}))
                        connection.send(error_response.encode("UTF-8"))
                        pass
                    if username not in self.users.keys():
                        self.users[username] = decoded_data.get("user_ip", None)
                        self.inputs.append(connection)
                        # Give the connection a queue for data we want to send
                        self.message_queues[connection.getpeername()] = queue.Queue()
                        self.room_logger.info(f"new connection {connection.getpeername()}")
                        error_response = json.dumps(({"action": "alert", "status": 200, "alert": "user connected", "time":datetime.timestamp(datetime.now()), "Users": self.users}))
                        connection.send(error_response.encode("UTF-8"))
                    else:
                        error_response = json.dumps(({"status": 403, "alert": "non unique username", "time":datetime.timestamp(datetime.now())}))
                        connection.send(error_response.encode("UTF-8"))

        else:
            try:
                data = s.recv(1024)
            except (ConnectionResetError, ConnectionAbortedError):
                self.room_logger.info(f"user {s.getpeername()} quit")
                updated, deleted_user = db_manager.remove_user_from_room(s.getpeername(), self.room_port, self.users)
                if self.message_queues.get(deleted_user):
                    del self.message_queues[deleted_user]
                self.inputs.remove(s)
                self.room_logger.debug(f"user {s.getpeername()} queue deleted")
                self.room_logger.debug(f"socket {s.getpeername()} closed")
                for user in self.message_queues.keys():
                    self.message_queues[user].put({"action": "alert", "status": 201, "alert": f"User {s.getpeername()} quit", "Users": self.users})
            try:
                decoded_data = json.loads(data.decode("UTF-8"))
                self.room_logger.info(f"recieved message from {s.getpeername()}, {decoded_data}")
                operation = decoded_data.get("action", None)
                if not operation:
                    error_response = json.dumps(({"status": 400, "alert": "no operation specified", "time":datetime.timestamp(datetime.now())}))
                    s.send(error_response.encode("UTF-8"))
                if operation == "QUIT":
                    self.room_logger.info(f"user {s.getpeername()} quit")
                elif operation == "MESSAGE":
                    at_user = decoded_data.get("at_user", None)
                    if not at_user:
                        error_response = json.dumps(({"status": 400, "alert": "sent to noone", "time":datetime.timestamp(datetime.now())}))
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
                elif operation == "add_to_con":
                    if not decoded_data.get("username") or not decoded_data.get("add_user"):
                        error_response = json.dumps(({"status": 400, "alert": "some data was not sent", "time":datetime.timestamp(datetime.now())}))
                        s.send(error_response.encode("UTF-8"))
                    else:
                        db_manager.add_to_contacts(decoded_data.get("username"), decoded_data.get("add_user"))
                        error_response = json.dumps(({"status": 200, "alert": f"user {decoded_data.get('add_user')} added", "time": datetime.timestamp(datetime.now())}))
                        s.send(error_response.encode("UTF-8"))
                elif operation == "remove_from_con":
                    if not decoded_data.get("username") or not decoded_data.get("remove_user"):
                        error_response = json.dumps(({"status": 400, "alert": "some data was not sent", "time": datetime.timestamp(datetime.now())}))
                        s.send(error_response.encode("UTF-8"))
                    else:
                        db_manager.add_to_contacts(decoded_data.get("username"), decoded_data.get("remove_user"))
                        error_response = json.dumps(({"status": 200, "alert": f"user {decoded_data.get('remove_user')} removed", "time": datetime.timestamp(datetime.now())}))
                        s.send(error_response.encode("UTF-8"))
            except json.decoder.JSONDecodeError:
                self.room_logger.info(f"malformed message recieved from {s.getpeername()}")
                error_response = json.dumps(({"status": 500, "alert": "malformed", "time":datetime.timestamp(datetime.now())}))
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