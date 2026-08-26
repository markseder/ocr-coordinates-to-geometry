"""Dependency-free coordinate parsing and validation."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence


NUMBER_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


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
    return str(int(value)) if value.is_integer() else str(value)


def dms_to_decimal(degrees: float, minutes: float, seconds: float) -> float:
    sign = -1.0 if degrees < 0 else 1.0
    return sign * (abs(degrees) + minutes / 60.0 + seconds / 3600.0)


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


def validate_row(row: CoordinateRow) -> None:
    if not 0 <= row.lat_min < 60 or not 0 <= row.lon_min < 60:
        raise ValueError("Minutes must be between 0 and 59.999")
    if not 0 <= row.lat_sec < 60 or not 0 <= row.lon_sec < 60:
        raise ValueError("Seconds must be between 0 and 59.999")
    if not -90 <= row.lat_deg <= 90:
        raise ValueError("Latitude degrees must be between -90 and 90")
    if not -180 <= row.lon_deg <= 180:
        raise ValueError("Longitude degrees must be between -180 and 180")


def parse_lines(lines: Iterable[str]) -> tuple[list[CoordinateRow], list[str]]:
    rows: list[CoordinateRow] = []
    warnings: list[str] = []
    for line_number, text in enumerate(lines, start=1):
        values = numbers_from_text(text)
        if not values:
            continue
        if len(values) != 7:
            warnings.append(f"Line {line_number}: found {len(values)} numbers instead of 7")
            continue
        try:
            rows.append(row_from_values(values))
        except ValueError as error:
            warnings.append(f"Line {line_number}: {error}")
    rows.sort(key=lambda item: item.point_id)
    duplicate_ids = sorted({r.point_id for r in rows if sum(x.point_id == r.point_id for x in rows) > 1})
    if duplicate_ids:
        warnings.append("Duplicate point numbers: " + ", ".join(map(str, duplicate_ids)))
    return rows, warnings


def closed_vertices(rows: Sequence[CoordinateRow], close: bool) -> list[tuple[float, float]]:
    vertices = [(row.longitude, row.latitude) for row in rows]
    if close and vertices and vertices[-1] != vertices[0]:
        vertices.append(vertices[0])
    return vertices
