import unittest

from ocr_coordinates_to_geometry.core import (
    closed_vertices,
    dms_to_decimal,
    numbers_from_text,
    parse_lines,
    row_from_values,
)


class CoreTests(unittest.TestCase):
    def test_example_image_rows(self):
        lines = [
            "1 59 46 15 93 27 00",
            "2 59 46 15 93 28 50",
            "3 59 45 15 93 28 50",
            "4 59 45 15 93 27 00",
        ]
        rows, warnings = parse_lines(lines)
        self.assertEqual([], warnings)
        self.assertEqual(4, len(rows))
        self.assertAlmostEqual(59.7708333333, rows[0].latitude)
        self.assertAlmostEqual(93.45, rows[0].longitude)

    def test_close_repeats_first_vertex(self):
        rows = [row_from_values([1, 59, 46, 15, 93, 27, 0]), row_from_values([2, 59, 46, 15, 93, 28, 50])]
        vertices = closed_vertices(rows, True)
        self.assertEqual(vertices[0], vertices[-1])
        self.assertEqual(3, len(vertices))

    def test_open_line_does_not_repeat_first_vertex(self):
        rows = [row_from_values([1, 59, 46, 15, 93, 27, 0]), row_from_values([2, 59, 46, 15, 93, 28, 50])]
        vertices = closed_vertices(rows, False)
        self.assertEqual(2, len(vertices))

    def test_common_ocr_substitutions(self):
        self.assertEqual([1.0, 59.0, 46.0, 15.0, 93.0, 27.0, 0.0], numbers_from_text("I 59 46 15 93 27 OO"))

    def test_invalid_seconds(self):
        with self.assertRaisesRegex(ValueError, "Seconds"):
            row_from_values([1, 59, 46, 60, 93, 27, 0])

    def test_negative_dms(self):
        self.assertAlmostEqual(-10.5, dms_to_decimal(-10, 30, 0))

    def test_rows_are_sorted_by_point_number(self):
        rows, warnings = parse_lines(["2 59 46 15 93 28 50", "1 59 46 15 93 27 00"])
        self.assertEqual([], warnings)
        self.assertEqual([1, 2], [row.point_id for row in rows])

    def test_duplicate_point_numbers_are_reported(self):
        rows, warnings = parse_lines(["1 59 46 15 93 28 50", "1 59 46 15 93 27 00"])
        self.assertEqual(2, len(rows))
        self.assertIn("Duplicate point numbers: 1", warnings)


if __name__ == "__main__":
    unittest.main()
