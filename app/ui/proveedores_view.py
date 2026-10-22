from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QFormLayout, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QTextEdit
)
from PySide6.QtCore import Qt

from .. import repositorio as repo
from .tema import marcar_boton
from .proveedor_perfil import ProveedorPerfilDialog

CONDICIONES_IVA = ["Responsable Inscripto", "Monotributo", "Exento", "Consumidor Final"]


class DialogoProveedor(QDialog):
    def __init__(self, parent=None, proveedor_existente=None):
        super().__init__(parent)
        self.setWindowTitle("Editar proveedor" if proveedor_existente else "Nuevo proveedor")
        self.resize(440, 380)
        form = QFormLayout(self)
        self.razon_social = QLineEdit()
        self.cuit = QLineEdit()
        self.cuit.setPlaceholderText("30XXXXXXXX3 (sirve para reconocerlo al leer sus facturas)")
        self.condicion_iva = QComboBox()
        self.condicion_iva.addItems(CONDICIONES_IVA)
        self.domicilio = QLineEdit()
        self.email = QLineEdit()
        self.telefono = QLineEdit()
        self.notas = QTextEdit()
        self.notas.setFixedHeight(70)
        form.addRow("Razón social / Nombre:", self.razon_social)
        form.addRow("CUIT:", self.cuit)
        form.addRow("Condición IVA:", self.condicion_iva)
        form.addRow("Domicilio:", self.domicilio)
        form.addRow("Email:", self.email)
        form.addRow("Teléfono:", self.telefono)
        form.addRow("Notas:", self.notas)
        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

        if proveedor_existente:
            p = proveedor_existente
            self.razon_social.setText(p.razon_social or "")
            self.cuit.setText(p.cuit or "")
            i = self.condicion_iva.findText(p.condicion_iva or "")
            if i >= 0:
                self.condicion_iva.setCurrentIndex(i)
            self.domicilio.setText(p.domicilio or "")
            self.email.setText(p.email or "")
            self.telefono.setText(p.telefono or "")
            self.notas.setPlainText(p.notas or "")

    def datos(self) -> dict:
        return dict(
            razon_social=self.razon_social.text().strip(),
            cuit=self.cuit.text().strip(),
            condicion_iva=self.condicion_iva.currentText(),
            domicilio=self.domicilio.text().strip(),
            email=self.email.text().strip(),
            telefono=self.telefono.text().strip(),
            notas=self.notas.toPlainText().strip(),
        )


class ProveedoresView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Buscar por nombre, CUIT o email...")
        self.buscador.textChanged.connect(self._pintar_tabla)
        layout.addWidget(self.buscador)

        barra = QHBoxLayout()
        btn_perfil = QPushButton("Ver perfil (facturas / cuenta corriente)")
        btn_perfil.clicked.connect(self.abrir_perfil)
        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self.editar)
        btn_eliminar = QPushButton("Eliminar")
        marcar_boton(btn_eliminar, "peligro")
        btn_eliminar.clicked.connect(self.eliminar)
        btn_nuevo = QPushButton("+ Nuevo proveedor")
        marcar_boton(btn_nuevo, "primario")
        btn_nuevo.clicked.connect(self.nuevo)
        barra.addWidget(btn_perfil)
        barra.addWidget(btn_editar)
        barra.addWidget(btn_eliminar)
        barra.addStretch()
        barra.addWidget(btn_nuevo)
        layout.addLayout(barra)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Razón social", "CUIT", "Condición IVA", "Email", "Teléfono", "Saldo (les debemos)"])
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.doubleClicked.connect(self.abrir_perfil)
        layout.addWidget(self.tabla)

        self._proveedores = []
        self._mostrados = []
        self.refrescar()

    def _seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un proveedor", "Elegí una fila de la tabla primero.")
            return None
        return self._mostrados[fila]

    def nuevo(self):
        d = DialogoProveedor(self)
        if d.exec() == QDialog.Accepted:
            datos = d.datos()
            if not datos["razon_social"]:
                QMessageBox.warning(self, "Datos incompletos", "La razón social es obligatoria.")
                return
            try:
                repo.crear_proveedor(**datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def editar(self):
        p = self._seleccionado()
        if p is None:
            return
        d = DialogoProveedor(self, proveedor_existente=p)
        if d.exec() == QDialog.Accepted:
            datos = d.datos()
            if not datos["razon_social"]:
                QMessageBox.warning(self, "Datos incompletos", "La razón social es obligatoria.")
                return
            try:
                repo.actualizar_proveedor(p.id, **datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def eliminar(self):
        p = self._seleccionado()
        if p is None:
            return
        if QMessageBox.question(
                self, "Confirmar eliminación",
                f"¿Eliminar a {p.razon_social}?\n\nSi tiene facturas o movimientos, solo se oculta "
                "de la lista y se conserva el historial.") != QMessageBox.Yes:
            return
        try:
            repo.eliminar_proveedor(p.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo eliminar", str(e))
            return
        self.refrescar()

    def abrir_perfil(self, *_):
        p = self._seleccionado()
        if p is None:
            return
        ProveedorPerfilDialog(p.id, self).exec()
        self.refrescar()

    def refrescar(self):
        self._proveedores = repo.listar_proveedores()
        self._pintar_tabla()

    def _pintar_tabla(self, *_):
        texto = self.buscador.text().strip().lower()
        lista = self._proveedores
        if texto:
            lista = [p for p in lista if texto in (p.razon_social or "").lower()
                     or texto in (p.cuit or "").lower() or texto in (p.email or "").lower()]
        self._mostrados = lista
        self.tabla.setRowCount(len(lista))
        for row, p in enumerate(lista):
            saldo = repo.saldo_proveedor(p.id)
            self.tabla.setItem(row, 0, QTableWidgetItem(p.razon_social or ""))
            self.tabla.setItem(row, 1, QTableWidgetItem(p.cuit or ""))
            self.tabla.setItem(row, 2, QTableWidgetItem(p.condicion_iva or ""))
            self.tabla.setItem(row, 3, QTableWidgetItem(p.email or ""))
            self.tabla.setItem(row, 4, QTableWidgetItem(p.telefono or ""))
            item = QTableWidgetItem(f"${saldo:,.2f}")
            if saldo > 0:
                item.setForeground(Qt.red)
            elif saldo < 0:
                item.setForeground(Qt.darkGreen)
            self.tabla.setItem(row, 5, item)
