import socket
import sys
import json
from simplejson.errors import JSONDecodeError
from PyQt5 import QtWidgets, QtWebSockets, QtGui
import client_ui as ui  # design file
from loguru import logger
from datetime import datetime


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

        self.sign_in_button.clicked.connect(self.switch_to_room_connector)
        self.register_page_button.clicked.connect(self.switch_to_registration)
        self.room_manager_button.clicked.connect(self.switch_to_room_connector)
        self.return_to_rooms_button.clicked.connect(self.switch_to_room)
        self.login_page_button.clicked.connect(self.login)
        self.register_button.clicked.connect(self.register)
        self.connect_to_room_button.clicked.connect(self.greet)
        # self.close_room_button.clicked.connect(self.register_user)
        # self.db_reconnect_button.clicked.connect(self.reconnect_mongo)

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

    def greet(self):
        self.client_socket = self.make_socket()
        self.client_socket.connect(self.room_service)
        logger.debug(f"connected to room service |{self.client_socket}")
        greeting = {"action": "GREETING", "username": self.username, "password": self.password, "target_room": self.room_number_input.text(), "token": self.token, "time":datetime.timestamp(datetime.now())}
        self.client_socket.send(json.dumps(greeting).encode("UTF-8"))
        logger.debug("greeting sent")
        response = self.client_socket.recv(1024)
        decoded_response = json.loads(response.decode("UTF-8"))
        logger.debug(f"response recieved, closing {decoded_response}")
        self.client_socket.close()
        self.switch_to_room()

    def closeEvent(self, event):
        logger.info("exiting")
        event.accept()  # let the window close


def main():
    app = QtWidgets.QApplication(sys.argv)
    admin_ui = client_ui()
    admin_ui.show()
    sys.exit(app.exec_())


main()