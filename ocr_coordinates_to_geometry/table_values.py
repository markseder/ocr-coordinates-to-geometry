"""Keep numeric values separate from their rounded table presentation."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QStyledItemDelegate, QTableWidgetItem

from .core import format_number


RAW_VALUE_ROLE = Qt.ItemDataRole.UserRole
OCR_SOURCE_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def numeric_item(text, raw_value=None):
    item = QTableWidgetItem(str(text))
    if raw_value is not None:
        item.setData(RAW_VALUE_ROLE, float(raw_value))
    return item


def cell_value(item):
    if item is None or not item.text().strip():
        raise ValueError("Empty coordinate cell")
    raw = item.data(RAW_VALUE_ROLE)
    return float(raw) if raw is not None else float(item.text().strip().replace(",", "."))


class ExactValueDelegate(QStyledItemDelegate):
    """Opening an editor exposes the stored value, not the rounded preview."""

    def setEditorData(self, editor, index):
        raw = index.data(RAW_VALUE_ROLE)
        if raw is not None and hasattr(editor, "setText"):
            editor.setText(format_number(float(raw)))
        else:
            super().setEditorData(editor, index)
