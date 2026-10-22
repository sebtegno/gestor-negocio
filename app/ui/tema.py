"""
Tema visual de la aplicación (hoja de estilos Qt + paleta clara).
Todos los colores salen de app/marca.py.
"""
from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication, QDialog

from .. import marca as m


def hoja_de_estilos() -> str:
    return f"""
    * {{
        font-family: {m.FUENTE};
        font-size: 13px;
    }}

    QMainWindow {{
        background: {m.COLOR_FONDO};
    }}
    QDialog, QMessageBox {{
        background: {m.COLOR_FONDO_DIALOGO};
    }}

    QWidget#contenido {{
        background: {m.COLOR_FONDO};
    }}

    QLabel {{
        color: {m.COLOR_TEXTO};
        background: transparent;
    }}
    QCheckBox {{
        color: {m.COLOR_TEXTO};
        background: transparent;
    }}

    /* ---- Cabecera ---- */
    QWidget#cabecera {{
        background: {m.COLOR_OSCURO};
    }}
    QLabel#tituloCabecera {{
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 700;
    }}
    QLabel#subtituloCabecera {{
        color: #C9D3E0;
        font-size: 12px;
    }}

    /* ---- Pestañas como menú de navegación ---- */
    QTabWidget::pane {{
        border: none;
        background: {m.COLOR_FONDO};
    }}
    QTabBar {{
        background: {m.COLOR_TARJETA};
    }}
    QTabBar::tab {{
        background: transparent;
        color: {m.COLOR_TEXTO};
        padding: 12px 20px;
        font-weight: 600;
        border-bottom: 3px solid transparent;
    }}
    QTabBar::tab:hover {{
        color: {m.COLOR_ACENTO_HOVER};
    }}
    QTabBar::tab:selected {{
        color: {m.COLOR_ACENTO};
        border-bottom: 3px solid {m.COLOR_ACENTO};
    }}

    /* Pestañas dentro de ventanas emergentes (ej. datos del cliente) */
    QDialog QTabWidget::pane {{
        border: 1px solid {m.COLOR_BORDE};
        background: {m.COLOR_FONDO_DIALOGO};
    }}
    QDialog QTabBar {{
        background: transparent;
    }}

    /* ---- Botones ---- */
    QPushButton {{
        background: {m.COLOR_TARJETA};
        color: {m.COLOR_ACENTO};
        border: 1px solid {m.COLOR_ACENTO};
        border-radius: 6px;
        padding: 7px 16px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background: {m.COLOR_ACENTO_SUAVE};
    }}
    QPushButton:pressed {{
        background: {m.COLOR_ACENTO};
        color: #FFFFFF;
    }}
    QPushButton[rol="primario"] {{
        background: {m.COLOR_ACENTO};
        color: #FFFFFF;
        border: 1px solid {m.COLOR_ACENTO};
    }}
    QPushButton[rol="primario"]:hover {{
        background: {m.COLOR_ACENTO_HOVER};
        border: 1px solid {m.COLOR_ACENTO_HOVER};
    }}
    QPushButton[rol="peligro"] {{
        color: {m.COLOR_PELIGRO};
        border: 1px solid {m.COLOR_PELIGRO};
    }}
    QPushButton[rol="peligro"]:hover {{
        background: {m.COLOR_PELIGRO};
        color: #FFFFFF;
    }}

    /* ---- Campos de entrada ---- */
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background: {m.COLOR_TARJETA};
        color: {m.COLOR_TEXTO};
        border: 1px solid {m.COLOR_BORDE};
        border-radius: 6px;
        padding: 6px 8px;
        selection-background-color: {m.COLOR_ACENTO_SUAVE};
        selection-color: {m.COLOR_TEXTO};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {m.COLOR_ACENTO};
    }}
    QComboBox QAbstractItemView {{
        background: {m.COLOR_TARJETA};
        color: {m.COLOR_TEXTO};
        selection-background-color: {m.COLOR_ACENTO_SUAVE};
        selection-color: {m.COLOR_TEXTO};
        border: 1px solid {m.COLOR_BORDE};
    }}

    /* ---- Tablas ---- */
    QTableWidget {{
        background: {m.COLOR_TARJETA};
        color: {m.COLOR_TEXTO};
        gridline-color: {m.COLOR_BORDE};
        border: 1px solid {m.COLOR_BORDE};
        border-radius: 6px;
        selection-background-color: {m.COLOR_ACENTO_SUAVE};
        selection-color: {m.COLOR_TEXTO};
    }}
    QHeaderView::section {{
        background: {m.COLOR_OSCURO};
        color: #FFFFFF;
        padding: 8px;
        border: none;
        font-weight: 600;
    }}

    /* ---- Tarjetas ---- */
    QFrame#tarjeta {{
        background: {m.COLOR_TARJETA};
        border: 1px solid {m.COLOR_BORDE};
        border-radius: 10px;
    }}

    QToolTip {{
        background: {m.COLOR_OSCURO};
        color: #FFFFFF;
        border: none;
        padding: 4px 8px;
    }}
    """


def _paleta_clara() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(m.COLOR_FONDO))
    p.setColor(QPalette.WindowText, QColor(m.COLOR_TEXTO))
    p.setColor(QPalette.Base, QColor(m.COLOR_TARJETA))
    p.setColor(QPalette.AlternateBase, QColor(m.COLOR_FONDO))
    p.setColor(QPalette.Text, QColor(m.COLOR_TEXTO))
    p.setColor(QPalette.Button, QColor(m.COLOR_TARJETA))
    p.setColor(QPalette.ButtonText, QColor(m.COLOR_TEXTO))
    p.setColor(QPalette.ToolTipBase, QColor(m.COLOR_OSCURO))
    p.setColor(QPalette.ToolTipText, QColor("#FFFFFF"))
    p.setColor(QPalette.Highlight, QColor(m.COLOR_ACENTO))
    p.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    return p


class _FondoDeDialogos(QObject):
    """
    Al mostrarse cualquier ventana emergente (QDialog), le pone el fondo gris.
    Se hace por paleta además de por hoja de estilos para que funcione
    también en los diálogos propios, sin tocar cada clase.
    """

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Show and isinstance(obj, QDialog):
            paleta = obj.palette()
            paleta.setColor(QPalette.Window, QColor(m.COLOR_FONDO_DIALOGO))
            obj.setPalette(paleta)
            obj.setAutoFillBackground(True)
        return False


_filtro_dialogos = None


def aplicar_tema(app: QApplication) -> None:
    """Fuerza un aspecto claro y consistente, aunque Windows esté en modo oscuro."""
    app.setStyle("Fusion")
    app.setPalette(_paleta_clara())
    app.setStyleSheet(hoja_de_estilos())

    global _filtro_dialogos
    _filtro_dialogos = _FondoDeDialogos(app)  # guardado para que no lo recoja el GC
    app.installEventFilter(_filtro_dialogos)


def marcar_boton(boton, rol: str) -> None:
    """rol: 'primario' (acción principal) o 'peligro' (eliminar)."""
    boton.setProperty("rol", rol)
