"""Dependency-free coordinate parsing and validation."""

from __future__ import annotations

from dataclasses import dataclass
import csv
from io import StringIO
import math
import re
from typing import Iterable, Sequence


NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
HEMISPHERE_RE = re.compile(r"(?<![A-Z])[NSEW](?![A-Z])", re.IGNORECASE)
FORMATS = ("auto", "dms", "dm", "dd")


def split_clipboard_table(text: str) -> list[list[str]]:
    """Parse table text copied from Excel, CSV or a whitespace table."""
    lines = [
        line
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    if not lines:
        return []
    if "\t" in text:
        rows = [line.split("\t") for line in lines]
    elif ";" in text:
        rows = list(csv.reader(StringIO("\n".join(lines)), delimiter=";"))
    else:
        rows = [line.split() for line in lines]
    return [[cell.strip() for cell in row] for row in rows]


def is_header_row(row: Sequence[str]) -> bool:
    if not row:
        return False
    try:
        float(row[0].replace(",", "."))
        return False
    except ValueError:
        return True


@dataclass(frozen=True)
class CoordinateRow:
    point_id: int
    lat_deg: float
    lat_min: float
    lat_sec: float
    lon_deg: float
    lon_min: float
    lon_sec: float

    @property
    def latitude(self) -> float:
        return dms_to_decimal(self.lat_deg, self.lat_min, self.lat_sec)

    @property
    def longitude(self) -> float:
        return dms_to_decimal(self.lon_deg, self.lon_min, self.lon_sec)

    def as_cells(self) -> list[str]:
        return [
            str(self.point_id),
            format_number(self.lat_deg),
            format_number(self.lat_min),
            format_number(self.lat_sec),
            format_number(self.lon_deg),
            format_number(self.lon_min),
            format_number(self.lon_sec),
        ]


def format_number(value: float) -> str:
    if value == 0 and math.copysign(1.0, value) < 0:
        return "-0"
    return str(int(value)) if value.is_integer() else str(value)


def dms_to_decimal(degrees: float, minutes: float, seconds: float) -> float:
    sign = -1.0 if math.copysign(1.0, degrees) < 0 else 1.0
    return sign * (abs(degrees) + minutes / 60.0 + seconds / 3600.0)


def decimal_to_dms(value: float) -> tuple[float, float, float]:
    sign = -1.0 if value < 0 else 1.0
    absolute = abs(value)
    degrees = int(absolute)
    minute_value = (absolute - degrees) * 60.0
    minutes = int(minute_value)
    seconds = round((minute_value - minutes) * 60.0, 8)
    if seconds >= 60:
        seconds = 0.0
        minutes += 1
    if minutes >= 60:
        minutes = 0
        degrees += 1
    return sign * float(degrees), float(minutes), seconds


def normalize_ocr_text(text: str) -> str:
    """Correct common OCR substitutions only in a numeric-table context."""
    translation = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})
    return text.translate(translation).replace(";", " ")


def numbers_from_text(text: str) -> list[float]:
    clean = normalize_ocr_text(text)
    return [float(token.replace(",", ".")) for token in NUMBER_RE.findall(clean)]


def row_from_values(values: Sequence[float]) -> CoordinateRow:
    if len(values) != 7:
        raise ValueError(f"Expected 7 numeric values, got {len(values)}")
    point = int(values[0])
    if values[0] != point or point < 1:
        raise ValueError("Point number must be a positive integer")
    row = CoordinateRow(point, *map(float, values[1:]))
    validate_row(row)
    return row


def row_from_decimal(point_id: int, latitude: float, longitude: float) -> CoordinateRow:
    lat = decimal_to_dms(latitude)
    lon = decimal_to_dms(longitude)
    return row_from_values([point_id, *lat, *lon])


def validate_row(row: CoordinateRow) -> None:
    if not 0 <= row.lat_min < 60 or not 0 <= row.lon_min < 60:
        raise ValueError("Minutes must be between 0 and 59.999")
    if not 0 <= row.lat_sec < 60 or not 0 <= row.lon_sec < 60:
        raise ValueError("Seconds must be between 0 and 59.999")
    if not -90 <= row.lat_deg <= 90:
        raise ValueError("Latitude degrees must be between -90 and 90")
    if not -180 <= row.lon_deg <= 180:
        raise ValueError("Longitude degrees must be between -180 and 180")


def _coordinate_directions(text: str, axis_order: str) -> tuple[str, str]:
    directions = [match.upper() for match in HEMISPHERE_RE.findall(text.upper())]
    first = directions[0] if directions else ""
    second = directions[1] if len(directions) > 1 else ""
    if axis_order == "lon_lat":
        return second, first
    return first, second


def detect_coordinate_format(number_count: int) -> tuple[str | None, bool]:
    """Return format and whether a point identifier is present."""
    for name, with_id, without_id in (("dms", 7, 6), ("dm", 5, 4), ("dd", 3, 2)):
        if number_count == with_id:
            return name, True
        if number_count == without_id:
            return name, False
    return None, False


