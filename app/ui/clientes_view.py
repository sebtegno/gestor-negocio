from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QFormLayout, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QTabWidget, QTextEdit
)
from PySide6.QtCore import Qt

from .. import repositorio as repo
from .tema import marcar_boton
from .cliente_perfil import ClientePerfilDialog

CONDICIONES_IVA = ["Consumidor Final", "Responsable Inscripto", "Monotributo", "Exento"]


class DialogoCliente(QDialog):
    def __init__(self, parent=None, cliente_existente=None):
        super().__init__(parent)
        self.cliente_existente = cliente_existente
        self.setWindowTitle("Editar cliente" if cliente_existente else "Nuevo cliente")
        self.resize(420, 400)
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Pestaña de datos generales / facturación ---
        tab_datos = QWidget()
        form_datos = QFormLayout(tab_datos)
        self.razon_social = QLineEdit()
        self.cuit = QLineEdit()
        self.cuit.setPlaceholderText("20XXXXXXXX3 (dejar vacío si es consumidor final)")
        self.condicion_iva = QComboBox()
        self.condicion_iva.addItems(CONDICIONES_IVA)
        self.domicilio = QLineEdit()
        self.email = QLineEdit()
        self.telefono = QLineEdit()
        form_datos.addRow("Razón social / Nombre:", self.razon_social)
        form_datos.addRow("CUIT:", self.cuit)
        form_datos.addRow("Condición IVA:", self.condicion_iva)
        form_datos.addRow("Domicilio fiscal:", self.domicilio)
        form_datos.addRow("Email:", self.email)
        form_datos.addRow("Teléfono:", self.telefono)
        tabs.addTab(tab_datos, "Datos generales")

        # --- Pestaña de dirección y datos de envío ---
        tab_envio = QWidget()
        form_envio = QFormLayout(tab_envio)
        self.domicilio_envio = QLineEdit()
        self.localidad_envio = QLineEdit()
        self.provincia_envio = QLineEdit()
        self.codigo_postal_envio = QLineEdit()
        self.notas_envio = QTextEdit()
        self.notas_envio.setPlaceholderText(
            "Ej: horario de recepción, contacto en depósito, referencias..."
        )
        form_envio.addRow("Dirección de envío:", self.domicilio_envio)
        form_envio.addRow("Localidad:", self.localidad_envio)
        form_envio.addRow("Provincia:", self.provincia_envio)
        form_envio.addRow("Código postal:", self.codigo_postal_envio)
        form_envio.addRow("Notas de envío:", self.notas_envio)
        tabs.addTab(tab_envio, "Dirección de envío")

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        if cliente_existente:
            c = cliente_existente
            self.razon_social.setText(c.razon_social)
            self.cuit.setText(c.cuit or "")
            idx = self.condicion_iva.findText(c.condicion_iva)
            if idx >= 0:
                self.condicion_iva.setCurrentIndex(idx)
            self.domicilio.setText(c.domicilio or "")
            self.email.setText(c.email or "")
            self.telefono.setText(c.telefono or "")
            self.domicilio_envio.setText(c.domicilio_envio or "")
            self.localidad_envio.setText(c.localidad_envio or "")
            self.provincia_envio.setText(c.provincia_envio or "")
            self.codigo_postal_envio.setText(c.codigo_postal_envio or "")
            self.notas_envio.setPlainText(c.notas_envio or "")

    def datos(self) -> dict:
        return dict(
            razon_social=self.razon_social.text().strip(),
            cuit=self.cuit.text().strip(),
            condicion_iva=self.condicion_iva.currentText(),
            domicilio=self.domicilio.text().strip(),
            email=self.email.text().strip(),
            telefono=self.telefono.text().strip(),
            domicilio_envio=self.domicilio_envio.text().strip(),
            localidad_envio=self.localidad_envio.text().strip(),
            provincia_envio=self.provincia_envio.text().strip(),
            codigo_postal_envio=self.codigo_postal_envio.text().strip(),
            notas_envio=self.notas_envio.toPlainText().strip(),
        )


