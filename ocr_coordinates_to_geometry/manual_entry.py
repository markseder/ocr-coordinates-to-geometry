"""Spreadsheet-style manual coordinate editor."""

from __future__ import annotations

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QKeySequence
from qgis.PyQt.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .core import (
    CoordinateRow,
    clipboard_column_layout,
    is_header_row,
    row_from_decimal,
    row_from_values,
    split_clipboard_table,
)
from .i18n import translate
from .table_values import ExactValueDelegate, RAW_VALUE_ROLE, cell_value, numeric_item
from qgis.PyQt.QtGui import QBrush, QColor


class CoordinateTable(QTableWidget):
    def __init__(self, owner):
        super().__init__(0, 9, owner)
        self.owner = owner

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Paste):
            self.owner.paste_from_clipboard()
            return
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            return
        super().keyPressEvent(event)

    def copy_selection(self):
        indexes = self.selectedIndexes()
        if not indexes:
            return
        min_row, max_row = min(i.row() for i in indexes), max(i.row() for i in indexes)
        min_col, max_col = min(i.column() for i in indexes), max(i.column() for i in indexes)
        lines = []
        for row in range(min_row, max_row + 1):
            values = []
            for column in range(min_col, max_col + 1):
                item = self.item(row, column)
                values.append(item.text() if item else "")
            lines.append("\t".join(values))
        QApplication.clipboard().setText("\n".join(lines))


