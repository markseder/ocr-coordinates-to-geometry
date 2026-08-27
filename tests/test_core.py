import unittest

from ocr_coordinates_to_geometry.core import (
    closed_vertices,
    coordinate_quality_issues,
    coordinate_csv_row,
    CSV_HEADERS,
    clipboard_column_layout,
    is_header_row,
    split_clipboard_table,
    decimal_to_dms,
    dms_to_decimal,
    format_number,
    rounded_dms_parts,
    numbers_from_text,
    parse_lines,
    parse_coordinate_lines,
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

    def test_decimal_degrees_are_detected(self):
        rows, warnings, detected = parse_coordinate_lines(["1 59.770833 93.450000"])
        self.assertEqual([], warnings)
        self.assertEqual("dd", detected)
        self.assertAlmostEqual(59.770833, rows[0].latitude, places=6)

    def test_degrees_decimal_minutes(self):
        rows, warnings, detected = parse_coordinate_lines(["1 59 46.25 93 27.5"], "dm")
        self.assertEqual([], warnings)
        self.assertEqual("dm", detected)
        self.assertAlmostEqual(59.770833333, rows[0].latitude)
        self.assertAlmostEqual(93.458333333, rows[0].longitude)

    def test_reverse_axis_order(self):
        rows, warnings, _ = parse_coordinate_lines(["1 93.45 59.770833"], "dd", "lon_lat")
        self.assertEqual([], warnings)
        self.assertAlmostEqual(59.770833, rows[0].latitude, places=6)
        self.assertAlmostEqual(93.45, rows[0].longitude)

    def test_hemisphere_suffixes(self):
        rows, warnings, _ = parse_coordinate_lines(["1 12.5 S 44.25 W"], "dd")
        self.assertEqual([], warnings)
        self.assertAlmostEqual(-12.5, rows[0].latitude)
        self.assertAlmostEqual(-44.25, rows[0].longitude)

    def test_missing_point_ids_are_generated(self):
        rows, warnings, _ = parse_coordinate_lines(["59.1 93.1", "59.2 93.2"], "dd")
        self.assertEqual([], warnings)
        self.assertEqual([1, 2], [row.point_id for row in rows])

    def test_preserve_source_order(self):
        rows, warnings, _ = parse_coordinate_lines(
            ["2 59.2 93.2", "1 59.1 93.1"], "dd", sort_by_point=False
        )
        self.assertEqual([], warnings)
        self.assertEqual([2, 1], [row.point_id for row in rows])

    def test_decimal_to_dms_round_trip(self):
        dms = decimal_to_dms(-59.770833333)
        self.assertAlmostEqual(-59.770833333, dms_to_decimal(*dms))

    def test_negative_fractional_degree_round_trip(self):
        dms = decimal_to_dms(-0.5)
        self.assertEqual("-0", format_number(dms[0]))
        self.assertAlmostEqual(-0.5, dms_to_decimal(*dms))

    def test_missing_point_numbers_are_reported(self):
        rows = [
            row_from_values([1, 59, 1, 0, 93, 1, 0]),
            row_from_values([3, 59, 2, 0, 93, 2, 0]),
        ]
        self.assertIn(("missing_point_ids", (2,)), coordinate_quality_issues(rows))

    def test_coincident_adjacent_vertices_are_reported(self):
        rows = [
            row_from_values([1, 59, 1, 0, 93, 1, 0]),
            row_from_values([2, 59, 1, 0, 93, 1, 0]),
        ]
        self.assertIn(("coincident_vertices", (1, 2)), coordinate_quality_issues(rows))

    def test_explicit_closing_vertex_is_reported(self):
        rows = [
            row_from_values([1, 59, 1, 0, 93, 1, 0]),
            row_from_values([2, 59, 2, 0, 93, 2, 0]),
            row_from_values([3, 59, 1, 0, 93, 1, 0]),
        ]
        self.assertIn(("repeated_closing_vertex", (1, 3)), coordinate_quality_issues(rows))

    def test_csv_row_contains_decimal_coordinates_and_confidence(self):
        row = row_from_values([1, 59, 46, 15, 93, 27, 0])
        record = coordinate_csv_row(row, (0.99, 0.87, 0.95))
        self.assertEqual(len(CSV_HEADERS), len(record))
        self.assertEqual("59.77083333", record[7])
        self.assertEqual("93.45000000", record[8])
        self.assertEqual("87.0", record[9])

    def test_csv_row_leaves_manual_confidence_empty(self):
        row = row_from_values([1, 59, 46, 15, 93, 27, 0])
        self.assertEqual("", coordinate_csv_row(row)[9])

    def test_excel_clipboard_table_is_split_by_tabs(self):
        rows = split_clipboard_table("1\t59\t45\t0\t93\t30\t0\n2\t60\t0\t0\t94\t0\t0")
        self.assertEqual(2, len(rows))
        self.assertEqual("93", rows[0][4])

    def test_semicolon_csv_with_decimal_commas_is_preserved(self):
        rows = split_clipboard_table("point_id;latitude_dd;longitude_dd\n1;59,75;93,5")
        self.assertTrue(is_header_row(rows[0]))
        self.assertEqual(["1", "59,75", "93,5"], rows[1])

    def test_eight_columns_without_point_id_skip_point_column(self):
        columns, auto_number, prefer_dd = clipboard_column_layout(8)
        self.assertEqual(list(range(1, 9)), columns)
        self.assertTrue(auto_number)
        self.assertFalse(prefer_dd)

    def test_six_dms_columns_without_point_id_skip_point_column(self):
        columns, auto_number, _ = clipboard_column_layout(6)
        self.assertEqual(list(range(1, 7)), columns)
        self.assertTrue(auto_number)

    def test_small_seconds_are_not_scientific_notation(self):
        self.assertEqual("0", format_number(0.000012, 3))

    def test_seconds_are_rounded_to_selected_precision(self):
        self.assertEqual("12.346", format_number(12.34567, 3))

    def test_seconds_rounding_carries_into_minutes_and_degrees(self):
        self.assertEqual((60.0, 0.0, 0.0), rounded_dms_parts(59, 59, 59.999988, 3))


if __name__ == "__main__":
    unittest.main()