def _row_from_line(
    text: str,
    line_number: int,
    coordinate_format: str,
    axis_order: str,
) -> tuple[CoordinateRow, str]:
    values = numbers_from_text(text)
    detected, has_point_id = detect_coordinate_format(len(values))
    selected_format = detected if coordinate_format == "auto" else coordinate_format
    if selected_format not in FORMATS[1:]:
        raise ValueError(f"Cannot detect coordinate format from {len(values)} numbers")
    expected = {"dms": (7, 6), "dm": (5, 4), "dd": (3, 2)}[selected_format]
    if len(values) not in expected:
        raise ValueError(
            f"Format {selected_format.upper()} expects {expected[0]} numbers with a point ID "
            f"or {expected[1]} without one; found {len(values)}"
        )
    has_point_id = len(values) == expected[0]
    if has_point_id:
        raw_point = values.pop(0)
        point_id = int(raw_point)
        if raw_point != point_id or point_id < 1:
            raise ValueError("Point number must be a positive integer")
    else:
        point_id = line_number

    if selected_format == "dms":
        first = dms_to_decimal(*values[:3])
        second = dms_to_decimal(*values[3:6])
    elif selected_format == "dm":
        first = dms_to_decimal(values[0], values[1], 0)
        second = dms_to_decimal(values[2], values[3], 0)
    else:
        first, second = values

    latitude, longitude = (second, first) if axis_order == "lon_lat" else (first, second)
    lat_direction, lon_direction = _coordinate_directions(text, axis_order)
    if lat_direction:
        latitude = abs(latitude) * (-1 if lat_direction == "S" else 1)
    if lon_direction:
        longitude = abs(longitude) * (-1 if lon_direction == "W" else 1)
    row = row_from_decimal(point_id, latitude, longitude)
    return row, selected_format


def parse_coordinate_lines(
    lines: Iterable[str],
    coordinate_format: str = "auto",
    axis_order: str = "lat_lon",
    sort_by_point: bool = True,
) -> tuple[list[CoordinateRow], list[str], str | None]:
    if coordinate_format not in FORMATS:
        raise ValueError(f"Unsupported coordinate format: {coordinate_format}")
    if axis_order not in {"lat_lon", "lon_lat"}:
        raise ValueError(f"Unsupported axis order: {axis_order}")
    rows: list[CoordinateRow] = []
    warnings: list[str] = []
    detected_formats: list[str] = []
    for line_number, text in enumerate(lines, start=1):
        values = numbers_from_text(text)
        if not values:
            continue
        try:
            row, detected = _row_from_line(text, line_number, coordinate_format, axis_order)
            rows.append(row)
            detected_formats.append(detected)
        except ValueError as error:
            warnings.append(f"Line {line_number}: {error}")
    if sort_by_point:
        rows.sort(key=lambda item: item.point_id)
    duplicate_ids = sorted({r.point_id for r in rows if sum(x.point_id == r.point_id for x in rows) > 1})
    if duplicate_ids:
        warnings.append("Duplicate point numbers: " + ", ".join(map(str, duplicate_ids)))
    unique_formats = set(detected_formats)
    detected_format = next(iter(unique_formats)) if len(unique_formats) == 1 else None
    if len(unique_formats) > 1:
        warnings.append("Mixed coordinate formats were detected")
    return rows, warnings, detected_format


def parse_lines(lines: Iterable[str]) -> tuple[list[CoordinateRow], list[str]]:
    rows, warnings, _ = parse_coordinate_lines(lines, "dms", "lat_lon", True)
    return rows, warnings


def closed_vertices(rows: Sequence[CoordinateRow], close: bool) -> list[tuple[float, float]]:
    vertices = [(row.longitude, row.latitude) for row in rows]
    if close and vertices and vertices[-1] != vertices[0]:
        vertices.append(vertices[0])
    return vertices


def coordinate_quality_issues(rows: Sequence[CoordinateRow]) -> list[tuple[str, tuple[int, ...]]]:
    """Return dependency-free coordinate-table issues for UI reporting."""
    issues: list[tuple[str, tuple[int, ...]]] = []
    point_ids = [row.point_id for row in rows]
    duplicate_ids = tuple(sorted({value for value in point_ids if point_ids.count(value) > 1}))
    if duplicate_ids:
        issues.append(("duplicate_point_ids", duplicate_ids))
    if point_ids:
        present = set(point_ids)
        missing = tuple(value for value in range(min(point_ids), max(point_ids) + 1) if value not in present)
        if missing:
            issues.append(("missing_point_ids", missing))
    coincident = []
    for first, second in zip(rows, rows[1:]):
        if (first.longitude, first.latitude) == (second.longitude, second.latitude):
            coincident.extend((first.point_id, second.point_id))
    if coincident:
        issues.append(("coincident_vertices", tuple(dict.fromkeys(coincident))))
    if len(rows) > 2 and (rows[0].longitude, rows[0].latitude) == (
        rows[-1].longitude,
        rows[-1].latitude,
    ):
        issues.append(("repeated_closing_vertex", (rows[0].point_id, rows[-1].point_id)))
    return issues


CSV_HEADERS = (
    "point_id",
    "latitude_deg",
    "latitude_min",
    "latitude_sec",
    "longitude_deg",
    "longitude_min",
    "longitude_sec",
    "latitude_dd",
    "longitude_dd",
    "ocr_confidence_min_pct",
)


def coordinate_csv_row(
    row: CoordinateRow, confidences: Sequence[float | None] = ()
) -> list[str]:
    """Return one stable, locale-independent CSV record."""
    known = [value for value in confidences if value is not None]
    confidence = f"{min(known) * 100:.1f}" if known else ""
    return [
        *row.as_cells(),
        f"{row.latitude:.8f}",
        f"{row.longitude:.8f}",
        confidence,
    ]