class ManualCoordinateDialog(QDialog):
    def __init__(self, locale_name, rows=None, seconds_precision=3, parent=None):
        super().__init__(parent)
        self.locale = locale_name
        self.seconds_precision = max(0, min(6, int(seconds_precision)))
        self.setWindowTitle(self.tr("manual_title"))
        self.resize(1050, 560)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(self.tr("manual_hint")))

        self.table = CoordinateTable(self)
        self.table.setItemDelegate(ExactValueDelegate(self.table))
        self.table.setHorizontalHeaderLabels(
            [
                self.tr("point"),
                self.tr("latitude"),
                "′",
                "″",
                self.tr("longitude"),
                "′",
                "″",
                self.tr("latitude_dd"),
                self.tr("longitude_dd"),
            ]
        )
        self.table.cellChanged.connect(self.cell_changed)
        root.addWidget(self.table, 1)

        tools = QHBoxLayout()
        paste_button = QPushButton(self.tr("paste_table"))
        add_button = QPushButton(self.tr("add_row"))
        delete_button = QPushButton(self.tr("delete_rows"))
        clear_button = QPushButton(self.tr("clear_table"))
        paste_button.clicked.connect(self.paste_from_clipboard)
        add_button.clicked.connect(self.add_row)
        delete_button.clicked.connect(self.delete_rows)
        clear_button.clicked.connect(self.clear_table)
        tools.addWidget(paste_button)
        tools.addWidget(add_button)
        tools.addWidget(delete_button)
        tools.addWidget(clear_button)
        tools.addStretch(1)
        root.addLayout(tools)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept_checked)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if rows:
            self.set_rows(rows)
        else:
            self.table.setRowCount(10)
            self.table.setCurrentCell(0, 0)

    def tr(self, key, **values):
        return translate(key, self.locale, **values)

    @staticmethod
    def _number(text):
        return float(text.strip().replace(",", "."))

    def _text(self, row, column):
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _set(self, row, column, value, raw_value=None):
        self.table.setItem(row, column, numeric_item(value, raw_value))

    def _value(self, row, column):
        return cell_value(self.table.item(row, column))

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setCurrentCell(row, 0)

    def delete_rows(self):
        selected = {index.row() for index in self.table.selectedIndexes()}
        for row in sorted(selected, reverse=True):
            self.table.removeRow(row)

    def clear_table(self):
        self.table.blockSignals(True)
        self.table.clearContents()
        self.table.setRowCount(10)
        self.table.blockSignals(False)
        self.table.setCurrentCell(0, 0)

    def set_rows(self, rows):
        self.table.blockSignals(True)
        self.table.setRowCount(max(10, len(rows)))
        for row_index, row in enumerate(rows):
            raw = [row.point_id, row.lat_deg, row.lat_min, row.lat_sec,
                   row.lon_deg, row.lon_min, row.lon_sec]
            for column, value in enumerate(row.as_cells(self.seconds_precision)):
                self._set(row_index, column, value, raw[column])
            self._set(row_index, 7, f"{row.latitude:.8f}", row.latitude)
            self._set(row_index, 8, f"{row.longitude:.8f}", row.longitude)
        self.table.blockSignals(False)

    def paste_from_clipboard(self):
        rows = split_clipboard_table(QApplication.clipboard().text())
        if rows and is_header_row(rows[0]):
            rows = rows[1:]
        if not rows:
            QMessageBox.warning(self, self.tr("clipboard"), self.tr("clipboard_table_empty"))
            return
        width = max(len(row) for row in rows)
        target_columns, auto_number, prefer_dd = clipboard_column_layout(width)
        start_row = max(0, self.table.currentRow())
        required = start_row + len(rows)
        if self.table.rowCount() < required:
            self.table.setRowCount(required)
        self.table.blockSignals(True)
        for offset, values in enumerate(rows):
            row_index = start_row + offset
            # Replacement must never reuse coordinates from an older row.
            for column in range(1, 9):
                self._set(row_index, column, "")
            if auto_number and not self._text(row_index, 0):
                self._set(row_index, 0, row_index + 1)
            for column, value in zip(target_columns, values):
                self._set(row_index, column, value)
            self._sync_row(row_index, prefer_dd=prefer_dd)
        self.table.blockSignals(False)

    def cell_changed(self, row, column):
        self.table.blockSignals(True)
        try:
            item = self.table.item(row, column)
            if item is not None:
                item.setData(RAW_VALUE_ROLE, None)
            self._sync_row(row, prefer_dd=column in {7, 8}, changed_column=column)
        finally:
            self.table.blockSignals(False)

    def _sync_row(self, row, prefer_dd=False, changed_column=None):
        if not self._text(row, 0):
            self._set(row, 0, row + 1)
        for dms_columns, dd_column in (((1, 2, 3), 7), ((4, 5, 6), 8)):
            if changed_column is not None and changed_column not in (*dms_columns, dd_column):
                continue
            source_columns = (dd_column,) if prefer_dd else dms_columns
            target_columns = dms_columns if prefer_dd else (dd_column,)
            try:
                if prefer_dd:
                    value = self._value(row, dd_column)
                    parsed = row_from_decimal(1, value if dd_column == 7 else 0,
                                              value if dd_column == 8 else 0)
                    raw = (parsed.lat_deg, parsed.lat_min, parsed.lat_sec) if dd_column == 7 else (
                        parsed.lon_deg, parsed.lon_min, parsed.lon_sec)
                    cells = parsed.as_cells(self.seconds_precision)
                    for column, exact in zip(dms_columns, raw):
                        self._set(row, column, cells[column], exact)
                else:
                    values = [0.0] * 6
                    for column in dms_columns:
                        values[column - 1] = self._value(row, column)
                    parsed = row_from_values([1, *values])
                    value = parsed.latitude if dd_column == 7 else parsed.longitude
                    self._set(row, dd_column, f"{value:.8f}", value)
                for column in source_columns:
                    item = self.table.item(row, column)
                    if item is not None:
                        item.setBackground(QBrush())
                        item.setToolTip("")
            except (ValueError, TypeError, OverflowError) as error:
                # Invalidate derived cells; acceptance cannot fall back to stale data.
                for column in target_columns:
                    self._set(row, column, "")
                for column in source_columns:
                    item = self.table.item(row, column)
                    if item is not None:
                        item.setBackground(QBrush(QColor("#ffcdd2")))
                        item.setToolTip(str(error))

    def coordinate_rows(self) -> list[CoordinateRow]:
        rows = []
        for row_index in range(self.table.rowCount()):
            values = [self._text(row_index, column) for column in range(9)]
            if not any(values):
                continue
            try:
                if all(values[column] for column in range(7)):
                    row = row_from_values([self._value(row_index, c) for c in range(7)])
                elif values[0] and values[7] and values[8]:
                    point_value = self._value(row_index, 0)
                    if point_value != int(point_value) or point_value < 1:
                        raise ValueError("Point number must be a positive integer")
                    row = row_from_decimal(
                        int(point_value),
                        self._value(row_index, 7),
                        self._value(row_index, 8),
                    )
                else:
                    raise ValueError(self.tr("manual_incomplete_row", row=row_index + 1))
            except (ValueError, OverflowError) as error:
                raise ValueError(self.tr("manual_row_error", row=row_index + 1, error=error))
            rows.append(row)
        return rows

    def accept_checked(self):
        try:
            rows = self.coordinate_rows()
        except ValueError as error:
            QMessageBox.critical(self, self.tr("table_error"), str(error))
            return
        if not rows:
            QMessageBox.warning(self, self.tr("empty_table"), self.tr("nothing_to_save"))
            return
        self._accepted_rows = rows
        self.accept()

    @property
    def accepted_rows(self):
        return getattr(self, "_accepted_rows", [])
