from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QFormLayout, QDoubleSpinBox, QMessageBox,
    QDialog, QDialogButtonBox, QLabel, QCheckBox, QFileDialog
)
from PySide6.QtCore import Qt

from .. import repositorio as repo
from .. import importar_productos as imp
from .tema import marcar_boton


class DialogoProducto(QDialog):
    def __init__(self, parent=None, producto_existente=None):
        super().__init__(parent)
        self.producto_existente = producto_existente
        self.setWindowTitle("Editar producto" if producto_existente else "Nuevo producto")
        layout = QFormLayout(self)

        self.codigo = QLineEdit()
        self.descripcion = QLineEdit()
        self.precio_en_dolares = QCheckBox("Precio en dólares (USD)")
        self.precio_en_dolares.setToolTip(
            "Si lo tildás, el costo y el precio de venta se cargan en USD y se "
            "convierten automáticamente a pesos con la cotización del día al "
            "armar una cotización o factura."
        )
        self.precio_costo = QDoubleSpinBox()
        self.precio_costo.setMaximum(10_000_000)
        self.precio_venta = QDoubleSpinBox()
        self.precio_venta.setMaximum(10_000_000)
        self.stock = QDoubleSpinBox()
        self.stock.setMaximum(1_000_000)
        self.stock_minimo = QDoubleSpinBox()
        self.stock_minimo.setMaximum(1_000_000)

        layout.addRow("Código:", self.codigo)
        layout.addRow("Descripción:", self.descripcion)
        layout.addRow("", self.precio_en_dolares)
        layout.addRow("Precio costo:", self.precio_costo)
        layout.addRow("Precio venta:", self.precio_venta)
        layout.addRow("Stock actual:" if producto_existente else "Stock inicial:", self.stock)
        layout.addRow("Stock mínimo:", self.stock_minimo)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addRow(botones)

        if producto_existente:
            p = producto_existente
            self.codigo.setText(p.codigo)
            self.descripcion.setText(p.descripcion)
            self.precio_en_dolares.setChecked(bool(p.precio_en_dolares))
            self.precio_costo.setValue(p.precio_costo)
            self.precio_venta.setValue(p.precio_venta)
            self.stock.setValue(p.stock_actual)
            self.stock_minimo.setValue(p.stock_minimo)

    def datos(self) -> dict:
        base = dict(
            codigo=self.codigo.text().strip(),
            descripcion=self.descripcion.text().strip(),
            precio_costo=self.precio_costo.value(),
            precio_venta=self.precio_venta.value(),
            stock_minimo=self.stock_minimo.value(),
            precio_en_dolares=self.precio_en_dolares.isChecked(),
        )
        if self.producto_existente:
            base["stock_actual"] = self.stock.value()
        else:
            base["stock_inicial"] = self.stock.value()
        return base


