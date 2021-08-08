import sys
from PyQt5 import QtWidgets
from administration_app import AdministrationUi


def main():
    app = QtWidgets.QApplication(sys.argv)
    admin_ui = AdministrationUi()
    admin_ui.show()
    sys.exit(app.exec_())


main()
