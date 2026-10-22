from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt, QSortFilterProxyModel
from PySide6.QtGui import QStandardItemModel, QStandardItem


class ComboBuscable(QComboBox):
    """
    QComboBox editable con autocompletado por coincidencia parcial
    (no solo por prefijo) e insensible a mayúsculas/minúsculas.
    Cada ítem guarda su id como userData, accesible con valor_seleccionado().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)

        self._modelo_fuente = QStandardItemModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._modelo_fuente)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setModel(self._proxy)

        completer = self.completer()
        completer.setCompletionMode(completer.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)

        self.lineEdit().textEdited.connect(self._filtrar)

    def cargar_items(self, items: list[tuple[object, str]]):
        """items: lista de (id, texto_a_mostrar)"""
        self.blockSignals(True)
        self._modelo_fuente.clear()
        for item_id, texto in items:
            item = QStandardItem(texto)
            item.setData(item_id, Qt.UserRole)
            self._modelo_fuente.appendRow(item)
        self.setCurrentIndex(-1)
        self.lineEdit().clear()
        self.blockSignals(False)

    def _filtrar(self, texto: str):
        self._proxy.setFilterFixedString(texto)

    def valor_seleccionado(self):
        """
        Devuelve el id asociado al texto actual, buscando primero una
        coincidencia exacta y si no la hay, la primera coincidencia parcial.
        None si no matchea nada.
        """
        texto = self.currentText().strip().lower()
        if not texto:
            return None

        coincidencia_parcial = None
        for row in range(self._modelo_fuente.rowCount()):
            item = self._modelo_fuente.item(row)
            item_texto = item.text().strip().lower()
            if item_texto == texto:
                return item.data(Qt.UserRole)
            if texto in item_texto and coincidencia_parcial is None:
                coincidencia_parcial = item.data(Qt.UserRole)
        return coincidencia_parcial
