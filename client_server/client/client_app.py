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

    def __init__(self, socket):
        super().__init__()
        self._isRunning = True
        self.connected = True
        self.socket = socket

    @pyqtSlot()
    def start(self):
        while self.connected:
            try:
                message = self.socket.recv(1024)
                # logger.debug(message.decode("UTF-8"))
                decoded_message = json.loads(message.decode("UTF-8"))
                if decoded_message.get("action", None) == "presence":
                    structured_message = {"action": "presence", "response": "here", "time":datetime.timestamp(datetime.now())}
                    self.socket.send(json.dumps(structured_message).encode("UTF-8"))
                # decrypted_message = self.decypher.decrypt(decoded_message.get('message'))
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

        self.sign_in_button.clicked.connect(self.login)
        self.register_page_button.clicked.connect(self.switch_to_registration)
        self.room_manager_button.clicked.connect(self.switch_to_room_connector)
        self.return_to_rooms_button.clicked.connect(self.switch_to_room)
        self.login_page_button.clicked.connect(self.switch_to_startpage)
        self.register_button.clicked.connect(self.register)
        self.connect_to_room_button.clicked.connect(self.greet)
        self.send_all_button.clicked.connect(self.send_message)
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
            structured_message = {"action": "MESSAGE", "at_user": "all", "from_user": (self.ip, self.port), "message": message, "time":datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
            self.add_message(f"you: {message}")

    def send_quit(self):
        structured_message = {"action": "QUIT", "time":datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(structured_message).encode("UTF-8"))
        self.connected = False
        self.signal_to_reciever()
        self.client_socket.close()

    def login(self):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        if self.username_input.text() and self.password_input.text():
            greeting = {"action": "login", "username": self.username_input.text(), "password": self.password_input.text(), "time":datetime.timestamp(datetime.now())}
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

    def register(self):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        if self.username_input_reg.text() and self.username_input_reg.text():
            greeting = {"action": "REG", "username": self.username_input_reg.text(), "password": self.username_input_reg.text(), "about_me": self.about_me_input.text() if self.about_me_input.text() else "", "time":datetime.timestamp(datetime.now())}
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
        greeting = {"action": "GREETING", "username": self.username, "password": self.password, "target_room": int(self.room_number_input.text()), "token": self.token, "time": datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("greeting sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        logger.debug(f"response recieved, closing {decoded_response}")
        self.client_socket.close()
        
        if decoded_response.get("status") == 200:

            self.client_socket = self.make_socket()
            self.client_socket.connect((self.room_service[0], int(self.room_number_input.text())))
            greeting = {"action": "GREETING", "username": self.username, "user_ip": [self.ip, self.port], "time": datetime.timestamp(datetime.now())}
            self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
            logger.debug("greeting sent")
            response = self.client_socket.recv(1024)
            decoded_response = json.loads(response.decode("UTF-8"))
            if decoded_response.get("status") == 200:
                logger.info("connected")

                self.reciever_object = reciever(self.client_socket)

                self.reciever_thread = QThread()

                self.reciever_object.recieved_message.connect(self.add_message)
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