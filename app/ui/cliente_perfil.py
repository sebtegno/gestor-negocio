from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QLabel, QComboBox, QDoubleSpinBox, QDialogButtonBox,
    QFileDialog
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from .. import repositorio as repo
from .tema import marcar_boton
from ..pdf_generator import generar_pdf_remito
from .. import impresion_remito as imp
from ..pdf_estado_cuenta import generar_pdf_estado_cuenta


class DialogoMovimientoCuenta(QDialog):
    """Formulario simple para cargar (o editar) un pago (haber) o una deuda manual (debe)."""

    def __init__(self, tipo: str, parent=None, movimiento_existente=None):
        super().__init__(parent)
        self.tipo = tipo  # "debe" | "haber"
        self.movimiento_existente = movimiento_existente
        titulo = "Registrar pago" if tipo == "haber" else "Registrar deuda"
        if movimiento_existente:
            titulo = "Editar movimiento"
        self.setWindowTitle(titulo)
        layout = QFormLayout(self)

        self.importe = QDoubleSpinBox()
        self.importe.setMaximum(100_000_000)
        self.importe.setDecimals(2)
        self.concepto = QLineEdit()
        self.concepto.setText("Pago recibido" if tipo == "haber" else "Cargo manual")

        layout.addRow("Importe:", self.importe)
        layout.addRow("Concepto:", self.concepto)

        if tipo == "haber":
            self.medio_pago = QComboBox()
            self.medio_pago.addItems(["Efectivo", "Transferencia", "Tarjeta", "Cheque", "Otro"])
            layout.addRow("Medio de pago:", self.medio_pago)
        else:
            self.medio_pago = None

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        if movimiento_existente:
            self.importe.setValue(movimiento_existente.importe)
            self.concepto.setText(movimiento_existente.concepto or "")
            if self.medio_pago is not None and movimiento_existente.medio_pago:
                idx = self.medio_pago.findText(movimiento_existente.medio_pago)
                if idx >= 0:
                    self.medio_pago.setCurrentIndex(idx)


