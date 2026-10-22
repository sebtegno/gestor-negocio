import unicodedata

from PySide6.QtWidgets import QLineEdit, QCompleter
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, Signal
from PySide6.QtGui import QStandardItemModel, QStandardItem


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return t.lower()


class _FiltroPalabras(QSortFilterProxyModel):
    """Muestra solo los ítems que contienen TODAS las palabras escritas (en cualquier orden)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._palabras: list[str] = []

    def set_texto(self, texto: str):
        self._palabras = _norm(texto).split()
        self.invalidateFilter()

    def filterAcceptsRow(self, fila: int, padre: QModelIndex) -> bool:
        if not self._palabras:
            return True
        item = self.sourceModel().index(fila, 0, padre).data(Qt.DisplayRole) or ""
        texto = _norm(item)
        return all(p in texto for p in self._palabras)


class ComboBuscable(QLineEdit):
    """
    Campo de texto con lista de sugerencias: al escribir muestra SOLO las
    opciones que contienen lo escrito (no autocompleta ni cambia el texto
    por su cuenta). Se elige con el mouse o con las flechas + Enter.
    Cada ítem guarda su id, accesible con valor_seleccionado().
    """

    seleccionado = Signal()  # el usuario eligió (o terminó de escribir) un ítem válido

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fuente = QStandardItemModel(self)
        self._proxy = _FiltroPalabras(self)
        self._proxy.setSourceModel(self._fuente)
        self._id_elegido = None
        self._texto_elegido = ""

        comp = QCompleter(self._proxy, self)
        comp.setCompletionMode(QCompleter.UnfilteredPopupCompletion)  # el filtro lo hace el proxy
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setMaxVisibleItems(8)
        comp.activated[QModelIndex].connect(self._al_elegir)
        self.setCompleter(comp)
        self.setClearButtonEnabled(True)
        self.setPlaceholderText("Escribí para buscar...")
        self.textEdited.connect(self._al_escribir)
        self.editingFinished.connect(self._al_terminar)

    # --- API ---------------------------------------------------------------
    def cargar_items(self, items: list[tuple[object, str]]):
        """items: lista de (id, texto_a_mostrar)"""
        self._fuente.clear()
        for item_id, texto in items:
            it = QStandardItem(texto)
            it.setData(item_id, Qt.UserRole)
            self._fuente.appendRow(it)
        self._id_elegido, self._texto_elegido = None, ""
        self._proxy.set_texto("")
        self.clear()

    def lineEdit(self):  # compatibilidad con el QComboBox anterior
        return self

    def setCurrentIndex(self, indice: int):
        if 0 <= indice < self._fuente.rowCount():
            it = self._fuente.item(indice)
            self._id_elegido, self._texto_elegido = it.data(Qt.UserRole), it.text()
            self.setText(it.text())
        else:
            self._id_elegido, self._texto_elegido = None, ""
            self.clear()

    def limpiar(self):
        self.setCurrentIndex(-1)

    def valor_seleccionado(self):
        """
        Id del ítem elegido. Si no se eligió de la lista pero el texto coincide
        exacto con uno, o deja una única opción posible, devuelve ese. Si hay
        varias opciones posibles sin elegir, None.
        """
        texto = self.text().strip()
        if not texto:
            return None
        if self._id_elegido is not None and texto == self._texto_elegido:
            return self._id_elegido
        exacto = [self._fuente.item(r) for r in range(self._fuente.rowCount())
                  if _norm(self._fuente.item(r).text()).strip() == _norm(texto).strip()]
        if len(exacto) == 1:
            return exacto[0].data(Qt.UserRole)
        palabras = _norm(texto).split()
        posibles = [self._fuente.item(r) for r in range(self._fuente.rowCount())
                    if all(p in _norm(self._fuente.item(r).text()) for p in palabras)]
        return posibles[0].data(Qt.UserRole) if len(posibles) == 1 else None

    # --- interno -----------------------------------------------------------
    def _al_escribir(self, texto: str):
        self._id_elegido, self._texto_elegido = None, ""
        self._proxy.set_texto(texto)
        if texto.strip() and self._proxy.rowCount() > 0:
            self.completer().complete()
        else:
            self.completer().popup().hide()

    def _al_elegir(self, indice: QModelIndex):
        self._id_elegido = indice.data(Qt.UserRole)
        self._texto_elegido = indice.data(Qt.DisplayRole)
        self.setText(self._texto_elegido)
        self.seleccionado.emit()

    def _al_terminar(self):
        if self.valor_seleccionado() is not None:
            self.seleccionado.emit()
