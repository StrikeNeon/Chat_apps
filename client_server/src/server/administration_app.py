import sys
import socket
import json
import loguru
from time import sleep
from room_object import RoomSocket as room_socket
from mongo_utils import MongoManager as mongo_manager
from datetime import datetime, timedelta
from simplejson.errors import JSONDecodeError
from PyQt5 import QtWidgets, QtWebSockets, QtGui, QtCore
from PyQt5.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
    QThread
)
from administration_ui import Ui_MainWindow as ui  # design file
from administration_ui import room_tab as ui_room_tab  # design file
from settings import ADMIN_LOGIN, ADMIN_PASSWORD, ACCESS_TOKEN_EXPIRE_MINUTES
from loguru import logger

db_manager = mongo_manager()
_translate = QtCore.QCoreApplication.translate # this is here to translate ui dynamically


class MainReciever(QObject):
    """ws based message server - handles logins, registration and user greetings
       both this and room object only handle operation dispatch logic,
       all db-relevant operation code in in mongo utilities"""
    finished = pyqtSignal()
    send_rooms = pyqtSignal(list)
    """emiting this signal will open a new tab, starting a new room"""
    send_users = pyqtSignal(dict)
    """emiting this signal will send user dictionary for rendering in main thread"""

    def __init__(self, room_manager, limit=10, port=6661):
        super().__init__()
        db_manager.flush_room_zero()
        """room zero records purged on startup"""
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
        """decorator for jwt token verification"""
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
        """user registration method - verifies that user is unique,
           sends response if successful"""
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
        """verifies user data sent in message,
            creates jwt token and sends it on successful"""
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
        """seraches through room zero records,
           sends room locations of users in sender's contacts if found"""
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
        """retrieves user info (profile) from db"""
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
        """retrieves room data (user amount) from db"""
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
        """allows the user into room or creates a new one after verification
           also emits users signal and rooms signal if new room is created"""
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
            else:
                if greeting_data.get('username') not in room_data.get("Blacklist"):
                    error_response = json.dumps(({"status": 200, "alert": "connection allowed", "time": datetime.timestamp(datetime.now())}))
                    result_of_check = self.base_socket.connect_ex((self.base_ip, location))
                    if result_of_check == 0:  # port open
                        self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                    else:
                        self.base_logger.info(f"recreated room {location}")
                    self.base_logger.info(f"allowed user {greeting_data.get('username')} to connect to room {location}")
                    db_manager.add_user_to_room(conn.getpeername(), greeting_data.get('username'), location, self.users)
                    self.users[greeting_data.get('username')] = location
                    conn.send(error_response.encode("UTF-8"))
                    self.send_users.emit(self.users)
                    conn.close()
                else:
                    error_response = json.dumps(({"status": 404, "alert": "no room found", "time": datetime.timestamp(datetime.now())}))
                    conn.send(error_response.encode("UTF-8"))
                    conn.close()
                    self.base_logger.warning("user blacklisted")

    @pyqtSlot()
    def start(self):
        """This a main server loop - handles operations
           specified by operation key in message"""
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


class AdministrationUi(QtWidgets.QMainWindow, ui):
    def __init__(self):
        """Main admin app thread"""
        super().__init__()
        self.setupUi(self)
        self.rooms = []
        """a list of currently active rooms, tab management logic is using this for reference"""

        self.start_server.clicked.connect(self.login)
        # self.db_reconnect_button.clicked.connect(self.reconnect_mongo)

    def login(self):
        """verify with config or env variables"""
        username = self.login_input.text()
        password = self.password_input.text()
        if username == ADMIN_LOGIN and password == ADMIN_PASSWORD:
            self.switch_to_admin()
        else:
            sys.exit(1)

    def render_users(self, users):
        """transform users dict to string and show it in main tab"""
        self.room_zero_tab.log_box.setText("\n".join([f"user {key} in {value}" for key, value in users.items()]))

    def render_rooms(self, rooms):
        """this method will open a new room and add it's tab
           A room is a socket occupying a separate thread"""
        self.room_zero_tab.user_counter.setNumDigits(len(rooms))
        if len(rooms) != len(self.rooms):
            location = rooms[-1]
            try:
                reciever_object = room_socket(ip=self.reciever_object.base_ip, port=location, manager=self.room_manager)
                new_room = ui_room_tab(self.room_manager)

                new_room.close_room_button.setText(_translate("MainWindow", "close room"))
                new_room.room_num_lable.setText(_translate("MainWindow", "room_num"))
                new_room.user_counter_lable.setText(_translate("MainWindow", "users online"))
                new_room.room_num_placeholder.setText(_translate("MainWindow", "placeholder_num"))
                new_room.label.setText(_translate("MainWindow", "room load"))

                self.room_manager.addTab(new_room, f'room_{location}_tab')
                reciever_thread = QThread()
                new_room.close_room_button.clicked.connect(reciever_object.close_server)
                reciever_object.moveToThread(reciever_thread)
                reciever_object.finished.connect(reciever_thread.quit)
                reciever_thread.started.connect(reciever_object.room_loop)
                reciever_thread.start()
                reciever_object.room_index = self.room_manager.indexOf(new_room)
                self.rooms.append((reciever_thread, reciever_object))
            except OSError:
                pass

    def close_server(self):
        self.reciever_object.running = False

    def switch_to_admin(self):
        """Room zero will open on successful login. It's a preset socket at hostname:6661 in a separate thread"""

        self.stackedWidget.setCurrentIndex(0)

        self.reciever_object = MainReciever(room_manager=self.room_manager)

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
