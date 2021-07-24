import sys
import json
from simplejson.errors import JSONDecodeError
from PyQt5 import QtWidgets, QtWebSockets, QtGui
import administration_ui as ui  # design file
from settings import ADMIN_LOGIN, ADMIN_PASSWORD
from loguru import logger


class administration_ui(QtWidgets.QMainWindow, ui.Ui_MainWindow):
    def __init__(self):
        # Это здесь нужно для доступа к переменным, методам
        # и т.д. в файле design.py
        super().__init__()
        self.setupUi(self)  # Это нужно для инициализации нашего дизайна
        self.username = None
        self.password = None

        self.start_server.clicked.connect(self.login)
        # self.close_room_button.clicked.connect(self.register_user)
        # self.db_reconnect_button.clicked.connect(self.reconnect_mongo)

    def login(self):
        if not self.username:
            self.username = self.login_input.text()
            self.password = self.password_input.text()
        if self.username == ADMIN_LOGIN and self.password == ADMIN_PASSWORD:
            self.switch_to_admin()
        else:
            sys.exit(1)

    def switch_to_admin(self):
        self.stackedWidget.setCurrentIndex(0)
        # from threading import Thread
        # from main_server_logic import room_server

        # server = room_server(ip="127.0.0.1")
        # room_thread = Thread(target=server.room_service, args=())
        # room_thread.start()
        # room_thread.join()

    def closeEvent(self, event):
        logger.info("exiting")
        event.accept()  # let the window close



def main():
    app = QtWidgets.QApplication(sys.argv)
    admin_ui = administration_ui()
    admin_ui.show()
    sys.exit(app.exec_())


main()