class DialogoGenerarRemito(QDialog):
    def __init__(self, cliente, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generar remito desde cotización")
        layout = QFormLayout(self)

        self._cotizaciones = repo.listar_cotizaciones_cliente(cliente.id)
        self.combo_cotizacion = QComboBox()
        for cot in self._cotizaciones:
            self.combo_cotizacion.addItem(
                f"{cot.numero} — {cot.fecha.strftime('%d/%m/%Y')} — ${cot.total:,.2f}",
                cot.id,
            )

        partes = [cliente.domicilio_envio or cliente.domicilio or ""]
        if cliente.domicilio_envio:
            partes += [cliente.localidad_envio or "", cliente.provincia_envio or ""]
        self.domicilio_entrega = QLineEdit(", ".join(p.strip() for p in partes if p and p.strip()))
        self.observaciones = QTextEdit()
        self.orden_compra = QLineEdit()
        self.expreso = QLineEdit()
        self.numero_formulario = QLineEdit()
        self.numero_formulario.setPlaceholderText("Nº preimpreso del formulario (solo registro)")

        layout.addRow("Cotización:", self.combo_cotizacion)
        layout.addRow("Domicilio de entrega:", self.domicilio_entrega)
        layout.addRow("Orden de compra Nº:", self.orden_compra)
        layout.addRow("Expreso:", self.expreso)
        layout.addRow("Nº de formulario:", self.numero_formulario)
        layout.addRow("Observaciones:", self.observaciones)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

    def tiene_cotizaciones(self) -> bool:
        return len(self._cotizaciones) > 0

    def datos(self) -> dict:
        return dict(
            cotizacion_id=self.combo_cotizacion.currentData(),
            domicilio_entrega=self.domicilio_entrega.text().strip(),
            observaciones=self.observaciones.toPlainText().strip(),
            orden_compra=self.orden_compra.text().strip(),
            expreso=self.expreso.text().strip(),
            numero_formulario=self.numero_formulario.text().strip(),
        )


class DialogoAjusteImpresion(QDialog):
    """Offsets de impresión y hoja de prueba de alineación."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajustar impresión sobre formulario")
        cfg = imp.cargar_config()
        form = QFormLayout(self)
        self.ox = QDoubleSpinBox(); self.ox.setRange(-30, 30); self.ox.setDecimals(1)
        self.ox.setSuffix(" mm"); self.ox.setValue(cfg["offset_x_mm"])
        self.oy = QDoubleSpinBox(); self.oy.setRange(-30, 30); self.oy.setDecimals(1)
        self.oy.setSuffix(" mm"); self.oy.setValue(cfg["offset_y_mm"])
        from PySide6.QtWidgets import QCheckBox
        self.a4 = QCheckBox("Imprimir en hoja A4 (formulario arriba a la izquierda)")
        self.a4.setChecked(cfg["hoja_a4"])
        form.addRow("Mover a la derecha (+) / izquierda (-):", self.ox)
        form.addRow("Mover hacia abajo (+) / arriba (-):", self.oy)
        form.addRow(self.a4)
        b = QPushButton("Generar hoja de prueba (con fondo)")
        b.clicked.connect(lambda: self._prueba(True))
        b2 = QPushButton("Generar hoja de prueba (solo datos, para imprimir)")
        b2.clicked.connect(lambda: self._prueba(False))
        form.addRow(b); form.addRow(b2)
        bt = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bt.accepted.connect(self._guardar); bt.rejected.connect(self.reject)
        form.addRow(bt)

    def _cfg(self):
        return {"offset_x_mm": self.ox.value(), "offset_y_mm": self.oy.value(),
                "hoja_a4": self.a4.isChecked()}

    def _prueba(self, con_fondo):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar hoja de prueba",
            "prueba_alineacion.pdf", "Archivos PDF (*.pdf)")
        if not ruta:
            return
        try:
            imp.generar_pdf_prueba_alineacion(ruta, con_fondo, self._cfg())
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def _guardar(self):
        imp.guardar_config(self._cfg())
        self.accept()


class ClientePerfilDialog(QDialog):
    def __init__(self, cliente_id: int, parent=None):
        super().__init__(parent)
        self.cliente_id = cliente_id
        self.cliente = repo.obtener_cliente(cliente_id)
        self.setWindowTitle(f"Perfil de {self.cliente.razon_social}")
        self.resize(700, 500)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        tabs.addTab(self._tab_datos_envio(), "Dirección de envío")
        tabs.addTab(self._tab_cuenta_corriente(), "Cuenta corriente")
        tabs.addTab(self._tab_remitos(), "Remitos")

    # ------------------------------------------------------------------
    # Pestaña: dirección y datos de envío (editable)
    # ------------------------------------------------------------------
    def _tab_datos_envio(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        c = self.cliente

        self.domicilio_envio = QLineEdit(c.domicilio_envio or "")
        self.localidad_envio = QLineEdit(c.localidad_envio or "")
        self.provincia_envio = QLineEdit(c.provincia_envio or "")
        self.codigo_postal_envio = QLineEdit(c.codigo_postal_envio or "")
        self.notas_envio = QTextEdit(c.notas_envio or "")

        form.addRow("Dirección de envío:", self.domicilio_envio)
        form.addRow("Localidad:", self.localidad_envio)
        form.addRow("Provincia:", self.provincia_envio)
        form.addRow("Código postal:", self.codigo_postal_envio)
        form.addRow("Notas de envío:", self.notas_envio)

        btn_guardar = QPushButton("Guardar cambios")
        btn_guardar.clicked.connect(self._guardar_datos_envio)
        form.addRow(btn_guardar)
        return w

    def _guardar_datos_envio(self):
        try:
            repo.actualizar_cliente(
                self.cliente_id,
                domicilio_envio=self.domicilio_envio.text().strip(),
                localidad_envio=self.localidad_envio.text().strip(),
                provincia_envio=self.provincia_envio.text().strip(),
                codigo_postal_envio=self.codigo_postal_envio.text().strip(),
                notas_envio=self.notas_envio.toPlainText().strip(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        QMessageBox.information(self, "Listo", "Datos de envío actualizados.")

    # ------------------------------------------------------------------
    # Pestaña: cuenta corriente (debe / haber)
    # ------------------------------------------------------------------
    def _tab_cuenta_corriente(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.label_saldo = QLabel()
        self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px;")
        layout.addWidget(self.label_saldo)

        barra = QHBoxLayout()
        btn_pago = QPushButton("+ Registrar pago (haber)")
        marcar_boton(btn_pago, "primario")
        btn_pago.clicked.connect(lambda: self._nuevo_movimiento("haber"))
        btn_cargo = QPushButton("+ Cargar deuda manual (debe)")
        btn_cargo.clicked.connect(lambda: self._nuevo_movimiento("debe"))
        btn_editar_mov = QPushButton("Editar")
        btn_editar_mov.clicked.connect(self._editar_movimiento)
        btn_eliminar_mov = QPushButton("Eliminar")
        marcar_boton(btn_eliminar_mov, "peligro")
        btn_eliminar_mov.clicked.connect(self._eliminar_movimiento)
        barra.addWidget(btn_pago)
        barra.addWidget(btn_cargo)
        barra.addWidget(btn_editar_mov)
        barra.addWidget(btn_eliminar_mov)
        btn_estado = QPushButton("Estado de cuenta (PDF)")
        btn_estado.clicked.connect(self._descargar_estado_cuenta)
        barra.addWidget(btn_estado)
        barra.addStretch()
        layout.addLayout(barra)

        self.tabla_cuenta = QTableWidget(0, 5)
        self.tabla_cuenta.setHorizontalHeaderLabels(
            ["Fecha", "Tipo", "Concepto", "Medio de pago", "Importe"]
        )
        self.tabla_cuenta.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_cuenta.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_cuenta.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla_cuenta)

        self._movimientos = []
        self._refrescar_cuenta_corriente()
        return w

    def _descargar_estado_cuenta(self):
        nombre = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in self.cliente.razon_social).strip()
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar estado de cuenta",
            f"Estado de cuenta - {nombre}.pdf", "Archivos PDF (*.pdf)")
        if not ruta:
            return
        try:
            generar_pdf_estado_cuenta(
                repo.obtener_cliente(self.cliente_id),
                repo.listar_movimientos_cliente(self.cliente_id), ruta)
        except Exception as e:
            QMessageBox.critical(self, "Error al generar el PDF", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def _movimiento_seleccionado(self):
        fila = self.tabla_cuenta.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un movimiento",
                                     "Elegí una fila de la tabla primero.")
            return None
        return self._movimientos[fila]

    def _editar_movimiento(self):
        mov = self._movimiento_seleccionado()
        if mov is None:
            return
        dialogo = DialogoMovimientoCuenta(mov.tipo, self, movimiento_existente=mov)
        if dialogo.exec() == QDialog.Accepted:
            importe = dialogo.importe.value()
            if importe <= 0:
                QMessageBox.warning(self, "Importe inválido", "El importe debe ser mayor a cero.")
                return
            campos = dict(
                importe=importe,
                concepto=dialogo.concepto.text().strip() or mov.concepto,
            )
            if dialogo.medio_pago is not None:
                campos["medio_pago"] = dialogo.medio_pago.currentText()
            try:
                repo.actualizar_movimiento_cuenta(mov.id, **campos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self._refrescar_cuenta_corriente()

    def _eliminar_movimiento(self):
        mov = self._movimiento_seleccionado()
        if mov is None:
            return
        confirmacion = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar el movimiento \"{mov.concepto}\" por ${mov.importe:,.2f}?"
        )
        if confirmacion != QMessageBox.Yes:
            return
        try:
            repo.eliminar_movimiento_cuenta(mov.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo eliminar", str(e))
            return
        self._refrescar_cuenta_corriente()

    def _nuevo_movimiento(self, tipo: str):
        dialogo = DialogoMovimientoCuenta(tipo, self)
        if dialogo.exec() == QDialog.Accepted:
            importe = dialogo.importe.value()
            if importe <= 0:
                QMessageBox.warning(self, "Importe inválido", "El importe debe ser mayor a cero.")
                return
            try:
                if tipo == "haber":
                    repo.registrar_pago(
                        self.cliente_id, importe,
                        medio_pago=dialogo.medio_pago.currentText(),
                        concepto=dialogo.concepto.text().strip() or "Pago recibido",
                    )
                else:
                    repo.registrar_cargo(
                        self.cliente_id, importe,
                        concepto=dialogo.concepto.text().strip() or "Cargo manual",
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self._refrescar_cuenta_corriente()

    def _refrescar_cuenta_corriente(self):
        self._movimientos = repo.listar_movimientos_cliente(self.cliente_id)
        movimientos = self._movimientos
        saldo = repo.saldo_cliente(self.cliente_id)

        if saldo > 0:
            self.label_saldo.setText(f"Saldo: nos debe ${saldo:,.2f}")
            self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px; color: #b00020;")
        elif saldo < 0:
            self.label_saldo.setText(f"Saldo: a favor del cliente ${abs(saldo):,.2f}")
            self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px; color: #2e7d32;")
        else:
            self.label_saldo.setText("Saldo: $0.00 (al día)")
            self.label_saldo.setStyleSheet("font-weight: bold; font-size: 15px;")

        self.tabla_cuenta.setRowCount(len(movimientos))
        for row, m in enumerate(movimientos):
            self.tabla_cuenta.setItem(row, 0, QTableWidgetItem(m.fecha.strftime("%d/%m/%Y %H:%M")))
            self.tabla_cuenta.setItem(row, 1, QTableWidgetItem("Debe" if m.tipo == "debe" else "Haber"))
            self.tabla_cuenta.setItem(row, 2, QTableWidgetItem(m.concepto or ""))
            self.tabla_cuenta.setItem(row, 3, QTableWidgetItem(m.medio_pago or ""))
            item_importe = QTableWidgetItem(f"${m.importe:,.2f}")
            item_importe.setForeground(Qt.red if m.tipo == "debe" else Qt.darkGreen)
            self.tabla_cuenta.setItem(row, 4, item_importe)

    # ------------------------------------------------------------------
    # Pestaña: remitos
    # ------------------------------------------------------------------
    def _tab_remitos(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        barra = QHBoxLayout()
        btn_generar = QPushButton("+ Generar remito desde cotización")
        marcar_boton(btn_generar, "primario")
        btn_generar.clicked.connect(self._generar_remito)
        btn_descargar = QPushButton("Descargar PDF")
        btn_descargar.clicked.connect(self._descargar_remito)
        btn_form = QPushButton("Imprimir en formulario")
        btn_form.clicked.connect(lambda: self._pdf_formulario(False))
        btn_prev = QPushButton("Vista previa (con fondo)")
        btn_prev.clicked.connect(lambda: self._pdf_formulario(True))
        btn_ajuste = QPushButton("Ajustar impresión")
        btn_ajuste.clicked.connect(lambda: DialogoAjusteImpresion(self).exec())
        barra.addWidget(btn_generar)
        barra.addWidget(btn_descargar)
        barra.addWidget(btn_form)
        barra.addWidget(btn_prev)
        barra.addWidget(btn_ajuste)
        barra.addStretch()
        layout.addLayout(barra)

        self.tabla_remitos = QTableWidget(0, 5)
        self.tabla_remitos.setHorizontalHeaderLabels(
            ["Número", "Fecha", "Ítems", "Estado", "Nº formulario"]
        )
        self.tabla_remitos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla_remitos.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_remitos.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla_remitos)

        self._remitos = []
        self._refrescar_remitos()
        return w

    def _remito_seleccionado(self):
        fila = self.tabla_remitos.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un remito",
                                     "Elegí una fila de la tabla primero.")
            return None
        return self._remitos[fila]

    def _descargar_remito(self):
        remito = self._remito_seleccionado()
        if remito is None:
            return

        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar remito como PDF",
            f"{remito.numero}.pdf", "Archivos PDF (*.pdf)"
        )
        if not ruta:
            return

        try:
            remito_completo = repo.obtener_remito(remito.id)
            generar_pdf_remito(remito_completo, ruta)
        except Exception as e:
            QMessageBox.critical(
                self, "Error al generar el PDF",
                f"{e}\n\n¿Instalaste reportlab? (pip install reportlab)"
            )
            return

        respuesta = QMessageBox.question(
            self, "PDF generado",
            f"Se guardó el remito en:\n{ruta}\n\n¿Querés abrirlo ahora?"
        )
        if respuesta == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def _pdf_formulario(self, con_fondo: bool):
        remito = self._remito_seleccionado()
        if remito is None:
            return
        sugerido = f"{remito.numero}_{'preview' if con_fondo else 'imprimir'}.pdf"
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar PDF", sugerido, "Archivos PDF (*.pdf)")
        if not ruta:
            return
        try:
            hojas = imp.generar_pdf_remito_preimpreso(
                repo.obtener_remito(remito.id), ruta, con_fondo=con_fondo)
        except Exception as e:
            QMessageBox.critical(self, "Error al generar el PDF", str(e))
            return
        if hojas > 1:
            QMessageBox.information(
                self, "Más de una hoja",
                f"El remito tiene más ítems que renglones del formulario: "
                f"se generaron {hojas} hojas. Usá {hojas} formularios.")
        QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def _generar_remito(self):
        dialogo = DialogoGenerarRemito(self.cliente, self)
        if not dialogo.tiene_cotizaciones():
            QMessageBox.information(
                self, "Sin cotizaciones",
                "Este cliente todavía no tiene cotizaciones cargadas."
            )
            return
        if dialogo.exec() == QDialog.Accepted:
            datos = dialogo.datos()
            try:
                repo.crear_remito_desde_cotizacion(**datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self._refrescar_remitos()

    def _refrescar_remitos(self):
        self._remitos = repo.listar_remitos_cliente(self.cliente_id)
        remitos = self._remitos
        self.tabla_remitos.setRowCount(len(remitos))
        for row, r in enumerate(remitos):
            resumen_items = ", ".join(
                f"{it.producto.codigo} x{it.cantidad:g}" for it in r.items
            )
            self.tabla_remitos.setItem(row, 0, QTableWidgetItem(r.numero))
            self.tabla_remitos.setItem(row, 1, QTableWidgetItem(r.fecha.strftime("%d/%m/%Y")))
            self.tabla_remitos.setItem(row, 2, QTableWidgetItem(resumen_items))
            self.tabla_remitos.setItem(row, 3, QTableWidgetItem(r.estado))
            self.tabla_remitos.setItem(row, 4, QTableWidgetItem(r.numero_formulario or ""))
