"""Qt dialog for OCR preview and geometry creation."""

from __future__ import annotations

import os
import csv
import platform
import tempfile
import time
from pathlib import Path

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QBrush, QColor, QDesktopServices, QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressDialog,
    QLineEdit,
    QSpinBox,
    QApplication,
    QVBoxLayout,
    QTextEdit,
)
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsApplication,
    QgsSettings,
    Qgis,
    QgsVectorLayer,
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
)
from qgis.gui import QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import QVariant

from .core import (
    CoordinateRow,
    CSV_HEADERS,
    closed_vertices,
    coordinate_csv_row,
    coordinate_quality_issues,
    parse_coordinate_lines,
    row_from_values,
)
from .ocr import OcrLine, OcrUnavailableError, recognize_lines
from .i18n import translate
from .manual_entry import ManualCoordinateDialog


class OcrCoordinatesDialog(QDialog):
    SETTINGS_PREFIX = "OCR2Geometry"

    def __init__(self, iface, locale_name=None, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.locale = locale_name or QgsApplication.locale()
        self.settings = QgsSettings()
        self.image_path = ""
        self.temp_image_path = ""
        self.row_confidences = []
        self.setWindowTitle(self.tr("window_title"))
        self.resize(
            int(self.settings.value(f"{self.SETTINGS_PREFIX}/width", 820)),
            int(self.settings.value(f"{self.SETTINGS_PREFIX}/height", 620)),
        )
        self._build_ui()
        self._restore_options()

    def tr(self, key, **values):
        return translate(key, self.locale, **values)

    def _build_ui(self):
        root = QVBoxLayout(self)
        buttons = QHBoxLayout()
        self.open_button = QPushButton(self.tr("open_image"))
        self.paste_button = QPushButton(self.tr("paste_clipboard"))
        self.paste_text_button = QPushButton(self.tr("paste_text"))
        self.recognize_button = QPushButton(self.tr("recognize"))
        self.install_ocr_button = QPushButton(self.tr("install_ocr"))
        self.about_button = QPushButton(self.tr("about"))
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.paste_button)
        buttons.addWidget(self.paste_text_button)
        buttons.addStretch(1)
        buttons.addWidget(self.install_ocr_button)
        buttons.addWidget(self.about_button)
        buttons.addWidget(self.recognize_button)
        root.addLayout(buttons)

        self.preview = QLabel(self.tr("preview_hint"))
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(150)
        self.preview.setStyleSheet("QLabel { border: 1px solid #999; background: #f4f4f4; }")
        root.addWidget(self.preview)

        input_group = QGroupBox(self.tr("input_group"))
        input_form = QFormLayout(input_group)
        self.format_combo = QComboBox()
        for key, value in (
            ("format_auto", "auto"),
            ("format_dms", "dms"),
            ("format_dm", "dm"),
            ("format_dd", "dd"),
        ):
            self.format_combo.addItem(self.tr(key), value)
        self.axis_combo = QComboBox()
        self.axis_combo.addItem(self.tr("axis_lat_lon"), "lat_lon")
        self.axis_combo.addItem(self.tr("axis_lon_lat"), "lon_lat")
        self.order_combo = QComboBox()
        self.order_combo.addItem(self.tr("sort_points"), True)
        self.order_combo.addItem(self.tr("preserve_order"), False)
        self.crs_widget = QgsProjectionSelectionWidget()
        self.crs_widget.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        self.seconds_precision_spin = QSpinBox()
        self.seconds_precision_spin.setRange(0, 6)
        self.seconds_precision_spin.setValue(3)
        input_form.addRow(self.tr("coordinate_format"), self.format_combo)
        input_form.addRow(self.tr("axis_order"), self.axis_combo)
        input_form.addRow(self.tr("row_order"), self.order_combo)
        input_form.addRow(self.tr("source_crs"), self.crs_widget)
        input_form.addRow(self.tr("seconds_precision"), self.seconds_precision_spin)
        root.addWidget(input_group)

        self.table = QTableWidget(0, 9)
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
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        self.confidence_legend = QLabel(self.tr("confidence_legend"))
        self.confidence_legend.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self.confidence_legend)

        table_buttons = QHBoxLayout()
        self.add_row_button = QPushButton(self.tr("add_row"))
        self.delete_row_button = QPushButton(self.tr("delete_rows"))
        self.save_csv_button = QPushButton(self.tr("save_csv"))
        table_buttons.addWidget(self.add_row_button)
        table_buttons.addWidget(self.delete_row_button)
        table_buttons.addStretch(1)
        table_buttons.addWidget(self.save_csv_button)
        root.addLayout(table_buttons)

        options = QGroupBox(self.tr("result_group"))
        option_grid = QGridLayout(options)
        self.layer_name_edit = QLineEdit()
        self.layer_name_edit.setPlaceholderText("OCR2Geometry")
        self.points_check = QCheckBox(self.tr("create_points"))
        self.points_check.setChecked(True)
        self.labels_check = QCheckBox(self.tr("label_points"))
        self.labels_check.setChecked(True)
        self.close_check = QCheckBox(self.tr("close_line"))
        self.close_check.setChecked(True)
        self.polygon_check = QCheckBox(self.tr("create_polygon"))
        option_grid.addWidget(QLabel(self.tr("layer_name")), 0, 0)
        option_grid.addWidget(self.layer_name_edit, 0, 1)
        option_grid.addWidget(self.points_check, 1, 0)
        option_grid.addWidget(self.labels_check, 1, 1)
        option_grid.addWidget(self.close_check, 2, 0, 1, 2)
        option_grid.addWidget(self.polygon_check, 3, 0, 1, 2)
        root.addWidget(options)

        bottom = QHBoxLayout()
        self.status = QLabel(self.tr("ready"))
        self.create_button = QPushButton(self.tr("add_to_qgis"))
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.create_button)
        root.addLayout(bottom)

        self.open_button.clicked.connect(self.open_image)
        self.paste_button.clicked.connect(self.paste_image)
        self.paste_text_button.clicked.connect(self.paste_coordinate_text)
        self.recognize_button.clicked.connect(self.recognize)
        self.install_ocr_button.clicked.connect(self.install_ocr)
        self.about_button.clicked.connect(self.show_about)
        self.add_row_button.clicked.connect(self.add_empty_row)
        self.delete_row_button.clicked.connect(self.delete_selected_rows)
        self.save_csv_button.clicked.connect(self.save_csv)
        self.create_button.clicked.connect(self.create_geometry)
        self.table.cellChanged.connect(self.update_decimal_preview)
        self.seconds_precision_spin.valueChanged.connect(self.refresh_seconds_precision)

    def _restore_options(self):
        for name, widget, default in (
            ("points", self.points_check, True),
            ("labels", self.labels_check, True),
            ("close", self.close_check, True),
            ("polygon", self.polygon_check, False),
        ):
            value = self.settings.value(f"{self.SETTINGS_PREFIX}/{name}", default, type=bool)
            widget.setChecked(value)
        for key, combo in (
            ("format", self.format_combo),
            ("axis_order", self.axis_combo),
            ("row_order", self.order_combo),
        ):
            saved = self.settings.value(f"{self.SETTINGS_PREFIX}/{key}", None)
            if saved is not None:
                index = combo.findData(saved if key != "row_order" else str(saved).lower() == "true")
                if index >= 0:
                    combo.setCurrentIndex(index)
        self.layer_name_edit.setText(
            self.settings.value(f"{self.SETTINGS_PREFIX}/layer_name", "OCR2Geometry")
        )
        saved_crs = self.settings.value(f"{self.SETTINGS_PREFIX}/source_crs", "EPSG:4326")
        crs = QgsCoordinateReferenceSystem(str(saved_crs))
        if crs.isValid():
            self.crs_widget.setCrs(crs)
        self.seconds_precision_spin.setValue(
            int(self.settings.value(f"{self.SETTINGS_PREFIX}/seconds_precision", 3))
        )

    def _save_options(self):
        self.settings.setValue(f"{self.SETTINGS_PREFIX}/width", self.width())
        self.settings.setValue(f"{self.SETTINGS_PREFIX}/height", self.height())
        for name, widget in (
            ("points", self.points_check),
            ("labels", self.labels_check),
            ("close", self.close_check),
            ("polygon", self.polygon_check),
        ):
            self.settings.setValue(f"{self.SETTINGS_PREFIX}/{name}", widget.isChecked())
        self.settings.setValue(f"{self.SETTINGS_PREFIX}/format", self.format_combo.currentData())
        self.settings.setValue(f"{self.SETTINGS_PREFIX}/axis_order", self.axis_combo.currentData())
        self.settings.setValue(f"{self.SETTINGS_PREFIX}/row_order", self.order_combo.currentData())
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}/layer_name", self.layer_name_edit.text().strip()
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}/source_crs", self.crs_widget.crs().authid()
        )
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}/seconds_precision",
            self.seconds_precision_spin.value(),
        )

    def closeEvent(self, event):
        self._save_options()
        super().closeEvent(event)

    def add_empty_row(self):
        row_index = self.table.rowCount()
        self.table.blockSignals(True)
        self.table.insertRow(row_index)
        next_point = row_index + 1
        self.table.setItem(row_index, 0, QTableWidgetItem(str(next_point)))
        for column in range(1, 7):
            self.table.setItem(row_index, column, QTableWidgetItem("0"))
        self._set_decimal_cells(row_index, row_from_values([next_point, 0, 0, 0, 0, 0, 0]))
        self.table.blockSignals(False)
        self.row_confidences.append(())
        self.table.setCurrentCell(row_index, 1)

    def delete_selected_rows(self):
        selected = {index.row() for index in self.table.selectedIndexes()}
        for row_index in sorted(selected, reverse=True):
            self.table.removeRow(row_index)
            if row_index < len(self.row_confidences):
                self.row_confidences.pop(row_index)

    def open_image(self):
        start_dir = self.settings.value(f"{self.SETTINGS_PREFIX}/last_image_dir", "")
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("choose_table"), start_dir, self.tr("images_filter")
        )
        if path:
            self.settings.setValue(f"{self.SETTINGS_PREFIX}/last_image_dir", str(Path(path).parent))
            self.set_image(path)

    def paste_image(self):
        from qgis.PyQt.QtWidgets import QApplication

        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.warning(self, self.tr("clipboard"), self.tr("clipboard_empty"))
            return
        path = os.path.join(tempfile.gettempdir(), "qgis_ocr_coordinates_clipboard.png")
        if not image.save(path, "PNG"):
            QMessageBox.critical(self, self.tr("error"), self.tr("clipboard_save_error"))
            return
        self.temp_image_path = path
        self.set_image(path)

    def paste_coordinate_text(self):
        try:
            current_rows = self.rows_from_table(apply_sort=False)
        except ValueError:
            current_rows = []
        dialog = ManualCoordinateDialog(
            self.locale,
            current_rows,
            self.seconds_precision_spin.value(),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.fill_table(dialog.accepted_rows)
            self.status.setText(
                self.tr("manual_rows_loaded", count=len(dialog.accepted_rows))
            )

    def set_image(self, path):
        self.image_path = path
        pixmap = QPixmap(path)
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.status.setText(os.path.basename(path))

    def recognize(self):
        if not self.image_path:
            QMessageBox.warning(self, self.tr("no_image"), self.tr("open_first"))
            return
        self.status.setText(self.tr("recognizing"))
        from .dependencies import rapidocr_available

        if not rapidocr_available():
            answer = QMessageBox.question(
                self,
                self.tr("ocr_setup_title"),
                self.tr("ocr_setup_question"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes or not self.install_ocr():
                self.status.setText(self.tr("ocr_missing"))
                return
        try:
            lines = recognize_lines(self.image_path)
        except OcrUnavailableError as error:
            QMessageBox.critical(self, self.tr("ocr_missing"), str(error))
            self.status.setText(self.tr("ocr_need_install"))
            return
        self.process_coordinate_lines(lines)

    def process_coordinate_lines(self, lines):
        prepared = [
            (line.text, line.confidences) if isinstance(line, OcrLine) else (str(line), ())
            for line in lines
        ]
        text_lines = [text for text, _ in prepared]
        rows, warnings, detected = parse_coordinate_lines(
            text_lines,
            coordinate_format=self.format_combo.currentData(),
            axis_order=self.axis_combo.currentData(),
            sort_by_point=False,
        )
        accepted_confidences = []
        for text, confidences in prepared:
            accepted, _, _ = parse_coordinate_lines(
                [text],
                coordinate_format=self.format_combo.currentData(),
                axis_order=self.axis_combo.currentData(),
                sort_by_point=False,
            )
            if accepted:
                accepted_confidences.append(tuple(confidences))
        paired = list(zip(rows, accepted_confidences))
        if bool(self.order_combo.currentData()):
            paired.sort(key=lambda item: item[0].point_id)
        rows = [row for row, _ in paired]
        confidences = [values for _, values in paired]
        self.fill_table(rows, confidences)
        if rows:
            format_name = (detected or self.format_combo.currentData() or "auto").upper()
            self.status.setText(
                self.tr("detected_format", format=format_name, count=len(rows))
            )
        else:
            self.status.setText(self.tr("no_coordinates"))
        if warnings:
            QMessageBox.warning(self, self.tr("check_recognition"), "\n".join(warnings[:12]))

    def install_ocr(self):
        from .dependencies import install_rapidocr, rapidocr_available, vendor_directory

        if rapidocr_available():
            self.status.setText(self.tr("ocr_already"))
            return True
        progress = QProgressDialog(self.tr("preparing_install"), self.tr("cancel"), 0, 0, self)
        progress.setWindowTitle(self.tr("ocr_setup_title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        last_update = [0.0]

        def update_progress(line):
            now = time.monotonic()
            if now - last_update[0] > 0.1:
                progress.setLabelText(line[:160] or self.tr("downloading"))
                QApplication.processEvents()
                last_update[0] = now

        ok, log = install_rapidocr(update_progress, progress.wasCanceled)
        progress.close()
        if ok:
            self.status.setText(self.tr("ocr_ready_status"))
            QMessageBox.information(
                self,
                self.tr("ocr_ready_title"),
                self.tr("ocr_ready_text"),
            )
            return True
        tail = "\n".join(log.splitlines()[-12:])
        QMessageBox.critical(
            self,
            self.tr("ocr_install_failed"),
            f"{self.tr('ocr_install_help')}\n\n{vendor_directory()}\n\n{tail}",
        )
        self.status.setText(self.tr("ocr_install_error"))
        return False

    def diagnostics_text(self):
        from .dependencies import qgis_python_executable, rapidocr_available, vendor_directory

        try:
            python_executable = str(qgis_python_executable())
        except RuntimeError as error:
            python_executable = str(error)
        return "\n".join(
            [
                "OCR2Geometry: 1.0.0-beta1",
                f"QGIS: {Qgis.QGIS_VERSION}",
                f"Locale: {self.locale}",
                f"OS: {platform.platform()}",
                f"Python: {platform.python_version()}",
                f"QGIS Python: {python_executable}",
                f"RapidOCR: {'available' if rapidocr_available() else 'not installed'}",
                f"OCR directory: {vendor_directory()}",
            ]
        )

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("about_title"))
        dialog.resize(620, 430)
        layout = QVBoxLayout(dialog)
        title = QLabel("<h2>OCR2Geometry 1.0.0-beta1</h2>")
        title.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(title)
        description = QLabel(
            "Screenshot → OCR → reviewed coordinates → QGIS geometry<br>"
            "<a href='https://github.com/markseder/ocr-coordinates-to-geometry'>"
            "github.com/markseder/ocr-coordinates-to-geometry</a>"
        )
        description.setOpenExternalLinks(True)
        layout.addWidget(description)
        layout.addWidget(QLabel(self.tr("developers")))
        layout.addWidget(QLabel(self.tr("diagnostics")))
        diagnostics = QTextEdit()
        diagnostics.setReadOnly(True)
        diagnostics.setPlainText(self.diagnostics_text())
        layout.addWidget(diagnostics, 1)

        buttons = QDialogButtonBox()
        copy_button = buttons.addButton(
            self.tr("copy_diagnostics"), QDialogButtonBox.ButtonRole.ActionRole
        )
        github_button = buttons.addButton(
            self.tr("open_github"), QDialogButtonBox.ButtonRole.ActionRole
        )
        support_button = buttons.addButton(
            self.tr("support_project"), QDialogButtonBox.ButtonRole.ActionRole
        )
        close_button = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        close_button.setText(self.tr("close"))
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(diagnostics.toPlainText())
        )
        github_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/markseder/ocr-coordinates-to-geometry")
            )
        )
        support_button.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/markseder/ocr-coordinates-to-geometry")
            )
        )
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def fill_table(self, rows, confidences=None):
        self.row_confidences = list(confidences or [()] * len(rows))
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, text in enumerate(
                row.as_cells(self.seconds_precision_spin.value())
            ):
                self.table.setItem(row_index, column, QTableWidgetItem(text))
            self._set_decimal_cells(row_index, row)
            self._apply_confidence_style(row_index)
        self.table.blockSignals(False)

    def refresh_seconds_precision(self):
        if self.table.rowCount() == 0:
            return
        try:
            rows = self.rows_from_table(apply_sort=False)
        except ValueError:
            return
        self.fill_table(rows, list(self.row_confidences))

    def _apply_confidence_style(self, row_index):
        if row_index >= len(self.row_confidences):
            return
        confidences = self.row_confidences[row_index]
        known = [value for value in confidences if value is not None]
        if not known:
            return
        row_score = min(known)
        for column in range(self.table.columnCount()):
            item = self.table.item(row_index, column)
            if item is None:
                continue
            score = (
                confidences[column]
                if column < 7 and len(confidences) == 7 and confidences[column] is not None
                else row_score
            )
            color = "#c8e6c9" if score >= 0.90 else "#fff3b0" if score >= 0.75 else "#ffcdd2"
            item.setBackground(QBrush(QColor(color)))
            item.setToolTip(self.tr("confidence_value", value=f"{score * 100:.1f}"))

    def _clear_confidence_style(self, row_index):
        for column in range(self.table.columnCount()):
            item = self.table.item(row_index, column)
            if item is not None:
                item.setBackground(QBrush())
                item.setToolTip("")

    def _set_decimal_cells(self, row_index, row):
        for column, value in ((7, row.latitude), (8, row.longitude)):
            item = QTableWidgetItem(f"{value:.8f}")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_index, column, item)

    def update_decimal_preview(self, row_index, column):
        if column >= 7:
            return
        if row_index < len(self.row_confidences):
            self.row_confidences[row_index] = ()
            self._clear_confidence_style(row_index)
        try:
            values = []
            for current_column in range(7):
                item = self.table.item(row_index, current_column)
                if item is None or not item.text().strip():
                    return
                values.append(float(item.text().strip().replace(",", ".")))
            row = row_from_values(values)
        except ValueError:
            return
        self.table.blockSignals(True)
        self._set_decimal_cells(row_index, row)
        self.table.blockSignals(False)

    def rows_from_table(self, apply_sort=True) -> list[CoordinateRow]:
        rows = []
        for row_index in range(self.table.rowCount()):
            values = []
            for column in range(7):
                item = self.table.item(row_index, column)
                if item is None or not item.text().strip():
                    raise ValueError(self.tr("empty_cell", row=row_index + 1))
                values.append(float(item.text().strip().replace(",", ".")))
            rows.append(row_from_values(values))
        if apply_sort and bool(self.order_combo.currentData()):
            rows.sort(key=lambda row: row.point_id)
        point_ids = [row.point_id for row in rows]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError(self.tr("duplicate_ids"))
        return rows

    def save_csv(self):
        try:
            rows = self.rows_from_table(apply_sort=False)
        except ValueError as error:
            QMessageBox.critical(self, self.tr("table_error"), str(error))
            return
        if not rows:
            QMessageBox.warning(self, self.tr("empty_table"), self.tr("nothing_to_save"))
            return
        start_dir = self.settings.value(f"{self.SETTINGS_PREFIX}/last_csv_dir", "")
        base_name = self.layer_name_edit.text().strip() or "OCR2Geometry"
        safe_name = "".join("_" if char in '<>:"/\\|?*' else char for char in base_name)
        suggested = str(Path(start_dir) / f"{safe_name}.csv") if start_dir else f"{safe_name}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("save_csv_title"), suggested, self.tr("csv_filter")
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as output:
                writer = csv.writer(output, delimiter=";", lineterminator="\n")
                writer.writerow(CSV_HEADERS)
                for row_index, row in enumerate(rows):
                    confidences = (
                        self.row_confidences[row_index]
                        if row_index < len(self.row_confidences)
                        else ()
                    )
                    writer.writerow(
                        coordinate_csv_row(
                            row, confidences, self.seconds_precision_spin.value()
                        )
                    )
        except OSError as error:
            QMessageBox.critical(
                self, self.tr("csv_save_error"), self.tr("csv_save_failed", error=error)
            )
            return
        self.settings.setValue(
            f"{self.SETTINGS_PREFIX}/last_csv_dir", str(Path(path).parent)
        )
        self.status.setText(self.tr("csv_saved_status", count=len(rows)))
        QMessageBox.information(
            self,
            self.tr("csv_saved_title"),
            self.tr("csv_saved", count=len(rows), path=path),
        )

    @staticmethod
    def _format_distance(metres):
        return f"{metres / 1000:.3f} km" if metres >= 1000 else f"{metres:.2f} m"

    @staticmethod
    def _format_area(square_metres):
        return (
            f"{square_metres / 1_000_000:.3f} km²"
            if square_metres >= 1_000_000
            else f"{square_metres:.2f} m²"
        )

    def review_quality(self, rows, line_geometry, polygon_geometry, source_crs):
        warnings = []
        for issue, point_ids in coordinate_quality_issues(rows):
            warnings.append(
                self.tr(issue, points=", ".join(str(value) for value in point_ids))
            )
        low_confidence_points = []
        for row_index, confidences in enumerate(self.row_confidences):
            known = [value for value in confidences if value is not None]
            if known and min(known) < 0.75:
                item = self.table.item(row_index, 0)
                low_confidence_points.append(item.text() if item is not None else row_index + 1)
        if low_confidence_points:
            warnings.append(
                self.tr(
                    "low_confidence_points",
                    points=", ".join(str(value) for value in low_confidence_points),
                )
            )

        if polygon_geometry is not None:
            for error in polygon_geometry.validateGeometry():
                warnings.append(self.tr("geometry_problem", problem=error.what()))

        project = QgsProject.instance()
        measurements = QgsDistanceArea()
        measurements.setSourceCrs(source_crs, project.transformContext())
        measurements.setEllipsoid(project.ellipsoid() or "WGS84")
        length_metres = measurements.convertLengthMeasurement(
            measurements.measureLength(line_geometry), Qgis.DistanceUnit.Meters
        )

        lines = [
            self.tr("review_points", count=len(rows)),
            self.tr("review_crs", crs=source_crs.authid() or source_crs.description()),
            self.tr("review_line_length", value=self._format_distance(length_metres)),
        ]
        if polygon_geometry is not None:
            perimeter_metres = measurements.convertLengthMeasurement(
                measurements.measurePerimeter(polygon_geometry), Qgis.DistanceUnit.Meters
            )
            area_metres = measurements.convertAreaMeasurement(
                measurements.measureArea(polygon_geometry), Qgis.AreaUnit.SquareMeters
            )
            lines.extend(
                [
                    self.tr("review_perimeter", value=self._format_distance(perimeter_metres)),
                    self.tr("review_area", value=self._format_area(area_metres)),
                ]
            )

        if warnings:
            lines.extend(["", self.tr("review_warnings"), *[f"• {text}" for text in warnings]])
        else:
            lines.extend(["", self.tr("review_valid")])

        message = QMessageBox(self)
        message.setWindowTitle(self.tr("review_title"))
        message.setIcon(
            QMessageBox.Icon.Warning if warnings else QMessageBox.Icon.Information
        )
        message.setText("\n".join(lines))
        create_button = message.addButton(
            self.tr("create_layers"), QMessageBox.ButtonRole.AcceptRole
        )
        message.addButton(self.tr("cancel"), QMessageBox.ButtonRole.RejectRole)
        message.exec()
        return message.clickedButton() is create_button

    def create_geometry(self):
        try:
            rows = self.rows_from_table()
        except ValueError as error:
            QMessageBox.critical(self, self.tr("table_error"), str(error))
            return
        if len(rows) < 2:
            QMessageBox.warning(self, self.tr("not_enough_points"), self.tr("line_minimum"))
            return
        project = QgsProject.instance()
        source_crs = self.crs_widget.crs()
        if not source_crs.isValid():
            QMessageBox.critical(self, self.tr("crs_error"), self.tr("invalid_crs"))
            return
        base_name = self.layer_name_edit.text().strip() or "OCR2Geometry"
        self._save_options()
        vertices = closed_vertices(rows, self.close_check.isChecked())
        line_geometry = QgsGeometry.fromPolylineXY(
            [QgsPointXY(x, y) for x, y in vertices]
        )
        polygon_geometry = None
        if len(rows) >= 3 and (self.close_check.isChecked() or self.polygon_check.isChecked()):
            ring = closed_vertices(rows, True)
            polygon_geometry = QgsGeometry.fromPolygonXY(
                [[QgsPointXY(x, y) for x, y in ring]]
            )
        if not self.review_quality(
            rows, line_geometry, polygon_geometry, source_crs
        ):
            self.status.setText(self.tr("creation_cancelled"))
            return
        if self.points_check.isChecked():
            point_layer = QgsVectorLayer("Point", self.tr("named_points", name=base_name), "memory")
            point_layer.setCrs(source_crs)
            provider = point_layer.dataProvider()
            provider.addAttributes([QgsField("point_no", QVariant.Int), QgsField("latitude", QVariant.Double), QgsField("longitude", QVariant.Double)])
            point_layer.updateFields()
            features = []
            for row in rows:
                feature = QgsFeature(point_layer.fields())
                feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(row.longitude, row.latitude)))
                feature.setAttributes([row.point_id, row.latitude, row.longitude])
                features.append(feature)
            provider.addFeatures(features)
            point_layer.updateExtents()
            if self.labels_check.isChecked():
                from qgis.core import QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling

                settings = QgsPalLayerSettings()
                settings.fieldName = "point_no"
                settings.enabled = True
                text_format = QgsTextFormat()
                text_format.setSize(10)
                settings.setFormat(text_format)
                point_layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
                point_layer.setLabelsEnabled(True)
            project.addMapLayer(point_layer)

        line_layer = QgsVectorLayer("LineString", self.tr("named_line", name=base_name), "memory")
        line_layer.setCrs(source_crs)
        line_feature = QgsFeature()
        line_feature.setGeometry(line_geometry)
        line_layer.dataProvider().addFeature(line_feature)
        line_layer.updateExtents()
        project.addMapLayer(line_layer)

        if self.polygon_check.isChecked():
            if len(rows) < 3:
                QMessageBox.warning(self, self.tr("polygon"), self.tr("polygon_minimum"))
            else:
                polygon_layer = QgsVectorLayer("Polygon", self.tr("named_polygon", name=base_name), "memory")
                polygon_layer.setCrs(source_crs)
                polygon_feature = QgsFeature()
                polygon_feature.setGeometry(polygon_geometry)
                polygon_layer.dataProvider().addFeature(polygon_feature)
                polygon_layer.updateExtents()
                project.addMapLayer(polygon_layer)

        self.iface.mapCanvas().zoomToFullExtent()
        self.status.setText(self.tr("vertices_added", count=len(rows)))
        self.iface.messageBar().pushSuccess(
            self.tr("plugin_name"), self.tr("points_added", count=len(rows))
        )
