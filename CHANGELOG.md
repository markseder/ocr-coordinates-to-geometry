# Changelog

All notable changes are recorded here. The project follows semantic versioning
while it matures toward 1.0.

## Unreleased

## 0.6.2 — 2026-08-26

- Added CSV export for the reviewed coordinate table.
- Added DMS and decimal-degree coordinates to each CSV record.
- Added minimum OCR confidence per row when available.
- Used UTF-8 with BOM and semicolon delimiters for Excel and QGIS compatibility.
- Remembered the last CSV destination folder.
- Confirmed with QGIS and Excel on Windows.

## 0.6.1 — 2026-08-26

- Preserved confidence scores returned by RapidOCR.
- Added green, yellow and red confidence highlighting to recognized values.
- Added exact confidence percentages in table-cell tooltips.
- Added low-confidence point warnings to the pre-creation review.
- Clear OCR confidence styling when a user manually edits a row.
- Confirmed in QGIS 4.0 on Windows.

## 0.6.0 — 2026-08-26

- Added a pre-creation quality review dialog.
- Added missing point-number and coincident-vertex checks.
- Added QGIS geometry validation, including self-intersection reporting.
- Added CRS-aware line length, perimeter and area measurements.
- Added an explicit choice to create layers or return to editing.
- Confirmed in QGIS 4.0 on Windows.

## 0.5.0 — 2026-08-26

- Added source CRS selection through the standard QGIS CRS catalog.
- Added a custom base name for output point, line and polygon layers.
- Persisted the selected source CRS and layer name.
- Kept coordinate transformation in standard QGIS tools.

## 0.4.0 — 2026-08-26

- Added automatic/manual DMS, DM and DD coordinate-format selection.
- Added latitude/longitude axis reversal.
- Added N/S/E/W hemisphere suffixes and signed values.
- Added plain-text coordinate paste without an image.
- Added source-order preservation or point-number sorting.
- Added live decimal-degree preview columns.
- Added Matveev Pavel as a developer and project contact.
- Expanded the parser test suite.

## 0.3.0 — 2026-08-26

- Adopted the OCR2Geometry product name and custom icon.
- Added English and Russian runtime localization based on the QGIS locale.
- Added persistent geometry options, window size and last image directory.
- Added About and environment-diagnostics tools.
- Added structural package validation for QGIS repository requirements.
- Expanded the automated test suite to 11 tests.
- Added bilingual project documentation and a public development roadmap.

## 0.2.0 — 2026-08-26

- Added automatic one-click RapidOCR and ONNX Runtime installation.
- Dependencies are stored in the QGIS user profile without administrator rights.
- Added a manual **Install OCR** recovery button.

## 0.1.0 — 2026-08-26

- First QGIS 4 MVP.
- Image loading and clipboard paste.
- Editable DMS recognition preview.
- Numbered points, line closing and optional polygon creation.
- EPSG:4326 memory layers.
