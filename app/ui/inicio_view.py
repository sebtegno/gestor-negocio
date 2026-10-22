import datetime as dt
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QCoreApplication

from .tema import marcar_boton

from .. import cotizador_dolar, marca
from ..rutas import ruta_logo

RUTA_LOGO = ruta_logo()

DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_en_espanol(fecha: dt.date) -> str:
    dia_semana = DIAS_ES[fecha.weekday()]
    mes = MESES_ES[fecha.month - 1]
    return f"{dia_semana.capitalize()} {fecha.day} de {mes} de {fecha.year}"


class InicioView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        # --- Logo, centrado arriba ---
        self.label_logo = QLabel()
        self.label_logo.setAlignment(Qt.AlignCenter)
        self._cargar_logo()
        layout.addWidget(self.label_logo)

        # --- Fecha ---
        self.label_fecha = QLabel(_fecha_en_espanol(dt.date.today()))
        self.label_fecha.setAlignment(Qt.AlignCenter)
        self.label_fecha.setStyleSheet(f"font-size: 16px; color: {marca.COLOR_TEXTO};")
        layout.addWidget(self.label_fecha)

        layout.addSpacing(20)

        # --- Cotización del dólar ---
        marco = QFrame()
        marco.setObjectName("tarjeta")
        marco_layout = QVBoxLayout(marco)
        marco_layout.setContentsMargins(20, 16, 20, 16)

        titulo = QLabel("Dólar Banco Nación (BNA)")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"font-weight: 600; font-size: 15px; color: {marca.COLOR_TEXTO};")
        marco_layout.addWidget(titulo)

        self.label_dolar = QLabel("Cargando...")
        self.label_dolar.setAlignment(Qt.AlignCenter)
        self.label_dolar.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {marca.COLOR_TEXTO};")
        marco_layout.addWidget(self.label_dolar)

        self.label_actualizado = QLabel("")
        self.label_actualizado.setAlignment(Qt.AlignCenter)
        self.label_actualizado.setStyleSheet(f"font-size: 12px; color: {marca.COLOR_TEXTO};")
        marco_layout.addWidget(self.label_actualizado)

        barra_botones = QHBoxLayout()
        btn_actualizar = QPushButton("ACTUALIZAR COTIZACIÓN")
        marcar_boton(btn_actualizar, "primario")
        btn_actualizar.clicked.connect(lambda: self.actualizar_dolar(forzar=True))
        barra_botones.addStretch()
        barra_botones.addWidget(btn_actualizar)
        barra_botones.addStretch()
        marco_layout.addLayout(barra_botones)

        layout.addWidget(marco)
        layout.addStretch()

        self.actualizar_dolar()

    def _cargar_logo(self):
        if RUTA_LOGO.exists():
            pixmap = QPixmap(str(RUTA_LOGO))
            if not pixmap.isNull():
                self.label_logo.setPixmap(
                    pixmap.scaledToHeight(90, Qt.SmoothTransformation)
                )
                return
        self.label_logo.setText("(Colocá tu logo en assets/logo.png)")
        self.label_logo.setStyleSheet(f"color: {marca.COLOR_TEXTO_SUAVE}; font-style: italic; padding: 20px;")

    def actualizar_dolar(self, forzar: bool = False):
        QCoreApplication.processEvents()
        try:
            valor = cotizador_dolar.valor_dolar_del_dia(forzar_actualizacion=forzar)
        except cotizador_dolar.DolarNoDisponibleError as e:
            self.label_dolar.setText("No disponible")
            self.label_actualizado.setText(str(e))
            return
        except Exception as e:
            self.label_dolar.setText("No disponible")
            self.label_actualizado.setText(f"Error al actualizar: {e}")
            return

        self.label_dolar.setText(
            f"Compra ${valor.compra:,.2f}   |   Venta ${valor.venta:,.2f}"
        )
        fecha_valor = valor.fecha.date() if hasattr(valor.fecha, "date") else valor.fecha
        self.label_actualizado.setText(
            f"Cotización del {fecha_valor.strftime('%d/%m/%Y')} — fuente: {valor.fuente}"
        )

    def valor_dolar_actual(self):
        """Devuelve el ValorDolar cacheado de hoy (o el último disponible), sin refrescar la UI."""
        try:
            return cotizador_dolar.valor_dolar_del_dia()
        except cotizador_dolar.DolarNoDisponibleError:
            return None
