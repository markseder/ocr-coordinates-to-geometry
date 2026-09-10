import threading
import time
import types
import unittest
from unittest.mock import patch

from qt_support import AVAILABLE

if AVAILABLE:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QDialog, QTableWidget, QComboBox, QSpinBox, QLabel, QLineEdit
    from ocr_coordinates_to_geometry.manual_entry import ManualCoordinateDialog
    from ocr_coordinates_to_geometry.dialog import OcrCoordinatesDialog
    from ocr_coordinates_to_geometry.table_values import cell_value, ExactValueDelegate
    from ocr_coordinates_to_geometry.core import row_from_decimal
    from ocr_coordinates_to_geometry.ocr import OcrLine
    from ocr_coordinates_to_geometry.background import run_background
    from qt_support import APP

    class MainHarness(OcrCoordinatesDialog):
        def __init__(self):
            QDialog.__init__(self)
            self.locale = 'en'
            self.table = QTableWidget(0, 9, self)
            self.table.setItemDelegate(ExactValueDelegate(self.table))
            self.row_confidences = []
            self.seconds_precision_spin = QSpinBox()
            self.seconds_precision_spin.setValue(3)
            self.order_combo = QComboBox()
            self.order_combo.addItem('source', False)
            self.format_combo = QComboBox()
            self.format_combo.addItem('auto', 'auto')
            self.axis_combo = QComboBox()
            self.axis_combo.addItem('lat_lon', 'lat_lon')
            self.axis_combo.addItem('lon_lat', 'lon_lat')
            self.status = QLabel()
            self.table.cellChanged.connect(self.update_decimal_preview)

        def closeEvent(self, event):
            QDialog.closeEvent(self, event)


