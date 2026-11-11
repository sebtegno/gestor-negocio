import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

from .database import init_db
from .ui.tema import aplicar_tema
from .actualizador import Actualizador


def _modo_recuperacion(app: QApplication, error_texto: str):
    """
    Si la ventana principal no puede abrirse (por ejemplo, por un error de una versión
    defectuosa), se busca igual una versión corregida para poder actualizar desde acá.
    """
    from .version import VERSION
    actualizador = Actualizador(None)
    app._actualizador = actualizador  # mantener vivo
    aviso = QMessageBox(QMessageBox.Warning, "La aplicación no pudo iniciar",
                        f"Hubo un error al abrir la versión {VERSION}.\n\n"
                        "Buscando una versión corregida en internet...\n"
                        "(Si hay una, te la va a ofrecer.)")
    aviso.setStandardButtons(QMessageBox.NoButton)
    aviso.show()
    app._aviso = aviso

    def sin_novedades():
        if getattr(actualizador, "_ofrecida", False):
            return
        aviso.close()
        QMessageBox.critical(None, "La aplicación no pudo iniciar",
                             "No se encontró una versión corregida.\n\n"
                             "Detalle del error:\n" + error_texto[-700:])
        app.quit()

    QTimer.singleShot(0, actualizador.comprobar)
    QTimer.singleShot(12000, sin_novedades)


def main():
    init_db()
    app = QApplication(sys.argv)
    aplicar_tema(app)
    try:
        from .ui.main_window import MainWindow
        ventana = MainWindow()
    except Exception:
        texto = traceback.format_exc()
        sys.excepthook(*sys.exc_info())  # lo anota en error.log
        _modo_recuperacion(app, texto)
        sys.exit(app.exec())
    ventana.show()
    actualizador = Actualizador(ventana)
    QTimer.singleShot(2000, actualizador.comprobar)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
