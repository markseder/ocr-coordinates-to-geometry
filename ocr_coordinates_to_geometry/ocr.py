"""RapidOCR adapter kept separate from QGIS and geometry code."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OcrUnavailableError(RuntimeError):
    pass


@dataclass
class OcrToken:
    text: str
    x: float
    y: float
    confidence: float | None = None


@dataclass(frozen=True)
class OcrLine:
    text: str
    confidences: tuple[float | None, ...] = ()


def _load_engine():
    from .dependencies import activate_vendor_directory

    activate_vendor_directory()
    errors = []
    try:
        from rapidocr import RapidOCR

        return RapidOCR()
    except Exception as error:
        errors.append(error)
    try:
        from rapidocr_onnxruntime import RapidOCR

        return RapidOCR()
    except Exception as error:
        errors.append(error)
    raise OcrUnavailableError(
        "RapidOCR не установлен или не загрузился. Нажмите «Установить OCR»."
    ) from errors[-1]


def _items_from_result(result: Any) -> list[Any]:
    if result is None:
        return []
    if hasattr(result, "txts") and hasattr(result, "boxes"):
        scores = getattr(result, "scores", None)
        if scores is None:
            scores = [None] * len(result.txts)
        return list(zip(result.boxes, result.txts, scores))
    if isinstance(result, tuple):
        result = result[0]
    return list(result or [])


def _group_adjacent(indices):
    """Return centers of consecutive integer runs."""
    import numpy as np

    if len(indices) == 0:
        return []
    groups = np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
    return [int(np.mean(group)) for group in groups if len(group)]


def _recognize_grid_cells(engine, image_path: str | Path) -> list[OcrLine]:
    """Recognize a ruled seven-column table one cell at a time.

    Tiny scans are much more reliable this way: table lines establish the
    rows/columns and RapidOCR only has to recognize one short number per cell.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None or image.shape[0] < 10 or image.shape[1] < 20:
        return []
    height, width = image.shape
    vertical_binary = cv2.threshold(image, 200, 255, cv2.THRESH_BINARY_INV)[1]
    horizontal_binary = cv2.threshold(image, 245, 255, cv2.THRESH_BINARY_INV)[1]
    vertical = cv2.morphologyEx(
        vertical_binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(8, height // 8))),
    )
    horizontal = cv2.morphologyEx(
        horizontal_binary,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, width // 25), 1)),
    )
    xs = _group_adjacent(np.where((vertical > 0).sum(axis=0) > height * 0.50)[0])
    ys = _group_adjacent(np.where((horizontal > 0).sum(axis=1) > width * 0.33)[0])
    column_count = len(xs) - 1
    if column_count not in {3, 5, 7} or len(ys) < 2:
        return []

    lines = []
    for row_index in range(len(ys) - 1):
        values = []
        confidences = []
        for column in range(column_count):
            top, bottom = ys[row_index] + 2, ys[row_index + 1] - 2
            left, right = xs[column] + 2, xs[column + 1] - 2
            crop = image[top:bottom, left:right]
            if crop.size == 0:
                return []
            scale = max(3.0, min(8.0, 80.0 / max(1, crop.shape[0])))
            crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            crop = cv2.copyMakeBorder(crop, 15, 15, 15, 15, cv2.BORDER_CONSTANT, value=255)
            result = engine(crop, use_det=False, use_cls=False, use_rec=True)
            texts = getattr(result, "txts", ()) or ()
            scores = getattr(result, "scores", ()) or ()
            values.append(str(texts[0]).strip() if texts else "")
            confidences.append(float(scores[0]) if scores else None)
        if all(values):
            lines.append(OcrLine(" ".join(values), tuple(confidences)))
    return lines


def recognize_lines(image_path: str | Path) -> list[OcrLine]:
    engine = _load_engine()
    grid_lines = _recognize_grid_cells(engine, image_path)
    if grid_lines:
        return grid_lines
    raw = engine(str(image_path))
    tokens: list[OcrToken] = []
    for item in _items_from_result(raw):
        try:
            box, text = item[0], str(item[1])
            confidence = float(item[2]) if len(item) > 2 and item[2] is not None else None
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            tokens.append(OcrToken(text, sum(xs) / len(xs), sum(ys) / len(ys), confidence))
        except (TypeError, ValueError, IndexError):
            continue
    if not tokens:
        return []
    tokens.sort(key=lambda token: token.y)
    heights = []
    for item in _items_from_result(raw):
        try:
            box = item[0]
            heights.append(max(float(p[1]) for p in box) - min(float(p[1]) for p in box))
        except (TypeError, ValueError, IndexError):
            pass
    tolerance = max(6.0, (sum(heights) / len(heights) if heights else 12.0) * 0.65)
    groups: dict[int, list[OcrToken]] = defaultdict(list)
    centers: list[float] = []
    for token in tokens:
        group_index = next((i for i, center in enumerate(centers) if abs(token.y - center) <= tolerance), None)
        if group_index is None:
            centers.append(token.y)
            group_index = len(centers) - 1
        groups[group_index].append(token)
    lines = []
    for index in sorted(groups, key=lambda idx: centers[idx]):
        ordered = sorted(groups[index], key=lambda token: token.x)
        lines.append(
            OcrLine(
                " ".join(token.text for token in ordered),
                tuple(token.confidence for token in ordered),
            )
        )
    return lines
