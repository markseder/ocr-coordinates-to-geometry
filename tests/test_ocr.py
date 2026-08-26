import unittest

from ocr_coordinates_to_geometry.ocr import OcrLine, _items_from_result


class Result:
    boxes = [[[0, 0], [1, 0], [1, 1], [0, 1]]]
    txts = ["42"]
    scores = [0.87]


class ResultWithoutScores:
    boxes = [[[0, 0], [1, 0], [1, 1], [0, 1]]]
    txts = ["42"]


class OcrTests(unittest.TestCase):
    def test_new_rapidocr_result_preserves_confidence(self):
        self.assertEqual(0.87, _items_from_result(Result())[0][2])

    def test_missing_scores_are_supported(self):
        self.assertIsNone(_items_from_result(ResultWithoutScores())[0][2])

    def test_ocr_line_holds_cell_confidences(self):
        line = OcrLine("1 59 00", (0.99, 0.82, 0.71))
        self.assertEqual((0.99, 0.82, 0.71), line.confidences)


if __name__ == "__main__":
    unittest.main()
