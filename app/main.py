import sys

from PySide6.QtWidgets import QApplication

from .database import init_db
from .ui.main_window import MainWindow
from .ui.tema import aplicar_tema
from .actualizador import Actualizador
from PySide6.QtCore import QTimer


def main():
    init_db()
    app = QApplication(sys.argv)
    aplicar_tema(app)
    ventana = MainWindow()
    ventana.show()
    actualizador = Actualizador(ventana)
    QTimer.singleShot(2000, actualizador.comprobar)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
