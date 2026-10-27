import datetime as dt

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QComboBox, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from .. import repositorio as repo

VERDE = "#1b7f3b"
ROJO = "#b42318"


def _pesos(v: float) -> str:
    return f"${v:,.2f}"


class _Tarjeta(QFrame):
    def __init__(self, titulo: str, color: str | None = None):
        super().__init__()
        self.setObjectName("tarjeta")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        self.t = QLabel(titulo)
        self.t.setStyleSheet("font-size: 12px; color: #6b7280;")
        self.v = QLabel("$0.00")
        estilo = "font-size: 22px; font-weight: 700;" + (f" color: {color};" if color else "")
        self.v.setStyleSheet(estilo)
        self.s = QLabel("")
        self.s.setStyleSheet("font-size: 11px; color: #6b7280;")
        self.s.setWordWrap(True)
        lay.addWidget(self.t)
        lay.addWidget(self.v)
        lay.addWidget(self.s)

    def set(self, valor: float, sub: str = "", color: str | None = None):
        self.v.setText(_pesos(valor))
        if color:
            self.v.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {color};")
        self.s.setText(sub)


class BalanceView(QWidget):
    """Balance general: lo que entra (cobros a clientes) vs. lo que sale (pagos a proveedores)."""

    PERIODOS = ["Este mes", "Mes anterior", "Este año", "Todo el historial", "Personalizado"]

    def __init__(self):
        super().__init__()
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(16, 12, 16, 12)

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Período:"))
        self.combo = QComboBox()
        self.combo.addItems(self.PERIODOS)
        self.combo.currentIndexChanged.connect(self._cambio_periodo)
        filtros.addWidget(self.combo)
        self.desde = QDateEdit(QDate.currentDate())
        self.hasta = QDateEdit(QDate.currentDate())
        for d in (self.desde, self.hasta):
            d.setCalendarPopup(True)
            d.setDisplayFormat("dd/MM/yyyy")
            d.dateChanged.connect(self.refrescar)
        self.l_desde, self.l_hasta = QLabel("Desde:"), QLabel("Hasta:")
        for w in (self.l_desde, self.desde, self.l_hasta, self.hasta):
            filtros.addWidget(w)
        filtros.addStretch()
        self.label_rango = QLabel("")
        filtros.addWidget(self.label_rango)
        raiz.addLayout(filtros)

        grilla = QGridLayout()
        self.c_entra = _Tarjeta("ENTRÓ (cobros de clientes)", VERDE)
        self.c_sale = _Tarjeta("SALIÓ (pagos a proveedores)", ROJO)
        self.c_neto = _Tarjeta("RESULTADO DEL PERÍODO (entró − salió)")
        self.c_cobrar = _Tarjeta("PENDIENTE DE COBRAR (deuda de clientes, hoy)")
        self.c_pagar = _Tarjeta("PENDIENTE DE PAGAR (deuda con proveedores, hoy)")
        self.c_pos = _Tarjeta("POSICIÓN NETA (por cobrar − por pagar)")
        for i, c in enumerate([self.c_entra, self.c_sale, self.c_neto, self.c_cobrar, self.c_pagar, self.c_pos]):
            grilla.addWidget(c, i // 3, i % 3)
        raiz.addLayout(grilla)

        self.label_extra = QLabel("")
        self.label_extra.setWordWrap(True)
        raiz.addWidget(self.label_extra)

        raiz.addWidget(QLabel("Movimientos del período:"))
        self.tabla = QTableWidget(0, 6)
        self.tabla.setHorizontalHeaderLabels(["Fecha", "Tipo", "Cliente / Proveedor", "Concepto", "Medio", "Importe"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tabla.horizontalHeader().setStretchLastSection(True)
        for i, w in enumerate([100, 70, 220, 280, 110]):
            self.tabla.setColumnWidth(i, w)
        self.tabla.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabla.setAlternatingRowColors(True)
        raiz.addWidget(self.tabla, 1)

        self._cambio_periodo()

    # -------------------------------------------------------------- período
    def _rango(self):
        hoy = dt.date.today()
        i = self.combo.currentIndex()
        if i == 0:
            return hoy.replace(day=1), hoy
        if i == 1:
            fin = hoy.replace(day=1) - dt.timedelta(days=1)
            return fin.replace(day=1), fin
        if i == 2:
            return dt.date(hoy.year, 1, 1), hoy
        if i == 3:
            return None, None
        d, h = self.desde.date(), self.hasta.date()
        return dt.date(d.year(), d.month(), d.day()), dt.date(h.year(), h.month(), h.day())

    def _cambio_periodo(self, *_):
        pers = self.combo.currentIndex() == 4
        for w in (self.l_desde, self.desde, self.l_hasta, self.hasta):
            w.setVisible(pers)
        self.refrescar()

    # ---------------------------------------------------------------- datos
    def refrescar(self, *_):
        desde, hasta = self._rango()
        b = repo.balance_general(desde, hasta)
        self.label_rango.setText(
            "Todo el historial" if desde is None else f"{desde:%d/%m/%Y} al {hasta:%d/%m/%Y}")

        self.c_entra.set(b["entradas"], "Pagos recibidos de clientes")
        self.c_sale.set(b["salidas"], "Pagos hechos a proveedores")
        neto = b["entradas"] - b["salidas"]
        self.c_neto.set(neto, "Ganancia de caja" if neto >= 0 else "Salió más de lo que entró",
                        VERDE if neto >= 0 else ROJO)
        self.c_cobrar.set(b["por_cobrar"], "Lo que los clientes todavía nos deben")
        self.c_pagar.set(b["por_pagar"], "Lo que todavía les debemos a proveedores")
        pos = b["por_cobrar"] - b["por_pagar"]
        self.c_pos.set(pos, "A favor" if pos >= 0 else "En contra", VERDE if pos >= 0 else ROJO)

        def medios(d):
            return ", ".join(f"{k}: {_pesos(v)}" for k, v in sorted(d.items(), key=lambda x: -x[1])) or "—"
        self.label_extra.setText(
            f"Facturado a clientes en el período: {_pesos(b['facturado'])}   |   "
            f"Comprado a proveedores en el período: {_pesos(b['comprado'])}\n"
            f"Entradas por medio: {medios(b['por_medio_entradas'])}\n"
            f"Salidas por medio: {medios(b['por_medio_salidas'])}")

        movs = b["movimientos"]
        self.tabla.setRowCount(len(movs))
        for r, m in enumerate(movs):
            fecha = m["fecha"].strftime("%d/%m/%Y") if m["fecha"] else ""
            entrada = m["tipo"] == "Entrada"
            vals = [fecha, m["tipo"], m["contraparte"], m["concepto"], m["medio"],
                    ("+ " if entrada else "− ") + _pesos(m["importe"])]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c in (1, 5):
                    it.setForeground(QColor(VERDE if entrada else ROJO))
                if c == 5:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tabla.setItem(r, c, it)
