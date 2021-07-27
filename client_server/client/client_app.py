import socket
import sys
import json
from simplejson.errors import JSONDecodeError
from PyQt5 import QtWidgets, QtWebSockets, QtGui
from PyQt5.QtCore import (
    QObject,
    pyqtSignal,
    pyqtSlot,
    QThread
)
import client_ui as ui  # design file
from loguru import logger
from datetime import datetime
from time import sleep


class reciever(QObject):
    finished = pyqtSignal()
    recieved_message = pyqtSignal(str)
    recount_users = pyqtSignal(dict)

    def __init__(self, socket, room):
        super().__init__()
        self._isRunning = True
        self.connected = True
        self.socket = socket
        self.room = room

    @pyqtSlot()
    def start(self):
        while self.connected:
            try:
                message = self.socket.recv(1024)
                # logger.debug(message.decode("UTF-8"))
                decoded_message = json.loads(message.decode("UTF-8"))
                if decoded_message.get("action", None) == "presence":
                    structured_message = {"action": "presence", "response": "here", "time": datetime.timestamp(datetime.now())}
                    self.socket.send(json.dumps(structured_message).encode("UTF-8"))
                # decrypted_message = self.decypher.decrypt(decoded_message.get('message'))
                elif  decoded_message.get("action", None) == "alert":
                    if decoded_message.get("status") == 201:
                        updated_users = {self.room: decoded_message.get("Users")}
                        self.recount_users.emit(updated_users)
                elif decoded_message.get('message') != "":
                    self.recieved_message.emit(f"message from: {decoded_message.get('from_user')}| {decoded_message.get('message')}")
            except json.decoder.JSONDecodeError:
                pass
            except ConnectionAbortedError:
                logger.warning("connection closed")
            sleep(0.2)


