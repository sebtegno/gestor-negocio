from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QDoubleSpinBox, QMessageBox, QLabel, QLineEdit,
    QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QFileDialog, QCheckBox
)
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from .. import repositorio as repo
from .tema import marcar_boton
from .. import cotizador_dolar
from ..pdf_generator import generar_pdf_cotizacion
from .widgets import ComboBuscable


class DialogoNuevaCotizacion(QDialog):
    """
    Arma o edita una cotización: elegís cliente (con autocompletado),
    agregás ítems buscando el producto por código o descripción (si se
    agrega el mismo producto más de una vez, se suman las cantidades en
    la misma línea), y podés quitarlos antes de guardar. Los productos
    cargados en dólares se convierten a pesos con la cotización del día.
    """

    def __init__(self, parent=None, cotizacion_existente=None):
        super().__init__(parent)
        self.cotizacion_existente = cotizacion_existente
        self.setWindowTitle("Editar cotización" if cotizacion_existente else "Nueva cotización")
        self.resize(700, 520)
        self._items: list[dict] = []

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.combo_cliente = ComboBuscable()
        self._clientes = repo.listar_clientes()
        self.combo_cliente.cargar_items([(c.id, c.razon_social) for c in self._clientes])
        form.addRow("Cliente (escribí para buscar):", self.combo_cliente)
        layout.addLayout(form)

        agregar_item = QHBoxLayout()
        self.combo_producto = ComboBuscable()
        self._productos = repo.listar_productos()
        self.combo_producto.cargar_items(
            [(p.id, f"{p.codigo} - {p.descripcion}") for p in self._productos]
        )
        self.cantidad = QDoubleSpinBox()
        self.cantidad.setMinimum(0.01)
        self.cantidad.setValue(1)
        self.cantidad.setMaximum(100000)
        btn_agregar = QPushButton("Agregar ítem")
        btn_agregar.clicked.connect(self.agregar_item)
        agregar_item.addWidget(self.combo_producto, 3)
        agregar_item.addWidget(self.cantidad, 1)
        agregar_item.addWidget(btn_agregar)
        layout.addLayout(agregar_item)

        self.tabla_items = QTableWidget(0, 5)
        self.tabla_items.setHorizontalHeaderLabels(
            ["Producto", "Cantidad", "Precio unit. (ARS)", "Origen (USD)", "Subtotal"]
        )
        self.tabla_items.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla_items.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla_items)

        btn_quitar = QPushButton("Quitar ítem seleccionado")
        btn_quitar.clicked.connect(self.quitar_item)
        layout.addWidget(btn_quitar)

        self.chk_iva = QCheckBox("Incluir IVA (según la alícuota de cada producto)")
        self.chk_iva.stateChanged.connect(self._refrescar_tabla_items)
        layout.addWidget(self.chk_iva)

        self.label_subtotal = QLabel("Subtotal: $0.00")
        self.label_iva = QLabel("IVA: $0.00")
        self.label_total = QLabel("Total: $0.00")
        self.label_total.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.label_subtotal)
        layout.addWidget(self.label_iva)
        layout.addWidget(self.label_total)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

        if cotizacion_existente:
            self._precargar(cotizacion_existente)

    def _precargar(self, cot):
        idx = next((i for i, c in enumerate(self._clientes) if c.id == cot.cliente_id), None)
        if idx is not None:
            self.combo_cliente.setCurrentIndex(idx)
            self.combo_cliente.lineEdit().setText(self._clientes[idx].razon_social)

        self.chk_iva.setChecked(bool(cot.incluye_iva))

        for it in cot.items:
            self._items.append(dict(
                producto_id=it.producto_id,
                descripcion=f"{it.producto.codigo} - {it.producto.descripcion}",
                cantidad=it.cantidad,
                precio_unitario=it.precio_unitario,
                precio_usd_original=it.precio_usd_original,
                tipo_cambio_usado=it.tipo_cambio_usado,
                alicuota_iva=it.producto.alicuota_iva,
            ))
        self._refrescar_tabla_items()

    def agregar_item(self):
        producto_id = self.combo_producto.valor_seleccionado()
        if producto_id is None:
            QMessageBox.warning(self, "Producto no encontrado",
                                 "Escribí el código o nombre y elegí un producto de la lista.")
            return
        producto = next(p for p in self._productos if p.id == producto_id)
        cantidad = self.cantidad.value()

        precio_usd_original = None
        tipo_cambio_usado = None
        if producto.precio_en_dolares:
            try:
                valor_dolar = cotizador_dolar.valor_dolar_del_dia()
            except cotizador_dolar.DolarNoDisponibleError as e:
                QMessageBox.critical(self, "Sin cotización del dólar", str(e))
                return
            precio_usd_original = producto.precio_venta
            tipo_cambio_usado = valor_dolar.venta
            precio_unitario = round(precio_usd_original * tipo_cambio_usado, 2)
        else:
            precio_unitario = producto.precio_venta

        # Si el mismo producto ya está en la lista, se suman las cantidades
        # en vez de crear una línea duplicada.
        existente = next((it for it in self._items if it["producto_id"] == producto.id), None)
        if existente:
            existente["cantidad"] += cantidad
        else:
            self._items.append(dict(
                producto_id=producto.id,
                descripcion=f"{producto.codigo} - {producto.descripcion}",
                cantidad=cantidad,
                precio_unitario=precio_unitario,
                precio_usd_original=precio_usd_original,
                tipo_cambio_usado=tipo_cambio_usado,
                alicuota_iva=producto.alicuota_iva,
            ))
        self._refrescar_tabla_items()

    def quitar_item(self):
        fila = self.tabla_items.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un ítem",
                                     "Elegí una fila de la tabla de ítems primero.")
            return
        self._items.pop(fila)
        self._refrescar_tabla_items()

    def _refrescar_tabla_items(self, *_):
        self.tabla_items.setRowCount(len(self._items))
        subtotal_neto = 0.0
        monto_iva = 0.0
        con_iva = self.chk_iva.isChecked()
        for row, it in enumerate(self._items):
            subtotal = it["cantidad"] * it["precio_unitario"]
            subtotal_neto += subtotal
            if con_iva:
                monto_iva += subtotal * (it.get("alicuota_iva", 21.0) / 100)
            self.tabla_items.setItem(row, 0, QTableWidgetItem(it["descripcion"]))
            self.tabla_items.setItem(row, 1, QTableWidgetItem(f"{it['cantidad']:g}"))
            self.tabla_items.setItem(row, 2, QTableWidgetItem(f"${it['precio_unitario']:,.2f}"))
            origen = ""
            if it.get("precio_usd_original") is not None:
                origen = f"US$ {it['precio_usd_original']:,.2f} x ${it['tipo_cambio_usado']:,.2f}"
            self.tabla_items.setItem(row, 3, QTableWidgetItem(origen))
            self.tabla_items.setItem(row, 4, QTableWidgetItem(f"${subtotal:,.2f}"))
        self.label_subtotal.setText(f"Subtotal (sin IVA): ${subtotal_neto:,.2f}")
        self.label_iva.setText(f"IVA: ${monto_iva:,.2f}" if con_iva else "IVA: no incluido")
        self.label_total.setText(f"Total: ${subtotal_neto + monto_iva:,.2f}")

    def datos(self) -> tuple[int, list[dict], bool]:
        cliente_id = self.combo_cliente.valor_seleccionado()
        return cliente_id, self._items, self.chk_iva.isChecked()


