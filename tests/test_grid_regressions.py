import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import cv2
    import numpy as np
except ImportError:
    AVAILABLE = False
else:
    AVAILABLE = True

from ocr_coordinates_to_geometry.ocr import recognize_lines, _recognize_grid_cells, is_table_header, OcrLine


@unittest.skipUnless(AVAILABLE, 'Install OpenCV and NumPy for grid-image regression tests')
class GridRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'table.png'
        image = np.full((135, 575), 255, dtype=np.uint8)
        for x in range(5, 566, 80):
            cv2.line(image, (x, 5), (x, 125), 0, 1)
        for y in (5, 45, 85, 125):
            cv2.line(image, (5, y), (565, y), 0, 1)
        cv2.imwrite(str(self.path), image)

    def test_real_grid_extraction_preserves_empty_last_cell(self):
        expected = ['1','59','0','0','93','0','0',
                    '2','60','0','0','94','0','0',
                    '3','61','0','0','95','0','']
        values = iter(expected)
        def engine(image, **kwargs):
            self.assertIsInstance(image, np.ndarray)
            text = next(values)
            return types.SimpleNamespace(txts=[text] if text else [], scores=[.99] if text else [])
        with patch('ocr_coordinates_to_geometry.ocr._load_engine', return_value=engine):
            lines = recognize_lines(self.path)
        self.assertEqual(3, len(lines))
        self.assertEqual(tuple(expected[-7:]), lines[-1].cells)

    def test_completely_unreadable_grid_rows_remain_visible(self):
        def engine(image, **kwargs):
            return types.SimpleNamespace(txts=None, scores=None)
        lines = _recognize_grid_cells(engine, self.path)
        self.assertEqual(3, len(lines))
        self.assertTrue(all(len(line.cells) == 7 for line in lines))
        self.assertTrue(all(not any(line.cells) for line in lines))

    def test_legacy_cell_result_uses_full_image_fallback(self):
        self.assertEqual([], _recognize_grid_cells(lambda *a, **k: ([], None), self.path))

    def test_header_detection_does_not_hide_numbered_data(self):
        self.assertTrue(is_table_header(OcrLine('Point Latitude Longitude')))
        self.assertFalse(is_table_header(OcrLine('3 60 latitude missing')))
        self.assertFalse(is_table_header(OcrLine('', cells=('',)*7)))
