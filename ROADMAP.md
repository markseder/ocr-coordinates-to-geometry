# Development roadmap

[Русская версия](ROADMAP_RU.md)

The roadmap is directional. A feature is released only after implementation,
tests, documentation and a real QGIS 4 field test.

## v0.3 — Product foundation

- [x] English/Russian interface and extensible translation catalog.
- [x] Plugin icon and consistent product name.
- [x] About, diagnostics and support links.
- [x] Persistent user settings.
- [x] QGIS official repository packaging and validation.
- [ ] Sanitized sample-image test collection.

## v0.4 — Coordinate formats

- [ ] DMS, decimal degrees and degrees/decimal-minutes.
- [ ] Automatic format detection with explicit override.
- [ ] Latitude/longitude and X/Y order reversal.
- [ ] N/S/E/W hemisphere suffixes and signed coordinates.
- [ ] Paste recognized/plain coordinate text without an image.
- [ ] Row-order preservation or sorting by point identifier.

## v0.5 — Source CRS and layer naming

- [x] Source CRS selector using the standard QGIS catalog.
- [x] EPSG:4326 as the safe default.
- [x] Custom base name for created layers.
- [x] Persist the selected CRS and layer name.
- [x] Leave coordinate transformation to standard QGIS tools.
- [x] Confirm v0.5.0 in QGIS 4.0 on Windows 10/11.

## v0.6 — Quality control

- [ ] Per-cell OCR confidence and warning highlighting.
- [x] Duplicate, missing and coincident vertex checks.
- [x] Self-intersection and invalid-ring checks.
- [x] CRS-aware length, area and perimeter calculation.
- [x] Pre-creation quality review with cancel/edit path.
- [ ] Outlier vertex checks.
- [ ] Area comparison with document values.
- [ ] Before/after audit report.
- [ ] Undo or remove the most recently created result.

## v0.7 — Documents and batch processing

- [ ] PDF page import and table-region selection.
- [ ] Multiple tables in one document.
- [ ] Batch image/folder processing.
- [ ] Reusable templates for recurring document layouts.
- [ ] GeoPackage, SHP, DXF, KML and GeoJSON export.

## v0.8 — Extensibility and integration

- [ ] Processing Toolbox algorithm.
- [ ] Template/recognizer plugin interface.
- [ ] OreScope integration and document-to-deposit workflow.
- [ ] Optional organization-wide configuration.
- [ ] Additional UI languages contributed by the community.

## v1.0 — Stable release

- [ ] Stable public API and documented data model.
- [ ] Automated compatibility tests for supported QGIS versions.
- [ ] Signed/reproducible packages and dependency manifest.
- [ ] Complete user manual and troubleshooting guide.
- [ ] Migration policy and long-term support plan.

## Non-negotiable principles

- Local processing by default.
- Human review before geometry creation.
- No silent CRS or datum assumptions.
- Reproducible transformations and auditable results.
- Real documents drive parser development.