class client_ui(QtWidgets.QMainWindow, ui.Ui_MainWindow):
    def __init__(self):
        # Это здесь нужно для доступа к переменным, методам
        # и т.д. в файле design.py
        super().__init__()
        self.room_service = ("127.0.0.1", 6661)
        self.ip = "localhost"
        self.port = 9991
        self.setupUi(self)  # Это нужно для инициализации нашего дизайна
        self.username = None
        self.password = None
        self.token = None
        self.active_rooms = {}

        self.sign_in_button.clicked.connect(self.login)
        self.register_page_button.clicked.connect(self.switch_to_registration)
        self.room_manager_button.clicked.connect(self.switch_to_room_connector)
        self.return_to_rooms_button.clicked.connect(self.switch_to_room)
        self.login_page_button.clicked.connect(self.switch_to_startpage)
        self.register_button.clicked.connect(self.register)
        self.connect_to_room_button.clicked.connect(self.greet)
        self.send_all_button.clicked.connect(self.send_message)
        self.send_to_user_button.clicked.connect(self.send_message_to_user)
        self.send_quit_message.clicked.connect(self.send_quit)

    def make_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.bind(('', self.port))
        logger.debug(f"made socket |{client_socket}")
        return client_socket

    def switch_to_startpage(self):
        self.stackedWidget.setCurrentIndex(0)

    def switch_to_registration(self):
        self.stackedWidget.setCurrentIndex(1)

    def switch_to_room(self):
        self.stackedWidget.setCurrentIndex(2)

    def switch_to_room_connector(self):
        self.stackedWidget.setCurrentIndex(3)

    def send_message(self):
        message = self.message_input_box.toPlainText()
        if message:
            # encrypted_message = self.cypher.encrypt(bytes(message, encoding="utf-8"))
            structured_message = {"action": "MESSAGE",
                                  "at_user": "all",
                                  "from_user": (self.ip, self.port),
                                  "message": message,
                                  "time": datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
            self.add_message(f"you: {message}")

    def send_message_to_user(self):
        user = self.user_choice_box.currentText()
        message = self.message_input_box.toPlainText()
        if message and user:
            # encrypted_message = self.cypher.encrypt(bytes(message, encoding="utf-8"))
            structured_message = {"action": "MESSAGE",
                                  "at_user": user,
                                  "from_user": (self.ip, self.port),
                                  "message": message,
                                  "time": datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
            self.add_message(f"to {user}|you: {message}")

    def add_to_contacts(self):
        user = self.user_choice_box.currentText()
        if user:
            # encrypted_message = self.cypher.encrypt(bytes(message, encoding="utf-8"))
            structured_message = {"action": "add_to_con",
                                  "username": self.username,
                                  "add_user": user,
                                  "time": datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))

    def remove_from_contacts(self):
        user = self.user_choice_box.currentText()
        if user:
            # encrypted_message = self.cypher.encrypt(bytes(message, encoding="utf-8"))
            structured_message = {"action": "remove_from_con",
                                  "username": self.username,
                                  "remove_user": user,
                                  "time": datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))

    def send_quit(self):
        structured_message = {"action": "QUIT", "time": datetime.timestamp(datetime.now())}
        try:
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
            self.connected = False
            self.signal_to_reciever()
            self.client_socket.close()
        except OSError:
            pass

    def update_users(self, users):
        logger.debug(users)
        room = list(users.keys())[0]
        self.active_rooms[room] = users.get(room)
        self.user_choice_box.clear()
        self.user_choice_box.addItems(self.active_rooms[room].keys())

    def login(self):
        if self.port_input.text():
            try:
                self.port = int(self.port_input.text())
                self.client_socket = self.make_socket()
                self.client_socket.connect(self.room_service)
                logger.debug(f"connected to room service |{self.client_socket}")
                if self.username_input.text() and self.password_input.text():
                    greeting = {"action": "login",
                                "username": self.username_input.text(),
                                "password": self.password_input.text(),
                                "time": datetime.timestamp(datetime.now())}
                    self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
                    logger.debug("login data sent sent")
                    response = self.client_socket.recv(1024)
                    decoded_response = json.loads(response.decode("UTF-8"))
                    if decoded_response.get("status") == 200:
                        logger.debug(f"response recieved, closing {decoded_response}")
                        self.client_socket.close()
                        self.token = decoded_response.get("token")
                        self.username = self.username_input.text()
                        self.password = self.password_input.text()
                        self.switch_to_room_connector()
                    else:
                        logger.debug(f"response recieved, closing {decoded_response}")
            except ValueError:
                logger.error("port is not a number")

    def register(self):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        if self.username_input_reg.text() and self.username_input_reg.text():
            greeting = {"action": "REG", "username": self.username_input_reg.text(),
                        "password": self.password_input_reg.text(),
                        "about_me": self.about_me_input.toPlainText() if self.about_me_input.toPlainText() else "",
                        "time": datetime.timestamp(datetime.now())}
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

    def add_message(self, message):
        self.message_output_box.setText(message)

    def signal_to_reciever(self):
        self.reciever_object.connected = False
        self.reciever_thread.quit()
        self.switch_to_room_connector()
        # TODO while there is no tab mechanism - return to room connector
        # self.sender_thread.quit()

    def greet(self):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        greeting = {"action": "GREETING",
                    "username": self.username,
                    "password": self.password,
                    "target_room": int(self.room_number_input.text()),
                    "token": self.token,
                    "time": datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("greeting sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        logger.debug(f"response recieved, closing {decoded_response}")
        self.client_socket.close()
        
        if 200 >= decoded_response.get("status") < 300:

            self.client_socket = self.make_socket()
            self.client_socket.connect((self.room_service[0], int(self.room_number_input.text())))
            greeting = {"action": "GREETING",
                        "username": self.username,
                        "token": self.token,
                        "user_ip": [self.ip, self.port],
                        "time": datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
            logger.debug("greeting sent")
            response = self.client_socket.recv(1024)
            decoded_response = json.loads(response.decode("UTF-8"))
            if 200 >= decoded_response.get("status") < 300:
                logger.info("connected")
                self.active_rooms[self.room_number_input.text()] = decoded_response.get("Users")

                self.reciever_object = reciever(self.client_socket, self.room_number_input.text())

                self.reciever_thread = QThread()

                self.reciever_object.recieved_message.connect(self.add_message)
                self.reciever_object.recount_users.connect(self.update_users)
                self.reciever_object.moveToThread(self.reciever_thread)
                # self.reciever_object.finished.connect(self.reciever_thread.quit)
                self.reciever_thread.started.connect(self.reciever_object.start)
                self.reciever_thread.start()

                self.switch_to_room()
            else:
                self.client_socket.close()
                logger.error(f"not connected, {decoded_response}")
        else:
            self.client_socket.close()
            logger.error(f"not connected, {decoded_response}")

    def closeEvent(self, event):
        logger.info("exiting")
        event.accept()  # let the window close


def main():
    app = QtWidgets.QApplication(sys.argv)
    admin_ui = client_ui()
    admin_ui.show()
    sys.exit(app.exec_())


main()