class ClientesView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        barra_busqueda = QHBoxLayout()
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Buscar por nombre, CUIT o email...")
        self.buscador.textChanged.connect(self._aplicar_filtro)
        barra_busqueda.addWidget(self.buscador)
        layout.addLayout(barra_busqueda)

        barra = QHBoxLayout()
        btn_perfil = QPushButton("Ver perfil (cuenta corriente / remitos)")
        btn_perfil.clicked.connect(self.abrir_perfil_seleccionado)
        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self.editar_seleccionado)
        btn_eliminar = QPushButton("Eliminar")
        marcar_boton(btn_eliminar, "peligro")
        btn_eliminar.clicked.connect(self.eliminar_seleccionado)
        btn_nuevo = QPushButton("+ Nuevo cliente")
        marcar_boton(btn_nuevo, "primario")
        btn_nuevo.clicked.connect(self.nuevo_cliente)
        barra.addWidget(btn_perfil)
        barra.addWidget(btn_editar)
        barra.addWidget(btn_eliminar)
        barra.addStretch()
        barra.addWidget(btn_nuevo)
        layout.addLayout(barra)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Razón social", "CUIT", "Condición IVA", "Email", "Teléfono", "Saldo"]
        )
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.doubleClicked.connect(self.abrir_perfil_seleccionado)
        layout.addWidget(self.tabla)

        self._clientes = []
        self._clientes_mostrados = []
        self.refrescar()

    def nuevo_cliente(self):
        dialogo = DialogoCliente(self)
        if dialogo.exec() == QDialog.Accepted:
            datos = dialogo.datos()
            if not datos["razon_social"]:
                QMessageBox.warning(self, "Datos incompletos",
                                     "La razón social / nombre es obligatorio.")
                return
            try:
                repo.crear_cliente(**datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def editar_seleccionado(self):
        cliente = self._cliente_seleccionado()
        if cliente is None:
            return
        dialogo = DialogoCliente(self, cliente_existente=cliente)
        if dialogo.exec() == QDialog.Accepted:
            datos = dialogo.datos()
            if not datos["razon_social"]:
                QMessageBox.warning(self, "Datos incompletos",
                                     "La razón social / nombre es obligatorio.")
                return
            try:
                repo.actualizar_cliente(cliente.id, **datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def eliminar_seleccionado(self):
        cliente = self._cliente_seleccionado()
        if cliente is None:
            return
        confirmacion = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar a {cliente.razon_social}? Esta acción no se puede deshacer."
        )
        if confirmacion != QMessageBox.Yes:
            return
        try:
            repo.eliminar_cliente(cliente.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo eliminar", str(e))
            return
        self.refrescar()

    def _cliente_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un cliente",
                                     "Elegí una fila de la tabla primero.")
            return None
        return self._clientes_mostrados[fila]

    def abrir_perfil_seleccionado(self):
        cliente = self._cliente_seleccionado()
        if cliente is None:
            return
        dialogo = ClientePerfilDialog(cliente.id, self)
        dialogo.exec()
        self.refrescar()  # el saldo puede haber cambiado

    def _aplicar_filtro(self):
        self._pintar_tabla()

    def refrescar(self):
        self._clientes = repo.listar_clientes()
        self._pintar_tabla()

    def _pintar_tabla(self):
        texto = self.buscador.text().strip().lower()
        clientes = self._clientes
        if texto:
            clientes = [
                c for c in clientes
                if texto in c.razon_social.lower()
                or texto in (c.cuit or "").lower()
                or texto in (c.email or "").lower()
            ]
        self._clientes_mostrados = clientes

        self.tabla.setRowCount(len(clientes))
        for row, c in enumerate(clientes):
            saldo = repo.saldo_cliente(c.id)
            self.tabla.setItem(row, 0, QTableWidgetItem(c.razon_social))
            self.tabla.setItem(row, 1, QTableWidgetItem(c.cuit or ""))
            self.tabla.setItem(row, 2, QTableWidgetItem(c.condicion_iva))
            self.tabla.setItem(row, 3, QTableWidgetItem(c.email or ""))
            self.tabla.setItem(row, 4, QTableWidgetItem(c.telefono or ""))
            item_saldo = QTableWidgetItem(f"${saldo:,.2f}")
            if saldo > 0:
                item_saldo.setForeground(Qt.red)  # nos debe
            elif saldo < 0:
                item_saldo.setForeground(Qt.darkGreen)  # a favor del cliente
            self.tabla.setItem(row, 5, item_saldo)
