import sys
from PyQt5 import QtWidgets
from client_app import ClientUi


def main():
    app = QtWidgets.QApplication(sys.argv)
    client_ui = ClientUi()
    client_ui.show()
    sys.exit(app.exec_())


main()
