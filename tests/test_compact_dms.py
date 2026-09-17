import unittest
from ocr_coordinates_to_geometry.core import prepare_grid_coordinates, parse_coordinate_lines

SAMPLE = [
    ('1', '61°47\'00"', '149°39\'07"'),
    ('2', '61°45\'29"', '149°43\'00"'),
    ('3', '61°44\'19"', '149°45\'00"'),
    ('4', '61°43\'32"', '149°42\'50"'),
    ('5', '61°45\'52"', '149°36\'37"'),
]

class CompactTests(unittest.TestCase):
    def test_five_survey_points_auto_and_dms(self):
        expected = [(61,47,0,149,39,7),(61,45,29,149,43,0),
                    (61,44,19,149,45,0),(61,43,32,149,42,50),(61,45,52,149,36,37)]
        for mode in ('auto', 'dms'):
            for cells, values in zip(SAMPLE, expected):
                text, repaired = prepare_grid_coordinates(cells)
                rows, warnings, detected = parse_coordinate_lines([text], mode)
                self.assertFalse(repaired)
                self.assertFalse(warnings)
                self.assertEqual('dms', detected)
                self.assertEqual(int(cells[0]), rows[0].point_id)
                self.assertAlmostEqual(values[0]+values[1]/60+values[2]/3600, rows[0].latitude)
                self.assertAlmostEqual(values[3]+values[4]/60+values[5]/3600, rows[0].longitude)

    def test_lost_degree_sign_and_unicode_quotes(self):
        text, repaired = prepare_grid_coordinates(('2', '6145′29″', '14943’00”'))
        rows, warnings, _ = parse_coordinate_lines([text])
        self.assertTrue(repaired)
        self.assertFalse(warnings)
        self.assertAlmostEqual(61+45/60+29/3600, rows[0].latitude)
        self.assertAlmostEqual(149+43/60, rows[0].longitude)

    def test_space_separator_missing_final_quote_reversed_axes(self):
        text, _ = prepare_grid_coordinates(('149°45\'00"', "61 44'19"))
        rows, warnings, _ = parse_coordinate_lines([text], 'auto', 'lon_lat')
        self.assertFalse(warnings)
        self.assertAlmostEqual(61+44/60+19/3600, rows[0].latitude)

    def test_decimal_seconds_and_hemispheres(self):
        text, _ = prepare_grid_coordinates(('1','0°30′00,125″S','149º39′07.25″W'))
        rows, warnings, _ = parse_coordinate_lines([text])
        self.assertFalse(warnings)
        self.assertLess(rows[0].latitude, 0)
        self.assertLess(rows[0].longitude, 0)

    def test_reject_damaged_cells_and_mixed_components(self):
        for cells in [('1','','149°39\'07"'),('1','bad61','149'),
                      ('1','61°47\'00"','149°39\''),('1','61','bad','00','149','39','07')]:
            with self.subTest(cells=cells), self.assertRaises(ValueError):
                prepare_grid_coordinates(cells)

    def test_invalid_angles_and_bare_merged_digits_remain_invalid(self):
        for cells in [('1',"6160'00", "14943'00"), ('1','614700','1493907'),
                      ('1',"91°00'00", "149°00'00")]:
            text, _ = prepare_grid_coordinates(cells)
            rows, warnings, _ = parse_coordinate_lines([text])
            self.assertFalse(rows)
            self.assertTrue(warnings)

    def test_plain_dd_and_seven_columns_unchanged(self):
        for cells in [('1','61.5','149.5'),('1','61','30','0','149','30','0')]:
            text, repaired = prepare_grid_coordinates(cells)
            rows, warnings, _ = parse_coordinate_lines([text])
            self.assertFalse(repaired)
            self.assertFalse(warnings)
            self.assertEqual(61.5, rows[0].latitude)