class DialogoFacturar(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Facturar cotización")
        layout = QFormLayout(self)

        self.tipo = QComboBox()
        self.tipo.addItems(["B", "A"])
        self.punto_venta = QSpinBox()
        self.punto_venta.setMinimum(1)
        self.punto_venta.setMaximum(9999)
        self.punto_venta.setValue(1)

        layout.addRow("Tipo de comprobante:", self.tipo)
        layout.addRow("Punto de venta:", self.punto_venta)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)


class CotizacionesView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        barra = QHBoxLayout()
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Buscar por cliente o número de cotización...")
        self.buscador.textChanged.connect(self._aplicar_filtro)
        barra.addWidget(self.buscador)
        layout.addLayout(barra)

        acciones = QHBoxLayout()
        btn_nueva = QPushButton("+ Nueva cotización")
        marcar_boton(btn_nueva, "primario")
        btn_nueva.clicked.connect(self.nueva_cotizacion)
        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self.editar_seleccionada)
        btn_eliminar = QPushButton("Eliminar")
        marcar_boton(btn_eliminar, "peligro")
        btn_eliminar.clicked.connect(self.eliminar_seleccionada)
        btn_pdf = QPushButton("Descargar PDF")
        btn_pdf.clicked.connect(self.descargar_pdf_seleccionada)
        btn_aceptar = QPushButton("Aceptar (descuenta stock)")
        btn_aceptar.clicked.connect(self.aceptar_seleccionada)
        btn_revertir = QPushButton("Revertir aceptación")
        btn_revertir.clicked.connect(self.revertir_seleccionada)
        btn_facturar = QPushButton("Convertir a factura")
        marcar_boton(btn_facturar, "primario")
        btn_facturar.clicked.connect(self.facturar_seleccionada)
        acciones.addWidget(btn_nueva)
        acciones.addWidget(btn_editar)
        acciones.addWidget(btn_eliminar)
        acciones.addWidget(btn_pdf)
        acciones.addWidget(btn_aceptar)
        acciones.addWidget(btn_revertir)
        acciones.addWidget(btn_facturar)
        acciones.addStretch()
        layout.addLayout(acciones)

        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Número", "Cliente", "Fecha", "Estado", "Total"]
        )
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla)

        self._cotizaciones = []
        self._cotizaciones_mostradas = []
        self.refrescar()

    def nueva_cotizacion(self):
        if not repo.listar_clientes():
            QMessageBox.warning(self, "Sin clientes",
                                 "Primero cargá al menos un cliente.")
            return
        if not repo.listar_productos():
            QMessageBox.warning(self, "Sin productos",
                                 "Primero cargá al menos un producto en Stock.")
            return

        dialogo = DialogoNuevaCotizacion(self)
        if dialogo.exec() == QDialog.Accepted:
            cliente_id, items, incluye_iva = dialogo.datos()
            if cliente_id is None:
                QMessageBox.warning(self, "Cliente no encontrado",
                                     "Escribí el nombre y elegí un cliente de la lista.")
                return
            if not items:
                QMessageBox.warning(self, "Sin ítems",
                                     "Agregá al menos un ítem a la cotización.")
                return
            try:
                nueva = repo.crear_cotizacion(cliente_id, items, incluye_iva=incluye_iva)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()
            self._ofrecer_descarga_pdf(nueva.id)

    def editar_seleccionada(self):
        cot = self._cotizacion_seleccionada()
        if cot is None:
            return
        if cot.estado == "Facturada":
            QMessageBox.information(self, "No editable",
                                     "Esta cotización ya fue facturada y no se puede editar.")
            return

        if cot.estado == "Aceptada":
            QMessageBox.information(
                self, "No editable",
                "Esta cotización está aceptada (ya descontó stock). "
                "Usá \"Revertir aceptación\" si necesitás corregirla."
            )
            return

        cot_completa = repo.obtener_cotizacion(cot.id)
        dialogo = DialogoNuevaCotizacion(self, cotizacion_existente=cot_completa)
        if dialogo.exec() == QDialog.Accepted:
            cliente_id, items, incluye_iva = dialogo.datos()
            if cliente_id is None:
                QMessageBox.warning(self, "Cliente no encontrado",
                                     "Escribí el nombre y elegí un cliente de la lista.")
                return
            if not items:
                QMessageBox.warning(self, "Sin ítems",
                                     "Una cotización necesita al menos un ítem.")
                return
            try:
                repo.actualizar_cotizacion(cot.id, cliente_id, items, incluye_iva=incluye_iva)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def eliminar_seleccionada(self):
        cot = self._cotizacion_seleccionada()
        if cot is None:
            return
        confirmacion = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar la cotización {cot.numero}? Esta acción no se puede deshacer."
        )
        if confirmacion != QMessageBox.Yes:
            return
        try:
            repo.eliminar_cotizacion(cot.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo eliminar", str(e))
            return
        self.refrescar()

    def descargar_pdf_seleccionada(self):
        cot = self._cotizacion_seleccionada()
        if cot is None:
            return
        self._ofrecer_descarga_pdf(cot.id, preguntar_antes=False)

    def _ofrecer_descarga_pdf(self, cotizacion_id: int, preguntar_antes: bool = True):
        if preguntar_antes:
            respuesta = QMessageBox.question(
                self, "Cotización creada",
                "La cotización se guardó correctamente.\n\n¿Querés descargarla en PDF ahora?"
            )
            if respuesta != QMessageBox.Yes:
                return

        cot = repo.obtener_cotizacion(cotizacion_id)
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar cotización como PDF",
            f"{cot.numero}.pdf", "Archivos PDF (*.pdf)"
        )
        if not ruta:
            return
        try:
            generar_pdf_cotizacion(cot, ruta)
        except Exception as e:
            QMessageBox.critical(
                self, "Error al generar el PDF",
                f"{e}\n\n¿Instalaste reportlab? (pip install reportlab)"
            )
            return

        respuesta = QMessageBox.question(
            self, "PDF generado",
            f"Se guardó la cotización en:\n{ruta}\n\n¿Querés abrirla ahora?"
        )
        if respuesta == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))

    def aceptar_seleccionada(self):
        cot = self._cotizacion_seleccionada()
        if cot is None:
            return
        confirmacion = QMessageBox.question(
            self, "Aceptar cotización",
            f"¿Aceptar la cotización {cot.numero}?\n\n"
            "Se va a descontar del stock la cantidad de cada producto. "
            "Si después la facturás, no se vuelve a descontar."
        )
        if confirmacion != QMessageBox.Yes:
            return
        try:
            repo.aceptar_cotizacion(cot.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo aceptar", str(e))
            return
        self.refrescar()

    def revertir_seleccionada(self):
        cot = self._cotizacion_seleccionada()
        if cot is None:
            return
        confirmacion = QMessageBox.question(
            self, "Revertir aceptación",
            f"¿Revertir la aceptación de {cot.numero}?\n\n"
            "Se devuelve el stock y la cotización vuelve a Borrador."
        )
        if confirmacion != QMessageBox.Yes:
            return
        try:
            repo.revertir_aceptacion(cot.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo revertir", str(e))
            return
        self.refrescar()

    def facturar_seleccionada(self):
        cot = self._cotizacion_seleccionada()
        if cot is None:
            return
        if cot.estado == "Facturada":
            QMessageBox.information(self, "Ya facturada",
                                     "Esta cotización ya fue convertida en factura.")
            return

        dialogo = DialogoFacturar(self)
        if dialogo.exec() == QDialog.Accepted:
            try:
                factura = repo.crear_factura_pendiente(
                    cot.id, dialogo.tipo.currentText(), dialogo.punto_venta.value()
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            QMessageBox.information(
                self, "Factura registrada",
                f"Se creó la factura #{factura.id} en estado Pendiente.\n\n"
                "Para obtener el CAE de ARCA, conectá el módulo app/afip/"
                "wsfe_client.py con tu certificado digital (ver README)."
            )
            self.refrescar()

    def _cotizacion_seleccionada(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná una cotización",
                                     "Elegí una fila de la tabla primero.")
            return None
        return self._cotizaciones_mostradas[fila]

    def _aplicar_filtro(self):
        self._pintar_tabla()

    def refrescar(self):
        self._cotizaciones = repo.listar_cotizaciones()
        self._pintar_tabla()

    def _pintar_tabla(self):
        texto = self.buscador.text().strip().lower()
        cotizaciones = self._cotizaciones
        if texto:
            cotizaciones = [
                c for c in cotizaciones
                if texto in c.cliente.razon_social.lower() or texto in c.numero.lower()
            ]
        self._cotizaciones_mostradas = cotizaciones

        self.tabla.setRowCount(len(cotizaciones))
        for row, cot in enumerate(cotizaciones):
            self.tabla.setItem(row, 0, QTableWidgetItem(cot.numero))
            self.tabla.setItem(row, 1, QTableWidgetItem(cot.cliente.razon_social))
            self.tabla.setItem(row, 2, QTableWidgetItem(cot.fecha.strftime("%d/%m/%Y")))
            self.tabla.setItem(row, 3, QTableWidgetItem(cot.estado))
            self.tabla.setItem(row, 4, QTableWidgetItem(f"${cot.total:,.2f}"))
