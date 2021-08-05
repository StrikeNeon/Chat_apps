import sys
from threading import Thread, Event
import socket
import json
import loguru
import schedule
from time import sleep
from room_object import room_socket
from mongo_utils import mongo_manager
from datetime import datetime, timedelta
from settings import ACCESS_TOKEN_EXPIRE_MINUTES
from simplejson.errors import JSONDecodeError
from PyQt5 import QtWidgets, QtWebSockets, QtGui, QtCore
from PyQt5.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
    QThread
)
import administration_ui as ui  # design file
from settings import ADMIN_LOGIN, ADMIN_PASSWORD
from loguru import logger

db_manager = mongo_manager()
_translate = QtCore.QCoreApplication.translate # this is here to translate ui dynamically

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


class main_reciever(QObject):
    finished = pyqtSignal()
    send_rooms = pyqtSignal(list)
    send_users = pyqtSignal(dict)

    def __init__(self, room_manager, ip=None, limit=10, port=6661):
        super().__init__()
        db_manager.flush_room_zero()
        self.base_logger = loguru.logger

        self.base_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.base_host_name = socket.gethostname()
        self.base_ip = socket.gethostbyname(self.base_host_name)
        self.base_port = port

        self.base_socket.bind((self.base_ip, self.base_port))
        self.base_logger.info("Binding successful!")
        self.base_logger.info(f"Base server bound to: {self.base_ip}:{self.base_port}")

        self.base_socket.listen(100)
        self.base_logger.info(f"Base server limit set at {100}")
        self.rooms = []
        self.users = {}
        self.running = True
        self._isRunning = True
        self.running = True
        self.room_manager = room_manager

    def login_required(func):
        def token_check(self, greeting_data, conn):
            if not greeting_data.get("token"):
                error_response = json.dumps(({"status": 403, "alert": "not logged in", "time": datetime.timestamp(datetime.now())}))
                conn.send(error_response.encode("UTF-8"))
                conn.close()
                return
            current_user = db_manager.verify_token(greeting_data.get('token'))
            if not current_user or current_user["username"] != greeting_data.get("username"):
                self.base_logger.debug(f'{current_user["username"], greeting_data.get("username")}')
                error_response = json.dumps(({"status": 403, "alert": "token error", "time": datetime.timestamp(datetime.now())}))
                conn.send(error_response.encode("UTF-8"))
                conn.close()
                return
            func(self, greeting_data, conn)
        return token_check

    def register_user(self, greeting_data, conn):
        if not greeting_data.get('username') or not greeting_data.get('password'):
            added = None
        else:
            added = db_manager.add_user(greeting_data.get('username'), greeting_data.get('password'), greeting_data.get('about_me'))
        if not added:
            error_response = json.dumps(({"status": 403, "alert": "already taken", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        else:
            error_response = json.dumps(({"status": 200, "alert": "registered user", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    def login_user(self, greeting_data, conn):
        if not greeting_data.get('username') or not greeting_data.get('password'):
            error_response = json.dumps(({"status": 400, "alert": "greeting data malformed", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        user_check = db_manager.check_user(greeting_data.get('username'), greeting_data.get('password'))
        if user_check:
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = db_manager.create_access_token(data={"sub": user_check["username"]},
                                                          expires_delta=access_token_expires)
            user_contacts = db_manager.get_contacts(greeting_data.get('username'))
            error_response = json.dumps(({"status": 200, "alert": f"logged {greeting_data.get('username')} in", "token": access_token, "contacts": user_contacts, "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        else:
            error_response = json.dumps(({"status": 400, "alert": "username or password is incorrect", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    @login_required
    def find_users(self, greeting_data, conn):
        if not greeting_data.get('contacts'):
            error_response = json.dumps(({"status": 400, "alert": "greeting data malformed", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        user_check = db_manager.find_users(greeting_data.get('contacts'))
        if user_check:
            error_response = json.dumps(({"status": 200, "alert": f"users found", "locations": user_check, "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        else:
            error_response = json.dumps(({"status": 202, "alert": "user wasn't found", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    @login_required
    def get_user_data(self, greeting_data, conn):
        if not greeting_data.get('username'):
            error_response = json.dumps(({"status": 400, "alert": "greeting data malformed", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        user_check = db_manager.find_user_record(greeting_data.get('username'))
        if user_check:
            error_response = json.dumps(({"status": 200, "alert": f"user {greeting_data.get('username')} found", "user_info": user_check, "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        elif user_check == 404:
            error_response = json.dumps(({"status": 404, "alert": "no user found", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        elif not user_check:
            error_response = json.dumps(({"status": 202, "alert": "user submitted no info", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    @login_required
    def get_room_data(self, greeting_data, conn):
        room_data = db_manager.get_room_data()
        if room_data:
            error_response = json.dumps(({"status": 200, "alert": "room data retrieved", "room_data": room_data, "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
        elif room_data == 500:
            error_response = json.dumps(({"status": 500, "alert": "server error", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()

    @login_required
    def greet(self, greeting_data, conn):
        if not greeting_data.get('username') or not greeting_data.get("target_room"):
            error_response = json.dumps(({"status": 400, "alert": "data malformed", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"malformed data at {conn}, data: {greeting_data}")
        if not greeting_data.get('token'):
            error_response = json.dumps(({"status": 403, "alert": "not logged in", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"non logged in user attempted to enter room|{conn}, data: {greeting_data}")
        self.base_logger.info(f'greetings from {greeting_data.get("username")} {greeting_data}')
        location = greeting_data.get("target_room")
        if location == self.base_port:
            error_response = json.dumps(({"status": 403, "alert": "no", "time": datetime.timestamp(datetime.now())}))
            conn.send(error_response.encode("UTF-8"))
            conn.close()
            self.base_logger.warning(f"{conn.getpeername()} tried to override base socket")
        else:
            room_data = db_manager.room_collection.find_one({"ROOM": location})
            self.base_logger.debug(f"queried data for {location}| {room_data}")
            if not room_data:
                self.base_logger.debug("no room found, creating")
                room_response = json.dumps(({"status": 201, "alert": "no room found, opening new", "time": datetime.timestamp(datetime.now())}))
                conn.send(room_response.encode("UTF-8"))
                self.users[greeting_data.get('username')] = location
                self.rooms.append(location)
                db_manager.add_user_to_room(conn.getpeername(), greeting_data.get('username'), location, self.users)
                self.users[greeting_data.get('username')] = location
                conn.send(room_response.encode("UTF-8"))
                self.send_users.emit(self.users)
                self.send_rooms.emit(self.rooms)
                conn.close()
                # self.base_logger.debug("no room found, creating")
                # room_response = json.dumps(({"status": 201, "alert": "no room found, opening new", "time": datetime.timestamp(datetime.now())}))
                # conn.send(room_response.encode("UTF-8"))
                # room_thread = Thread(target=self.open_room, args=([location]))
                # room_thread.start()
                # self.rooms.append((room_thread, location))
                # self.send_rooms.emit(self.rooms)
                # conn.close()
            else:
                if greeting_data.get('username') not in room_data.get("Blacklist"):
                    error_response = json.dumps(({"status": 200, "alert": "connection allowed", "time": datetime.timestamp(datetime.now())}))
                    result_of_check = self.base_socket.connect_ex((self.base_ip, location))
                    if result_of_check == 0:  # port open
                        self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                    else:
                        self.base_logger.info(f"recreated room {location}")
                        self.rooms.append(location)
                    self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                    db_manager.add_user_to_room(conn.getpeername(), greeting_data.get('username'), location, self.users)
                    self.users[greeting_data.get('username')] = location
                    conn.send(error_response.encode("UTF-8"))
                    self.send_rooms.emit(self.rooms)
                    self.send_users.emit(self.users)
                    conn.close()
                else:
                    error_response = json.dumps(({"status": 404, "alert": "no room found", "time": datetime.timestamp(datetime.now())}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                    self.base_logger.warning("user blacklisted")

    def send_user_signal(self):
        self.send_users.emit(self.users)

    def open_room(self, port):
        room = room_socket(self.base_ip, port)
        if not db_manager.room_collection.find_one({"ROOM": port}):
            self.base_logger.debug("creating_room")
            db_manager.add_room(port)
        room.room_loop()
        self.base_logger.info(f"room {port} closed")
        db_manager.remove_room(port)

    @pyqtSlot()
    def start(self):
        self.base_logger.debug("main loop started")
        while self.running:
            try:
                conn, add = self.base_socket.accept()

                self.base_logger.info(f"Received connection from {conn.getpeername()}")
                self.base_logger.info(f'Connection Established. Connected From: {conn.getpeername()}')
                greeting_data = json.loads((conn.recv(1024)).decode("UTF-8"))
                operation = greeting_data.get("action", None)
                if operation:
                    if operation == "login":
                        self.login_user(greeting_data, conn)
                    if operation == "GREETING":
                        self.greet(greeting_data, conn)
                    elif operation == "REG":
                        self.register_user(greeting_data, conn)
                    elif operation == "get_contact_locations":
                        self.find_users(greeting_data, conn)
                    elif operation == "get_user_info":
                        self.get_user_data(greeting_data, conn)
                    elif operation == "get_room_data":
                        self.get_room_data(greeting_data, conn)
                else:
                    error_response = json.dumps(({"status": 400, "alert": "no operation specified", "time": datetime.timestamp(datetime.now())}))
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
            self.rooms = []
            self.send_rooms.emit(self.rooms)
            room.join()
        self.finished.emit()


class administration_ui(QtWidgets.QMainWindow, ui.Ui_MainWindow):
    def __init__(self):
        # Это здесь нужно для доступа к переменным, методам
        # и т.д. в файле design.py
        super().__init__()
        self.setupUi(self)
        self.username = None
        self.password = None
        self.rooms = []

        self.start_server.clicked.connect(self.login)
        # self.db_reconnect_button.clicked.connect(self.reconnect_mongo)

    def login(self):
        if not self.username:
            self.username = self.login_input.text()
            self.password = self.password_input.text()
        if self.username == ADMIN_LOGIN and self.password == ADMIN_PASSWORD:
            self.switch_to_admin()
        else:
            sys.exit(1)

    def render_users(self, users):
        self.room_zero_tab.log_box.setText("\n".join([f"user {key} in {value}" for key, value in users.items()]))

    def render_rooms(self, rooms):
        self.room_zero_tab.user_counter.setNumDigits(len(rooms))
        if len(rooms) != len(self.rooms):
            location = rooms[-1]
            try:
                reciever_object = room_socket(ip=self.reciever_object.base_ip, port=location)
                new_room = ui.room_tab(self.room_manager)

                new_room.close_room_button.setText(_translate("MainWindow", "close room"))
                new_room.room_num_lable.setText(_translate("MainWindow", "room_num"))
                new_room.user_counter_lable.setText(_translate("MainWindow", "users online"))
                new_room.room_num_placeholder.setText(_translate("MainWindow", "placeholder_num"))
                new_room.label.setText(_translate("MainWindow", "room load"))

                self.room_manager.addTab(new_room, f'room_{location}_tab')
                reciever_thread = QThread()
                new_room.close_room_button.clicked.connect(reciever_object.close_server)
                # reciever_object.send_users.connect(self.send_user_signal)
                reciever_object.moveToThread(reciever_thread)
                reciever_object.finished.connect(reciever_thread.quit)
                reciever_thread.started.connect(reciever_object.room_loop)
                reciever_thread.start()
                self.rooms.append((reciever_thread, reciever_object))
            except OSError:
                pass

    def close_server(self):
        self.reciever_object.running = False

    def switch_to_admin(self):

        self.stackedWidget.setCurrentIndex(0)

        self.reciever_object = main_reciever(room_manager=self.room_manager, ip="127.0.0.1")

        self.reciever_thread = QThread()
        self.room_zero_tab.close_room_button.clicked.connect(self.close_server)
        self.reciever_object.send_rooms.connect(self.render_rooms)
        self.reciever_object.send_users.connect(self.render_users)
        self.reciever_object.moveToThread(self.reciever_thread)
        self.reciever_object.finished.connect(self.reciever_thread.quit)
        self.reciever_thread.started.connect(self.reciever_object.start)
        self.reciever_thread.start()

    def closeEvent(self, event):
        logger.info("exiting")
        try:
            self.reciever_object.running = False
            while not self.reciever_object._isRunning:
                sleep(2)
                logger.error("server thread still runs")
            self.reciever_thread.quit()
        except AttributeError:
            pass
        event.accept()  # let the window close


def main():
    app = QtWidgets.QApplication(sys.argv)
    admin_ui = administration_ui()
    admin_ui.show()
    sys.exit(app.exec_())

main()