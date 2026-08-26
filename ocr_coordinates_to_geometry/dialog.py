"""Qt dialog for OCR preview and geometry creation."""

from __future__ import annotations

import os
import tempfile
import time

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
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
    QApplication,
    QVBoxLayout,
)
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from .core import CoordinateRow, closed_vertices, row_from_values
from .ocr import OcrUnavailableError, recognize_lines


HEADERS = ["№", "Широта °", "′", "″", "Долгота °", "′", "″"]


class OcrCoordinatesDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.image_path = ""
        self.temp_image_path = ""
        self.setWindowTitle("OCR координат → геометрия")
        self.resize(820, 620)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        buttons = QHBoxLayout()
        self.open_button = QPushButton("Открыть изображение…")
        self.paste_button = QPushButton("Вставить из буфера")
        self.recognize_button = QPushButton("Распознать")
        self.install_ocr_button = QPushButton("Установить OCR")
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.paste_button)
        buttons.addStretch(1)
        buttons.addWidget(self.install_ocr_button)
        buttons.addWidget(self.recognize_button)
        root.addLayout(buttons)

        self.preview = QLabel("Откройте изображение или вставьте скриншот из буфера")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(150)
        self.preview.setStyleSheet("QLabel { border: 1px solid #999; background: #f4f4f4; }")
        root.addWidget(self.preview)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.table, 1)

        table_buttons = QHBoxLayout()
        self.add_row_button = QPushButton("Добавить строку")
        self.delete_row_button = QPushButton("Удалить выбранные строки")
        table_buttons.addWidget(self.add_row_button)
        table_buttons.addWidget(self.delete_row_button)
        table_buttons.addStretch(1)
        root.addLayout(table_buttons)

        options = QGroupBox("Результат (EPSG:4326 — WGS 84)")
        option_grid = QGridLayout(options)
        self.points_check = QCheckBox("Создать угловые точки")
        self.points_check.setChecked(True)
        self.labels_check = QCheckBox("Подписать номера точек")
        self.labels_check.setChecked(True)
        self.close_check = QCheckBox("Замкнуть линию (повторить первую точку в конце)")
        self.close_check.setChecked(True)
        self.polygon_check = QCheckBox("Дополнительно создать полигон")
        option_grid.addWidget(self.points_check, 0, 0)
        option_grid.addWidget(self.labels_check, 0, 1)
        option_grid.addWidget(self.close_check, 1, 0, 1, 2)
        option_grid.addWidget(self.polygon_check, 2, 0, 1, 2)
        root.addWidget(options)

        bottom = QHBoxLayout()
        self.status = QLabel("Готово к работе")
        self.create_button = QPushButton("Добавить в проект QGIS")
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.create_button)
        root.addLayout(bottom)

        self.open_button.clicked.connect(self.open_image)
        self.paste_button.clicked.connect(self.paste_image)
        self.recognize_button.clicked.connect(self.recognize)
        self.install_ocr_button.clicked.connect(self.install_ocr)
        self.add_row_button.clicked.connect(self.add_empty_row)
        self.delete_row_button.clicked.connect(self.delete_selected_rows)
        self.create_button.clicked.connect(self.create_geometry)

    def add_empty_row(self):
        row_index = self.table.rowCount()
        self.table.insertRow(row_index)
        next_point = row_index + 1
        self.table.setItem(row_index, 0, QTableWidgetItem(str(next_point)))
        for column in range(1, 7):
            self.table.setItem(row_index, column, QTableWidgetItem("0"))
        self.table.setCurrentCell(row_index, 1)

    def delete_selected_rows(self):
        selected = {index.row() for index in self.table.selectedIndexes()}
        for row_index in sorted(selected, reverse=True):
            self.table.removeRow(row_index)

    def open_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите таблицу координат", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)")
        if path:
            self.set_image(path)

    def paste_image(self):
        from qgis.PyQt.QtWidgets import QApplication

        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.warning(self, "Буфер обмена", "В буфере обмена нет изображения.")
            return
        path = os.path.join(tempfile.gettempdir(), "qgis_ocr_coordinates_clipboard.png")
        if not image.save(path, "PNG"):
            QMessageBox.critical(self, "Ошибка", "Не удалось сохранить изображение из буфера.")
            return
        self.temp_image_path = path
        self.set_image(path)

    def set_image(self, path):
        self.image_path = path
        pixmap = QPixmap(path)
        self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.status.setText(os.path.basename(path))

    def recognize(self):
        if not self.image_path:
            QMessageBox.warning(self, "Нет изображения", "Сначала откройте или вставьте изображение.")
            return
        self.status.setText("Распознавание…")
        from .dependencies import rapidocr_available

        if not rapidocr_available():
            answer = QMessageBox.question(
                self,
                "Установка RapidOCR",
                "Для распознавания нужно один раз установить RapidOCR (около 100–200 МБ).\n\n"
                "Он будет установлен автоматически в профиль QGIS без прав администратора. Продолжить?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer != QMessageBox.StandardButton.Yes or not self.install_ocr():
                self.status.setText("RapidOCR не установлен")
                return
        try:
            lines = recognize_lines(self.image_path)
        except OcrUnavailableError as error:
            QMessageBox.critical(self, "RapidOCR не установлен", str(error))
            self.status.setText("Нужна установка RapidOCR")
            return
        from .core import parse_lines

        rows, warnings = parse_lines(lines)
        self.fill_table(rows)
        self.status.setText(f"Распознано точек: {len(rows)}")
        if warnings:
            QMessageBox.warning(self, "Проверьте распознавание", "\n".join(warnings[:12]))

    def install_ocr(self):
        from .dependencies import install_rapidocr, rapidocr_available, vendor_directory

        if rapidocr_available():
            self.status.setText("RapidOCR уже установлен")
            return True
        progress = QProgressDialog("Подготовка установки…", "Отмена", 0, 0, self)
        progress.setWindowTitle("Установка RapidOCR")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        last_update = [0.0]

        def update_progress(line):
            now = time.monotonic()
            if now - last_update[0] > 0.1:
                progress.setLabelText(line[:160] or "Загрузка компонентов OCR…")
                QApplication.processEvents()
                last_update[0] = now

        ok, log = install_rapidocr(update_progress, progress.wasCanceled)
        progress.close()
        if ok:
            self.status.setText("RapidOCR установлен — можно распознавать")
            QMessageBox.information(
                self,
                "RapidOCR готов",
                "Компоненты OCR установлены. Повторно устанавливать их при следующем запуске не нужно.",
            )
            return True
        tail = "\n".join(log.splitlines()[-12:])
        QMessageBox.critical(
            self,
            "Не удалось установить RapidOCR",
            f"Проверьте интернет и повторите установку.\n\nПапка: {vendor_directory()}\n\n{tail}",
        )
        self.status.setText("Ошибка установки RapidOCR")
        return False

    def fill_table(self, rows):
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column, text in enumerate(row.as_cells()):
                self.table.setItem(row_index, column, QTableWidgetItem(text))

    def rows_from_table(self) -> list[CoordinateRow]:
        rows = []
        for row_index in range(self.table.rowCount()):
            values = []
            for column in range(7):
                item = self.table.item(row_index, column)
                if item is None or not item.text().strip():
                    raise ValueError(f"Строка {row_index + 1}: пустая ячейка")
                values.append(float(item.text().strip().replace(",", ".")))
            rows.append(row_from_values(values))
        rows.sort(key=lambda row: row.point_id)
        point_ids = [row.point_id for row in rows]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError("Номера точек не должны повторяться")
        return rows

    def create_geometry(self):
        try:
            rows = self.rows_from_table()
        except ValueError as error:
            QMessageBox.critical(self, "Ошибка в таблице", str(error))
            return
        if len(rows) < 2:
            QMessageBox.warning(self, "Недостаточно точек", "Для линии нужны минимум две точки.")
            return
        project = QgsProject.instance()
        if self.points_check.isChecked():
            point_layer = QgsVectorLayer("Point?crs=EPSG:4326", "OCR — угловые точки", "memory")
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

        vertices = closed_vertices(rows, self.close_check.isChecked())
        line_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "OCR — линия", "memory")
        line_feature = QgsFeature()
        line_feature.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in vertices]))
        line_layer.dataProvider().addFeature(line_feature)
        line_layer.updateExtents()
        project.addMapLayer(line_layer)

        if self.polygon_check.isChecked():
            if len(rows) < 3:
                QMessageBox.warning(self, "Полигон", "Для полигона нужны минимум три точки. Точки и линия уже созданы.")
            else:
                ring = closed_vertices(rows, True)
                polygon_layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "OCR — полигон", "memory")
                polygon_feature = QgsFeature()
                polygon_feature.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in ring]]))
                polygon_layer.dataProvider().addFeature(polygon_feature)
                polygon_layer.updateExtents()
                project.addMapLayer(polygon_layer)

        self.iface.mapCanvas().zoomToFullExtent()
        self.status.setText(f"Добавлено вершин: {len(rows)}")
        self.iface.messageBar().pushSuccess("OCR координат", f"Добавлено точек: {len(rows)}")
