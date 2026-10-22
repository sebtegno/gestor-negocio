import datetime as dt
import os
import shutil

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QDateEdit, QDoubleSpinBox, QTableWidget, QTableWidgetItem, QComboBox,
    QDialogButtonBox, QMessageBox, QFileDialog, QScrollArea, QSplitter, QWidget
)
from PySide6.QtCore import Qt, QDate, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices

from .. import repositorio as repo
from .. import factura_parser as fp
from ..rutas import carpeta_datos
from .tema import marcar_boton

OMITIR, NUEVO, PENDIENTE = "omitir", "nuevo", "pendiente"


class DialogoFacturaProveedor(QDialog):
    """Carga de una factura de proveedor: lee el PDF (si tiene texto), propone a qué producto
    del stock corresponde cada renglón y, al confirmar, suma el stock y registra la deuda."""

    def __init__(self, proveedor, parent=None):
        super().__init__(parent)
        self.proveedor = proveedor
        self.setWindowTitle(f"Cargar factura de {proveedor.razon_social}")
        self.resize(1000, 640)
        self._archivo = ""
        self._productos = repo.listar_productos()
        self._alias = repo.alias_de_proveedor(proveedor.id)

        raiz = QVBoxLayout(self)

        # --- archivo
        fila_arch = QHBoxLayout()
        b_arch = QPushButton("Elegir PDF o foto de la factura...")
        marcar_boton(b_arch, "primario")
        b_arch.clicked.connect(self._elegir_archivo)
        self.label_archivo = QLabel("Sin archivo (podés cargar los renglones a mano)")
        fila_arch.addWidget(b_arch)
        fila_arch.addWidget(self.label_archivo, 1)
        raiz.addLayout(fila_arch)

        self.label_aviso = QLabel("")
        self.label_aviso.setWordWrap(True)
        self.label_aviso.setStyleSheet("color: #8a5a00;")
        raiz.addWidget(self.label_aviso)

        # --- cabecera
        form = QFormLayout()
        self.numero = QLineEdit()
        self.numero.setPlaceholderText("0001-00001234")
        self.fecha = QDateEdit(QDate.currentDate())
        self.fecha.setCalendarPopup(True)
        self.fecha.setDisplayFormat("dd/MM/yyyy")
        self.total = QDoubleSpinBox()
        self.total.setMaximum(1_000_000_000)
        self.total.setDecimals(2)
        self.total.valueChanged.connect(self._actualizar_suma)
        self.observaciones = QLineEdit()
        form.addRow("Número de factura:", self.numero)
        form.addRow("Fecha:", self.fecha)
        form.addRow("Total de la factura (con IVA):", self.total)
        form.addRow("Observaciones:", self.observaciones)
        raiz.addLayout(form)

        # --- vista previa (solo fotos) + tabla
        self.split = QSplitter(Qt.Horizontal)
        self.visor = QLabel()
        self.visor.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll = QScrollArea()
        scroll.setWidget(self.visor)
        scroll.setWidgetResizable(True)
        self.panel_img = scroll
        self.panel_img.hide()
        self.split.addWidget(self.panel_img)

        derecha = QWidget()
        lay_der = QVBoxLayout(derecha)
        lay_der.setContentsMargins(0, 0, 0, 0)
        lay_der.addWidget(QLabel("Renglones de la factura y a qué producto del stock corresponden:"))
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Cantidad", "Descripción (según la factura)", "Costo unit.", "Producto del stock", "Coincidencia"])
        self.tabla.horizontalHeader().setStretchLastSection(True)
        self.tabla.setColumnWidth(0, 80)
        self.tabla.setColumnWidth(1, 280)
        self.tabla.setColumnWidth(2, 90)
        self.tabla.setColumnWidth(3, 280)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        lay_der.addWidget(self.tabla)
        barra = QHBoxLayout()
        b_mas = QPushButton("+ Renglón")
        b_mas.clicked.connect(lambda: self._agregar_fila())
        b_menos = QPushButton("Quitar renglón")
        b_menos.clicked.connect(self._quitar_fila)
        barra.addWidget(b_mas)
        barra.addWidget(b_menos)
        barra.addStretch()
        self.label_suma = QLabel("")
        barra.addWidget(self.label_suma)
        lay_der.addLayout(barra)
        self.split.addWidget(derecha)
        self.split.setStretchFactor(1, 3)
        raiz.addWidget(self.split, 1)

        ayuda = QLabel("No se cambia el costo de los productos que ya existen. "
                       "Los productos nuevos se crean con código provisorio y el costo de esta factura.")
        ayuda.setWordWrap(True)
        raiz.addWidget(ayuda)

        botones = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        botones.button(QDialogButtonBox.Ok).setText("Guardar factura y sumar stock")
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)
        raiz.addWidget(botones)

        self._agregar_fila()

    # ----------------------------------------------------------------- archivo
    def _elegir_archivo(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Elegir factura", "",
            "Facturas (*.pdf *.png *.jpg *.jpeg *.bmp *.webp);;Todos los archivos (*)")
        if not ruta:
            return
        self._archivo = ruta
        self.label_archivo.setText(os.path.basename(ruta))
        self.label_aviso.setText("")
        self.panel_img.hide()
        ext = os.path.splitext(ruta)[1].lower()

        if ext in fp.EXTENSIONES_IMAGEN:
            pix = QPixmap(ruta)
            if not pix.isNull():
                self.visor.setPixmap(pix.scaledToWidth(460, Qt.SmoothTransformation))
                self.panel_img.show()
                self.split.setSizes([480, 560])
            self.label_aviso.setText(
                "Es una foto: la app no puede leer el texto de una imagen. Cargá los renglones a mano "
                "mirando la foto de la izquierda; el buscador de la columna «Producto del stock» te ayuda "
                "a elegir. (Si tenés la factura en PDF con texto, se lee sola.)")
            return

        try:
            texto = fp.extraer_texto_pdf(ruta)
        except Exception as e:
            QMessageBox.warning(self, "No se pudo leer el PDF", str(e))
            return
        if len(texto.strip()) < 30:
            self.label_aviso.setText(
                "Este PDF no tiene texto (es una imagen escaneada), así que no se puede leer solo. "
                "Se abrió con tu visor de PDF: cargá los renglones a mano.")
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
            return
        self._aplicar_analisis(fp.analizar_factura(texto))

    def _aplicar_analisis(self, datos: dict):
        if datos["numero"]:
            self.numero.setText(datos["numero"])
        if datos["fecha"]:
            self.fecha.setDate(QDate(datos["fecha"].year, datos["fecha"].month, datos["fecha"].day))
        if datos["total"]:
            self.total.setValue(datos["total"])

        avisos = []
        cuit_prov = "".join(c for c in (self.proveedor.cuit or "") if c.isdigit())
        if cuit_prov and datos["cuits"] and cuit_prov not in datos["cuits"]:
            avisos.append("El CUIT de la factura no coincide con el de este proveedor: revisá que sea el correcto.")

        self.tabla.setRowCount(0)
        for l in datos["lineas"]:
            self._agregar_fila(l)
        if not datos["lineas"]:
            self._agregar_fila()
            avisos.append("No se pudieron reconocer los renglones: cargalos a mano.")
        else:
            avisos.append(f"Se leyeron {len(datos['lineas'])} renglones. Revisá cantidades, precios y el producto de cada uno antes de guardar.")
        self.label_aviso.setText(" ".join(avisos))
        self._actualizar_suma()

    # ------------------------------------------------------------------ tabla
    def _armar_combo(self, sugerido_id, tiene_sugerencia: bool) -> QComboBox:
        c = QComboBox()
        if not tiene_sugerencia:
            c.addItem("— Elegir —", PENDIENTE)
        c.addItem("— Omitir (no sumar al stock) —", OMITIR)
        c.addItem("+ Crear producto nuevo", NUEVO)
        for p in self._productos:
            c.addItem(f"{p.codigo} - {p.descripcion}", p.id)
        if sugerido_id is not None:
            i = c.findData(sugerido_id)
            if i >= 0:
                c.setCurrentIndex(i)
        return c

    def _agregar_fila(self, linea: dict | None = None):
        fila = self.tabla.rowCount()
        self.tabla.insertRow(fila)
        linea = linea or {}
        cant = linea.get("cantidad", 1)
        self.tabla.setItem(fila, 0, QTableWidgetItem(f"{cant:g}" if cant != "" else ""))
        self.tabla.setItem(fila, 1, QTableWidgetItem(linea.get("descripcion", "")))
        self.tabla.setItem(fila, 2, QTableWidgetItem(f"{linea.get('precio_unitario', 0):.2f}"))

        sug_id, puntaje = (None, 0.0)
        if linea.get("descripcion"):
            sug_id, puntaje = fp.sugerir_producto(
                linea["descripcion"], linea.get("codigo", ""), self._productos, self._alias)
        combo = self._armar_combo(sug_id, sug_id is not None)
        self.tabla.setCellWidget(fila, 3, combo)
        if sug_id is None:
            txt = "Sin coincidencia" if linea.get("descripcion") else ""
        else:
            txt = "Segura" if puntaje >= 0.95 else f"Revisar ({puntaje:.0%})"
        item = QTableWidgetItem(txt)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self.tabla.setItem(fila, 4, item)
        self.tabla.itemChanged.connect(self._actualizar_suma) if fila == 0 and not getattr(self, "_conectado", False) else None
        self._conectado = True

    def _quitar_fila(self):
        fila = self.tabla.currentRow()
        if fila >= 0:
            self.tabla.removeRow(fila)
            self._actualizar_suma()

    @staticmethod
    def _num(texto, defecto=0.0):
        v = fp.numero_ar(str(texto).replace("$", "")) if str(texto).strip() else None
        if v is None:
            try:
                v = float(str(texto).replace(",", "."))
            except ValueError:
                v = defecto
        return v

    def _filas(self):
        res = []
        for f in range(self.tabla.rowCount()):
            desc = (self.tabla.item(f, 1).text() if self.tabla.item(f, 1) else "").strip()
            cant = self._num(self.tabla.item(f, 0).text() if self.tabla.item(f, 0) else "")
            precio = self._num(self.tabla.item(f, 2).text() if self.tabla.item(f, 2) else "")
            data = self.tabla.cellWidget(f, 3).currentData()
            res.append((desc, cant, precio, data))
        return res

    def _actualizar_suma(self, *_):
        suma = sum(c * p for d, c, p, _ in self._filas())
        self.label_suma.setText(f"Suma de renglones: ${suma:,.2f}  |  Total de la factura: ${self.total.value():,.2f}")

    # ---------------------------------------------------------------- guardar
    def _guardar(self):
        filas = [f for f in self._filas() if f[0] or f[1]]
        if not filas:
            QMessageBox.warning(self, "Sin renglones", "Cargá al menos un renglón.")
            return
        if self.total.value() <= 0:
            QMessageBox.warning(self, "Falta el total", "Ingresá el total de la factura (es lo que se suma a la deuda con el proveedor).")
            return
        pendientes = [d or "(sin descripción)" for d, c, p, data in filas if data == PENDIENTE]
        if pendientes:
            QMessageBox.warning(
                self, "Falta elegir el producto",
                "Elegí qué hacer con estos renglones (producto del stock, crear nuevo u omitir):\n\n• "
                + "\n• ".join(pendientes[:10]))
            return
        sin_cant = [d for d, c, p, data in filas if data not in (OMITIR,) and c <= 0]
        if sin_cant:
            QMessageBox.warning(self, "Cantidad inválida", "Hay renglones sin cantidad mayor a cero:\n• " + "\n• ".join(sin_cant[:10]))
            return

        items = []
        for desc, cant, precio, data in filas:
            if data == OMITIR:
                accion, pid = "omitir", None
            elif data == NUEVO:
                accion, pid = "nuevo", None
            else:
                accion, pid = "existente", data
            items.append(dict(descripcion=desc, cantidad=cant, precio_unitario=precio, accion=accion,
                              producto_id=pid, descripcion_norm=fp.norm(desc)))

        ruta_guardada = ""
        if self._archivo and os.path.exists(self._archivo):
            try:
                carpeta = carpeta_datos() / "facturas_proveedores"
                carpeta.mkdir(parents=True, exist_ok=True)
                destino = carpeta / f"{self.proveedor.id}_{dt.datetime.now():%Y%m%d_%H%M%S}_{os.path.basename(self._archivo)}"
                shutil.copy2(self._archivo, destino)
                ruta_guardada = str(destino)
            except Exception:
                ruta_guardada = self._archivo

        f = self.fecha.date()
        try:
            r = repo.crear_factura_proveedor(
                self.proveedor.id, self.numero.text().strip(), dt.date(f.year(), f.month(), f.day()),
                self.total.value(), items, self.observaciones.text().strip(), ruta_guardada)
        except Exception as e:
            QMessageBox.critical(self, "No se pudo guardar", str(e))
            return
        QMessageBox.information(
            self, "Factura guardada",
            f"Se sumó stock de {r['sumados']} producto(s) ({r['creados']} nuevo(s) creado(s)).\n"
            f"Omitidos: {r['omitidos']}.\nSe registró una deuda de ${self.total.value():,.2f} con el proveedor.")
        self.accept()
