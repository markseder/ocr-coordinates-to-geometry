import math
import sys
import time
import unittest

from ocr_coordinates_to_geometry.core import (
    parse_coordinate_lines, row_from_decimal, row_from_values,
    coordinate_quality_issues, coordinate_csv_row,
)
from ocr_coordinates_to_geometry.install_process import run_install


class CoordinateRegressionTests(unittest.TestCase):
    def test_invalid_source_components_are_not_normalized(self):
        for line in ('1 59 99 0 93 0 0', '1 59 0 60 93 0 0',
                     '1 59 -30 0 93 0 0', '1 59 0 -1 93 0 0',
                     '1 90 30 0 180 30 0', '1 59.5 30 0 93 0 0',
                     '1 59 30.5 1 93 0 0'):
            with self.subTest(line=line):
                rows, warnings, _ = parse_coordinate_lines([line], 'dms')
                self.assertFalse(rows)
                self.assertTrue(warnings)

    def test_dm_rejects_invalid_minutes_and_poles(self):
        for line in ('1 59 60 93 0', '1 90 0.1 93 0', '1 59 -1 93 0'):
            rows, warnings, _ = parse_coordinate_lines([line], 'dm')
            self.assertFalse(rows)
            self.assertTrue(warnings)

    def test_full_decimal_bounds_and_nonfinite_values(self):
        for lat, lon in ((90.1, 0), (0, 180.1), (-90.1, 0), (0, -180.1),
                         (math.inf, 0), (0, math.nan)):
            with self.subTest(lat=lat, lon=lon), self.assertRaises(ValueError):
                row_from_decimal(1, lat, lon)
        for value in (math.inf, math.nan, 2147483648):
            with self.assertRaises(ValueError):
                row_from_values([value, 59, 0, 0, 93, 0, 0])

    def test_text_nan_cannot_shift_the_coordinate_columns(self):
        for line in ('1 nan 93', '1 inf 93', '1 -Infinity 93'):
            rows, warnings, _ = parse_coordinate_lines([line])
            self.assertFalse(rows)
            self.assertTrue(warnings)

    def test_exact_bounds_and_negative_fraction_remain_valid(self):
        for lat, lon in ((90, 180), (-90, -180), (-0.5, -0.25)):
            row = row_from_decimal(1, lat, lon)
            self.assertAlmostEqual(lat, row.latitude)
            self.assertAlmostEqual(lon, row.longitude)

    def test_lone_hemisphere_is_applied_to_its_axis(self):
        cases = [('1 12.5 44.25 W', 'lat_lon', 12.5, -44.25),
                 ('1 44.25 W 12.5', 'lon_lat', 12.5, -44.25),
                 ('1 12.5 S 44.25', 'lat_lon', -12.5, 44.25),
                 ('1 44.25 12.5 S', 'lon_lat', -12.5, 44.25)]
        for text, order, lat, lon in cases:
            rows, warnings, _ = parse_coordinate_lines([text], 'dd', order)
            self.assertFalse(warnings)
            self.assertEqual((lat, lon), (rows[0].latitude, rows[0].longitude))

    def test_conflicting_hemispheres_are_rejected(self):
        rows, warnings, _ = parse_coordinate_lines(['1 12.5 N S 44.25 W'], 'dd')
        self.assertFalse(rows)
        self.assertTrue(warnings)

    def test_huge_id_gap_has_bounded_output(self):
        rows = [row_from_decimal(1, 59, 93), row_from_decimal(1000000000, 60, 94)]
        issues = dict(coordinate_quality_issues(rows))
        self.assertEqual(tuple(range(2, 102)), issues['missing_point_ids'])
        self.assertEqual((999999998,), issues['missing_point_ids_truncated'])

    def test_precision_does_not_change_csv_decimal_coordinates(self):
        row = row_from_decimal(1, 59.12345678, -0.12345678)
        self.assertEqual(coordinate_csv_row(row, seconds_precision=0)[7:9],
                         coordinate_csv_row(row, seconds_precision=6)[7:9])


class InstallerRegressionTests(unittest.TestCase):
    def test_silent_process_can_be_cancelled_and_reaped(self):
        started = time.monotonic()
        heartbeats = []
        ok, log = run_install(
            [sys.executable, '-c', 'import time; time.sleep(30)'],
            progress_callback=heartbeats.append,
            cancelled_callback=lambda: time.monotonic() - started > 0.2,
        )
        self.assertFalse(ok)
        self.assertIn('cancelled', log)
        self.assertLess(time.monotonic() - started, 5)
        self.assertGreaterEqual(len(heartbeats), 2)

    def test_output_is_drained_and_exit_failure_reported(self):
        ok, log = run_install([sys.executable, '-c', "print('diagnostic'); raise SystemExit(7)"])
        self.assertFalse(ok)
        self.assertIn('diagnostic', log)

    def test_timeout_stops_silent_process(self):
        started = time.monotonic()
        ok, log = run_install([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.2)
        self.assertFalse(ok)
        self.assertIn('timed out', log)
        self.assertLess(time.monotonic() - started, 5)

    def test_callback_failure_does_not_leave_process_running(self):
        def fail(_):
            raise RuntimeError('callback failed')
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, 'callback failed'):
            run_install([sys.executable, '-c', 'import time; time.sleep(30)'], fail)
        self.assertLess(time.monotonic() - started, 5)


if __name__ == '__main__':
    unittest.main()
