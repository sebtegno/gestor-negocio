from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel

from .. import marca
from ..version import VERSION
from .inicio_view import InicioView
from .stock_view import StockView
from .clientes_view import ClientesView
from .cotizaciones_view import CotizacionesView


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{marca.NOMBRE_EMPRESA.title()} — Gestión de negocio  (v{VERSION})")
        self.resize(1050, 680)

        contenedor = QWidget()
        contenedor.setObjectName("contenido")
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._crear_cabecera())

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.inicio_view = InicioView()
        self.stock_view = StockView()
        self.clientes_view = ClientesView()
        self.cotizaciones_view = CotizacionesView()

        tabs.addTab(self.inicio_view, "INICIO")
        tabs.addTab(self.stock_view, "STOCK")
        tabs.addTab(self.clientes_view, "CLIENTES")
        tabs.addTab(self.cotizaciones_view, "COTIZACIONES / FACTURAS")

        # Refrescar la pestaña al abrirla, por si cambió algo desde otra.
        tabs.currentChanged.connect(self._on_tab_changed)
        self._tabs = tabs
        layout.addWidget(tabs)

        self.setCentralWidget(contenedor)

    def _crear_cabecera(self) -> QWidget:
        cabecera = QWidget()
        cabecera.setObjectName("cabecera")
        caja = QVBoxLayout(cabecera)
        caja.setContentsMargins(24, 14, 24, 14)
        caja.setSpacing(2)

        titulo = QLabel(marca.NOMBRE_EMPRESA)
        titulo.setObjectName("tituloCabecera")
        subtitulo = QLabel(marca.SUBTITULO)
        subtitulo.setObjectName("subtituloCabecera")
        caja.addWidget(titulo)
        caja.addWidget(subtitulo)
        return cabecera

    def _on_tab_changed(self, index: int):
        widget = self._tabs.widget(index)
        if hasattr(widget, "refrescar"):
            widget.refrescar()
