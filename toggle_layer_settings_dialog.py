from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
    QPushButton, QAbstractItemView, QComboBox, QHeaderView,
    QKeySequenceEdit, QWidget, QToolButton, QSizePolicy
)
from qgis.core import QgsProject


class KeyCell(QWidget):
    """
    Cell widget: QKeySequenceEdit + clear button.
    Forces exactly ONE shortcut (one chord). If user types more, keeps only the first.
    """
    def __init__(self, parent=None, initial_key_text=""):
        super().__init__(parent)

        self._guard = False

        self.edit = QKeySequenceEdit(self)
        if initial_key_text:
            try:
                self.edit.setKeySequence(QKeySequence(initial_key_text))
            except Exception:
                pass

        self.btn = QToolButton(self)
        self.btn.setText("X")
        self.btn.setToolTip("Clear")
        self.btn.setAutoRaise(True)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.btn, 0)

        self.btn.clicked.connect(self.clear)

        # Force single-chord shortcuts
        self.edit.keySequenceChanged.connect(self._force_single_chord)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _force_single_chord(self, ks: QKeySequence):
        if self._guard:
            return
        try:
            # QKeySequence can hold up to 4 chords; keep only the first.
            first = ks[0]  # int
            # If empty, do nothing
            if not first:
                return
            self._guard = True
            self.edit.setKeySequence(QKeySequence(first))
        finally:
            self._guard = False
        # End capture immediately so extra keys don't append.
        self.edit.clearFocus()

    def clear(self):
        try:
            self._guard = True
            self.edit.setKeySequence(QKeySequence())
        finally:
            self._guard = False

    def key_text(self) -> str:
        try:
            return self.edit.keySequence().toString().strip()
        except Exception:
            return ""



class ToggleLayerSettingsDialog(QDialog):
    def __init__(self, parent=None, mappings=None):
        super().__init__(parent)
        self.setWindowTitle("Toggle Layer")
        self.setMinimumWidth(720)

        self._mappings = mappings or []

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["Key", "Layer name"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)

        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_plus = QPushButton("+")
        self.btn_minus = QPushButton("-")
        self.btn_plus.setFixedWidth(40)
        self.btn_minus.setFixedWidth(40)

        btn_row.addWidget(self.btn_plus)
        btn_row.addWidget(self.btn_minus)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        bottom = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        bottom.addStretch(1)
        bottom.addWidget(self.btn_ok)
        bottom.addWidget(self.btn_cancel)
        layout.addLayout(bottom)

        self.btn_plus.clicked.connect(self.add_row)
        self.btn_minus.clicked.connect(self.remove_selected_row)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        # load saved rows
        for m in self._mappings:
            self.add_row(m.get("key", ""), m.get("layer", ""))

        if self.table.rowCount() == 0:
            self.add_row()

    def _layer_names(self):
        proj = QgsProject.instance()
        names = []
        for lyr in proj.mapLayers().values():
            n = lyr.name()
            if n and n not in names:
                names.append(n)
        names.sort(key=lambda x: x.lower())
        return names

    def add_row(self, key_text="", layer_text=""):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Key cell widget (edit + clear)
        key_cell = KeyCell(self.table, key_text)
        self.table.setCellWidget(row, 0, key_cell)

        # Layer picker (editable)
        combo = QComboBox(self.table)
        combo.setEditable(True)
        combo.addItems(self._layer_names())
        if layer_text:
            combo.setEditText(layer_text)
        self.table.setCellWidget(row, 1, combo)

        self.table.setRowHeight(row, 28)
        self.table.selectRow(row)

    def remove_selected_row(self):
        r = self.table.currentRow()
        if r < 0:
            return
        self.table.removeRow(r)
        if self.table.rowCount() > 0:
            self.table.selectRow(min(r, self.table.rowCount() - 1))

    def get_mappings(self):
        out = []
        for r in range(self.table.rowCount()):
            key_cell = self.table.cellWidget(r, 0)
            combo = self.table.cellWidget(r, 1)

            key = key_cell.key_text() if key_cell else ""
            layer = combo.currentText().strip() if combo else ""
            out.append({"key": key, "layer": layer})

        # drop empty lines
        out = [m for m in out if (m.get("key") or "").strip() and (m.get("layer") or "").strip()]
        return out
