import sys
import json
from simplejson.errors import JSONDecodeError
from PyQt5 import QtWidgets, QtWebSockets, QtGui
import client_ui as ui  # design file
from loguru import logger


class client_ui(QtWidgets.QMainWindow, ui.Ui_MainWindow):
    def __init__(self):
        # Это здесь нужно для доступа к переменным, методам
        # и т.д. в файле design.py
        super().__init__()
        self.setupUi(self)  # Это нужно для инициализации нашего дизайна
        self.username = None
        self.password = None
        self.token = None

        self.sign_in_button.clicked.connect(self.switch_to_room_connector)
        self.register_page_button.clicked.connect(self.switch_to_registration)
        self.room_manager_button.clicked.connect(self.switch_to_room_connector)
        self.return_to_rooms_button.clicked.connect(self.switch_to_room)
        self.login_page_button.clicked.connect(self.switch_to_startpage)
        # self.close_room_button.clicked.connect(self.register_user)
        # self.db_reconnect_button.clicked.connect(self.reconnect_mongo)

    def switch_to_startpage(self):
        self.stackedWidget.setCurrentIndex(0)

    def switch_to_registration(self):
        self.stackedWidget.setCurrentIndex(1)

    def switch_to_room(self):
        self.stackedWidget.setCurrentIndex(2)

    def switch_to_room_connector(self):
        self.stackedWidget.setCurrentIndex(3)

    def closeEvent(self, event):
        logger.info("exiting")
        event.accept()  # let the window close



def main():
    app = QtWidgets.QApplication(sys.argv)
    admin_ui = client_ui()
    admin_ui.show()
    sys.exit(app.exec_())


main()