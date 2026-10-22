import os

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from .. import repositorio as repo
from .tema import marcar_boton
from .cliente_perfil import DialogoMovimientoCuenta
from .factura_proveedor import DialogoFacturaProveedor


class ProveedorPerfilDialog(QDialog):
    def __init__(self, proveedor_id: int, parent=None):
        super().__init__(parent)
        self.proveedor_id = proveedor_id
        self.proveedor = repo.obtener_proveedor(proveedor_id)
        self.setWindowTitle(f"Proveedor: {self.proveedor.razon_social}")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        tabs.addTab(self._tab_facturas(), "Facturas")
        tabs.addTab(self._tab_cuenta(), "Cuenta corriente")

    # ------------------------------------------------------------------ facturas
    def _tab_facturas(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        barra = QHBoxLayout()
        b_cargar = QPushButton("+ Cargar factura")
        marcar_boton(b_cargar, "primario")
        b_cargar.clicked.connect(self._cargar_factura)
        b_ver = QPushButton("Ver detalle")
        b_ver.clicked.connect(self._ver_detalle)
        b_abrir = QPushButton("Abrir archivo original")
        b_abrir.clicked.connect(self._abrir_archivo)
        b_elim = QPushButton("Eliminar")
        marcar_boton(b_elim, "peligro")
        b_elim.clicked.connect(self._eliminar_factura)
        for b in (b_cargar, b_ver, b_abrir, b_elim):
            barra.addWidget(b)
        barra.addStretch()
        lay.addLayout(barra)

        self.tabla_fact = QTableWidget(0, 5)
        self.tabla_fact.setHorizontalHeaderLabels(["Fecha", "Número", "Total", "Ítems sumados al stock", "Archivo"])
        self.tabla_fact.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_fact.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_fact.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tabla_fact)
        self._facturas = []
        self._refrescar_facturas()
        return w

    def _factura_sel(self):
        fila = self.tabla_fact.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná una factura", "Elegí una fila de la tabla primero.")
            return None
        return self._facturas[fila]

    def _cargar_factura(self):
        d = DialogoFacturaProveedor(self.proveedor, self)
        if d.exec() == QDialog.Accepted:
            self._refrescar_facturas()
            self._refrescar_cuenta()

    def _ver_detalle(self):
        f = self._factura_sel()
        if f is None:
            return
        lineas = []
        for it in f.items:
            if it.producto is not None:
                dest = f"-> {it.producto.codigo} (+{it.stock_sumado:g})"
            else:
                dest = "(no se sumó al stock)"
            lineas.append(f"{it.cantidad:g} x {it.descripcion}  ${it.precio_unitario:,.2f}  {dest}")
        QMessageBox.information(
            self, f"Factura {f.numero or f.id}",
            f"Fecha: {f.fecha:%d/%m/%Y}\nTotal: ${f.total:,.2f}\n\n" + ("\n".join(lineas) or "Sin renglones"))

    def _abrir_archivo(self):
        f = self._factura_sel()
        if f is None:
            return
        if not f.archivo or not os.path.exists(f.archivo):
            QMessageBox.information(self, "Sin archivo", "Esta factura no tiene un archivo guardado o ya no está en esa ubicación.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(f.archivo))

    def _eliminar_factura(self):
        f = self._factura_sel()
        if f is None:
            return
        caja = QMessageBox(self)
        caja.setWindowTitle("Eliminar factura")
        caja.setText(f"¿Eliminar la factura {f.numero or f.id} por ${f.total:,.2f}?\n\n"
                     "También se borra la deuda que generó en la cuenta corriente.")
        chk = QCheckBox("Restar del stock lo que había sumado")
        chk.setChecked(True)
        caja.setCheckBox(chk)
        caja.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        if caja.exec() != QMessageBox.Yes:
            return
        try:
            repo.eliminar_factura_proveedor(f.id, revertir_stock=chk.isChecked())
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self._refrescar_facturas()
        self._refrescar_cuenta()

    def _refrescar_facturas(self):
        self._facturas = repo.listar_facturas_proveedor(self.proveedor_id)
        self.tabla_fact.setRowCount(len(self._facturas))
        for row, f in enumerate(self._facturas):
            sumados = sum(1 for it in f.items if (it.stock_sumado or 0) > 0)
            self.tabla_fact.setItem(row, 0, QTableWidgetItem(f.fecha.strftime("%d/%m/%Y")))
            self.tabla_fact.setItem(row, 1, QTableWidgetItem(f.numero or ""))
            self.tabla_fact.setItem(row, 2, QTableWidgetItem(f"${f.total:,.2f}"))
            self.tabla_fact.setItem(row, 3, QTableWidgetItem(f"{sumados} de {len(f.items)}"))
            self.tabla_fact.setItem(row, 4, QTableWidgetItem(os.path.basename(f.archivo) if f.archivo else ""))

    # ------------------------------------------------------------ cuenta corriente
    def _tab_cuenta(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.label_saldo = QLabel()
        self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px;")
        lay.addWidget(self.label_saldo)
        nota = QLabel("Debe = lo que les debemos (facturas). Haber = lo que les pagamos.")
        lay.addWidget(nota)

        barra = QHBoxLayout()
        b_pago = QPushButton("+ Registrar pago (haber)")
        marcar_boton(b_pago, "primario")
        b_pago.clicked.connect(lambda: self._nuevo_mov("haber"))
        b_deuda = QPushButton("+ Cargar deuda manual (debe)")
        b_deuda.clicked.connect(lambda: self._nuevo_mov("debe"))
        b_edit = QPushButton("Editar")
        b_edit.clicked.connect(self._editar_mov)
        b_elim = QPushButton("Eliminar")
        marcar_boton(b_elim, "peligro")
        b_elim.clicked.connect(self._eliminar_mov)
        for b in (b_pago, b_deuda, b_edit, b_elim):
            barra.addWidget(b)
        barra.addStretch()
        lay.addLayout(barra)

        self.tabla_cc = QTableWidget(0, 5)
        self.tabla_cc.setHorizontalHeaderLabels(["Fecha", "Tipo", "Concepto", "Medio de pago", "Importe"])
        self.tabla_cc.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_cc.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_cc.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tabla_cc)
        self._movs = []
        self._refrescar_cuenta()
        return w

    def _mov_sel(self):
        fila = self.tabla_cc.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un movimiento", "Elegí una fila de la tabla primero.")
            return None
        return self._movs[fila]

    def _nuevo_mov(self, tipo: str):
        d = DialogoMovimientoCuenta(tipo, self)
        d.concepto.setText("Pago realizado" if tipo == "haber" else "Cargo manual")
        if d.exec() != QDialog.Accepted:
            return
        if d.importe.value() <= 0:
            QMessageBox.warning(self, "Importe inválido", "El importe debe ser mayor a cero.")
            return
        try:
            repo.registrar_movimiento_proveedor(
                self.proveedor_id, tipo, d.importe.value(),
                d.concepto.text().strip() or ("Pago realizado" if tipo == "haber" else "Cargo manual"),
                d.medio_pago.currentText() if d.medio_pago is not None else "")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self._refrescar_cuenta()

    def _editar_mov(self):
        m = self._mov_sel()
        if m is None:
            return
        if m.factura_id:
            QMessageBox.information(self, "Movimiento de una factura",
                                    "Este movimiento viene de una factura cargada. Para cambiarlo, eliminá la factura y volvé a cargarla.")
            return
        d = DialogoMovimientoCuenta(m.tipo, self, movimiento_existente=m)
        if d.exec() != QDialog.Accepted:
            return
        if d.importe.value() <= 0:
            QMessageBox.warning(self, "Importe inválido", "El importe debe ser mayor a cero.")
            return
        campos = dict(importe=d.importe.value(), concepto=d.concepto.text().strip() or m.concepto)
        if d.medio_pago is not None:
            campos["medio_pago"] = d.medio_pago.currentText()
        try:
            repo.actualizar_movimiento_proveedor(m.id, **campos)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self._refrescar_cuenta()

    def _eliminar_mov(self):
        m = self._mov_sel()
        if m is None:
            return
        if QMessageBox.question(self, "Confirmar", f"¿Eliminar «{m.concepto}» por ${m.importe:,.2f}?") != QMessageBox.Yes:
            return
        try:
            repo.eliminar_movimiento_proveedor(m.id)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo eliminar", str(e))
            return
        self._refrescar_cuenta()

    def _refrescar_cuenta(self):
        self._movs = repo.listar_movimientos_proveedor(self.proveedor_id)
        saldo = repo.saldo_proveedor(self.proveedor_id)
        if saldo > 0:
            self.label_saldo.setText(f"Saldo: les debemos ${saldo:,.2f}")
            self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px; color: #b00020;")
        elif saldo < 0:
            self.label_saldo.setText(f"Saldo: a nuestro favor ${abs(saldo):,.2f}")
            self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px; color: #2e7d32;")
        else:
            self.label_saldo.setText("Saldo: $0.00 (al día)")
            self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.tabla_cc.setRowCount(len(self._movs))
        for row, m in enumerate(self._movs):
            self.tabla_cc.setItem(row, 0, QTableWidgetItem(m.fecha.strftime("%d/%m/%Y")))
            self.tabla_cc.setItem(row, 1, QTableWidgetItem("Debe" if m.tipo == "debe" else "Haber"))
            self.tabla_cc.setItem(row, 2, QTableWidgetItem(m.concepto or ""))
            self.tabla_cc.setItem(row, 3, QTableWidgetItem(m.medio_pago or ""))
            it = QTableWidgetItem(f"${m.importe:,.2f}")
            it.setForeground(Qt.red if m.tipo == "debe" else Qt.darkGreen)
            self.tabla_cc.setItem(row, 4, it)