@unittest.skipUnless(AVAILABLE, 'Install PyQt6 to exercise the real table widgets')
class QtRegressionTests(unittest.TestCase):
    def setUp(self):
        self.dialogs = []

    def tearDown(self):
        for dialog in self.dialogs:
            dialog.deleteLater()
        APP.processEvents()

    def manual(self, precision=3):
        d = ManualCoordinateDialog('en', [row_from_decimal(1, 59.12345678, 93.98765432)], precision)
        self.dialogs.append(d)
        return d

    def main(self):
        d = MainHarness()
        self.dialogs.append(d)
        return d

    def test_invalid_dd_cannot_accept_old_dms(self):
        for value in ('oops', '91', '', 'inf', 'nan'):
            with self.subTest(value=value):
                d = self.manual()
                d.table.item(0, 7).setText(value)
                with self.assertRaises(ValueError):
                    d.coordinate_rows()
                self.assertEqual('', d.table.item(0, 1).text())

    def test_editing_other_axis_does_not_erase_invalid_dd(self):
        d = self.manual()
        d.table.item(0, 7).setText('oops')
        d.table.item(0, 8).setText('94.5')
        self.assertEqual('oops', d.table.item(0, 7).text())
        with self.assertRaises(ValueError):
            d.coordinate_rows()
        d.table.item(0, 7).setText('60.5')
        row = d.coordinate_rows()[0]
        self.assertEqual((60.5, 94.5), (row.latitude, row.longitude))

    def test_invalid_dms_cannot_accept_old_dd(self):
        d = self.manual()
        d.table.item(0, 2).setText('99')
        self.assertEqual('', d.table.item(0, 7).text())
        with self.assertRaises(ValueError):
            d.coordinate_rows()

    def test_rounding_does_not_change_manual_or_main_values(self):
        for precision in (0, 3, 6):
            d = self.manual(precision)
            d.table.item(0, 7).setText('59.12345678')
            row = d.coordinate_rows()[0]
            self.assertAlmostEqual(59.12345678, row.latitude, places=10)
            main = self.main()
            main.seconds_precision_spin.setValue(precision)
            main.fill_table([row])
            self.assertAlmostEqual(row.latitude, main.rows_from_table()[0].latitude, places=10)
            main.seconds_precision_spin.setValue(0)
            main.refresh_seconds_precision()
            main.seconds_precision_spin.setValue(6)
            main.refresh_seconds_precision()
            self.assertAlmostEqual(row.latitude, main.rows_from_table()[0].latitude, places=10)

    def test_editing_point_id_preserves_exact_coordinates_and_clears_confidence(self):
        d = self.main()
        d.seconds_precision_spin.setValue(0)
        row = row_from_decimal(1, 59.12345678, 93.98765432)
        d.fill_table([row], [(0.5,)*7])
        d.table.item(0, 0).setText('2')
        actual = d.rows_from_table()[0]
        self.assertEqual(2, actual.point_id)
        self.assertAlmostEqual(row.latitude, actual.latitude, places=10)
        self.assertAlmostEqual(row.longitude, actual.longitude, places=10)
        self.assertEqual([()], d.row_confidences)

    def test_nonnumeric_grid_cell_is_not_reinterpreted_as_missing_id(self):
        d = self.main()
        cells = ('1','59','bad','0','93','0','0')
        with patch('ocr_coordinates_to_geometry.dialog.QMessageBox.warning'):
            d.process_coordinate_lines([OcrLine(' '.join(cells), cells=cells)])
        self.assertEqual('bad', d.table.item(0, 2).text())
        with self.assertRaises(ValueError):
            d.rows_from_table()

    def test_editor_opens_exact_value(self):
        d = self.manual(0)
        item = d.table.item(0, 3)
        editor = QLineEdit()
        d.table.itemDelegate().setEditorData(editor, d.table.model().index(0, 3))
        self.assertAlmostEqual(cell_value(item), float(editor.text()), places=10)

    def test_paste_incomplete_replacement_does_not_reuse_old_row(self):
        d = self.manual()
        d.table.setCurrentCell(0, 0)
        APP.clipboard().setText('1\t60.5\t')
        d.paste_from_clipboard()
        with self.assertRaises(ValueError):
            d.coordinate_rows()

    def test_main_invalid_edit_clears_decimal_preview(self):
        d = self.main()
        d.fill_table([row_from_decimal(1, 59.5, 93)])
        d.table.item(0, 2).setText('99')
        self.assertEqual('', d.table.item(0, 7).text())
        with self.assertRaises(ValueError):
            d.rows_from_table()

    def test_missing_final_ocr_row_blocks_geometry_until_repaired(self):
        d = self.main()
        lines = [OcrLine('Point Latitude Longitude'),
                 OcrLine('1\t59\t0\t0\t93\t0\t0', cells=('1','59','0','0','93','0','0')),
                 OcrLine('2\t60\t\t0\t94\t0\t0', cells=('2','60','','0','94','0','0'))]
        with patch('ocr_coordinates_to_geometry.dialog.QMessageBox.warning'):
            d.process_coordinate_lines(lines)
        self.assertEqual(2, d.table.rowCount())
        self.assertEqual('60', d.table.item(1, 1).text())
        self.assertIn('Original OCR', d.table.item(1, 2).toolTip())
        with self.assertRaises(ValueError):
            d.rows_from_table()
        d.table.item(1, 2).setText('30')
        self.assertEqual(60.5, d.rows_from_table()[1].latitude)

    def test_blank_and_bad_dd_ocr_rows_are_preserved(self):
        d = self.main()
        lines = [OcrLine('1 59 93'), OcrLine('', cells=('','','')),
                 OcrLine('3 91 93', cells=('3','91','93'))]
        with patch('ocr_coordinates_to_geometry.dialog.QMessageBox.warning'):
            d.process_coordinate_lines(lines)
        self.assertEqual(3, d.table.rowCount())
        with self.assertRaises(ValueError):
            d.rows_from_table()

    def test_generated_ids_survive_per_line_parsing(self):
        d = self.main()
        d.process_coordinate_lines([OcrLine('59 93'), OcrLine('60 94')])
        self.assertEqual([1, 2], [row.point_id for row in d.rows_from_table()])

    def test_projected_crs_is_blocked_before_geometry_creation(self):
        d = self.main()
        d.fill_table([row_from_decimal(1,59,93),row_from_decimal(2,60,94)])
        crs = types.SimpleNamespace(isValid=lambda: True, isGeographic=lambda: False)
        d.crs_widget = types.SimpleNamespace(crs=lambda: crs)
        with patch('ocr_coordinates_to_geometry.dialog.QMessageBox.critical') as error:
            d.create_geometry()
        self.assertIn('geographic CRS', error.call_args.args[2])

    def test_background_work_does_not_block_qt_events(self):
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        timer.start(10)
        main_thread = threading.get_ident()
        def work():
            time.sleep(0.15)
            return threading.get_ident()
        try:
            worker_thread = run_background(work, 'Test OCR', None)
        finally:
            timer.stop()
        self.assertNotEqual(main_thread, worker_thread)
        self.assertGreaterEqual(len(ticks), 2)

    def test_background_errors_reach_caller(self):
        def work():
            raise ValueError('bad image')
        with self.assertRaisesRegex(ValueError, 'bad image'):
            run_background(work, 'Test OCR', None)