class DialogoImportar(QDialog):
    """Vista previa de la importación desde Excel."""

    def __init__(self, resultado, existentes: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar productos desde Excel")
        self.resize(760, 520)
        layout = QVBoxLayout(self)

        nuevos = [p for p in resultado.productos if p.codigo not in existentes]
        repetidos = [p for p in resultado.productos if p.codigo in existentes]
        layout.addWidget(QLabel(
            f"<b>{len(resultado.productos)}</b> productos en el archivo: "
            f"<b>{len(nuevos)}</b> nuevos y <b>{len(repetidos)}</b> cuyo código ya existe."))

        self.chk_actualizar = QCheckBox(
            "Actualizar los que ya existen (descripción y precio; el stock no se toca)")
        self.chk_actualizar.setEnabled(bool(repetidos))
        layout.addWidget(self.chk_actualizar)

        tabla = QTableWidget(len(resultado.productos), 4)
        tabla.setHorizontalHeaderLabels(["Código", "Descripción", "Precio", "Estado"])
        tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        tabla.horizontalHeader().setStretchLastSection(True)
        for i, p in enumerate(resultado.productos):
            simbolo = "US$" if p.en_dolares else "$"
            estado = "Ya existe" if p.codigo in existentes else (
                "Nuevo (código provisorio)" if p.codigo_provisorio else "Nuevo")
            for j, v in enumerate((p.codigo, p.descripcion, f"{simbolo}{p.precio:,.2f}", estado)):
                tabla.setItem(i, j, QTableWidgetItem(v))
        tabla.resizeColumnToContents(0)
        tabla.setColumnWidth(1, 330)
        layout.addWidget(tabla)

        if resultado.avisos:
            avisos = QLabel("<b>Avisos:</b><br>" + "<br>".join("• " + a for a in resultado.avisos))
            avisos.setWordWrap(True)
            layout.addWidget(avisos)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Importar")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def actualizar_existentes(self) -> bool:
        return self.chk_actualizar.isChecked()


class StockView(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        barra_busqueda = QHBoxLayout()
        self.buscador = QLineEdit()
        self.buscador.setPlaceholderText("Buscar por código o descripción...")
        self.buscador.textChanged.connect(self._aplicar_filtro)
        barra_busqueda.addWidget(self.buscador)
        layout.addLayout(barra_busqueda)

        barra = QHBoxLayout()
        btn_editar = QPushButton("Editar")
        btn_editar.clicked.connect(self.editar_seleccionado)
        btn_eliminar = QPushButton("Eliminar")
        marcar_boton(btn_eliminar, "peligro")
        btn_eliminar.clicked.connect(self.eliminar_seleccionado)
        btn_nuevo = QPushButton("+ Nuevo producto")
        marcar_boton(btn_nuevo, "primario")
        btn_nuevo.clicked.connect(self.nuevo_producto)
        barra.addWidget(btn_editar)
        barra.addWidget(btn_eliminar)
        btn_importar = QPushButton("Importar desde Excel")
        btn_importar.clicked.connect(self.importar_excel)
        barra.addWidget(btn_importar)
        barra.addStretch()
        barra.addWidget(btn_nuevo)
        layout.addLayout(barra)

        self.alerta_stock = QLabel("")
        self.alerta_stock.setStyleSheet("color: #b00020; font-weight: bold;")
        layout.addWidget(self.alerta_stock)

        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(
            ["Código", "Descripción", "Costo", "Venta", "Stock", "Mínimo"]
        )
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.tabla)

        self._productos_mostrados = []
        self.refrescar()

    def nuevo_producto(self):
        dialogo = DialogoProducto(self)
        if dialogo.exec() == QDialog.Accepted:
            datos = dialogo.datos()
            if not datos["codigo"] or not datos["descripcion"]:
                QMessageBox.warning(self, "Datos incompletos",
                                     "Código y descripción son obligatorios.")
                return
            try:
                repo.crear_producto(**datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def editar_seleccionado(self):
        producto = self._producto_seleccionado()
        if producto is None:
            return
        dialogo = DialogoProducto(self, producto_existente=producto)
        if dialogo.exec() == QDialog.Accepted:
            datos = dialogo.datos()
            if not datos["codigo"] or not datos["descripcion"]:
                QMessageBox.warning(self, "Datos incompletos",
                                     "Código y descripción son obligatorios.")
                return
            try:
                repo.actualizar_producto(producto.id, **datos)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            self.refrescar()

    def importar_excel(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegir Excel de productos", "", "Excel (*.xlsx)")
        if not ruta:
            return
        try:
            resultado = imp.leer_excel(ruta)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo leer el Excel", str(e))
            return
        if not resultado.productos:
            QMessageBox.information(self, "Sin productos", "No se encontraron productos en el archivo.")
            return

        existentes = {p.codigo: p for p in repo.listar_productos(solo_activos=False)}
        imp.asignar_codigos_provisorios(resultado.productos, set(existentes))
        dialogo = DialogoImportar(resultado, existentes, self)
        if dialogo.exec() != QDialog.Accepted:
            return

        creados = actualizados = salteados = 0
        errores = []
        for p in resultado.productos:
            try:
                ex = existentes.get(p.codigo)
                if ex is None:
                    repo.crear_producto(
                        codigo=p.codigo, descripcion=p.descripcion, precio_costo=0.0,
                        precio_venta=p.precio, stock_inicial=p.stock,
                        stock_minimo=p.stock_minimo, unidad=p.unidad,
                        alicuota_iva=p.alicuota_iva, precio_en_dolares=p.en_dolares)
                    creados += 1
                elif dialogo.actualizar_existentes():
                    repo.actualizar_producto(
                        ex.id, descripcion=p.descripcion, precio_venta=p.precio,
                        precio_en_dolares=p.en_dolares, activo=True)
                    actualizados += 1
                else:
                    salteados += 1
            except Exception as e:
                errores.append(f"{p.codigo}: {e}")
        self.refrescar()
        msg = f"Creados: {creados}\nActualizados: {actualizados}\nSalteados: {salteados}"
        if errores:
            msg += "\n\nErrores:\n" + "\n".join(errores[:10])
        QMessageBox.information(self, "Importación terminada", msg)

    def eliminar_seleccionado(self):
        producto = self._producto_seleccionado()
        if producto is None:
            return
        confirmacion = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar {producto.codigo} - {producto.descripcion}?\n\n"
            "El producto se ocultará de los listados, pero se conserva su "
            "historial en cotizaciones y remitos ya generados."
        )
        if confirmacion != QMessageBox.Yes:
            return
        try:
            repo.eliminar_producto(producto.id)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo eliminar", str(e))
            return
        self.refrescar()

    def _producto_seleccionado(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.information(self, "Seleccioná un producto",
                                     "Elegí una fila de la tabla primero.")
            return None
        return self._productos_mostrados[fila]

    def _aplicar_filtro(self):
        self.refrescar()

    def refrescar(self):
        texto = self.buscador.text().strip().lower()
        productos = repo.listar_productos()
        if texto:
            productos = [
                p for p in productos
                if texto in p.codigo.lower() or texto in p.descripcion.lower()
            ]
        self._productos_mostrados = productos

        self.tabla.setRowCount(len(productos))
        for row, p in enumerate(productos):
            simbolo = "US$" if p.precio_en_dolares else "$"
            self.tabla.setItem(row, 0, QTableWidgetItem(p.codigo))
            self.tabla.setItem(row, 1, QTableWidgetItem(p.descripcion))
            self.tabla.setItem(row, 2, QTableWidgetItem(f"{simbolo}{p.precio_costo:,.2f}"))
            self.tabla.setItem(row, 3, QTableWidgetItem(f"{simbolo}{p.precio_venta:,.2f}"))
            item_stock = QTableWidgetItem(f"{p.stock_actual:g}")
            if p.stock_bajo:
                item_stock.setForeground(Qt.red)
            self.tabla.setItem(row, 4, item_stock)
            self.tabla.setItem(row, 5, QTableWidgetItem(f"{p.stock_minimo:g}"))

        bajos = repo.productos_con_stock_bajo()
        if bajos:
            nombres = ", ".join(p.codigo for p in bajos)
            self.alerta_stock.setText(f"⚠ Stock bajo en: {nombres}")
        else:
            self.alerta_stock.setText("")
