# OCR2Geometry user guide

## Install

Download the ZIP from GitHub Releases, then use **Plugins → Manage and Install
Plugins → Install from ZIP**. On the first OCR run, approve installation of the
optional RapidOCR dependencies. Images and coordinates remain local.

## From an image

1. Open an image or paste a screenshot and run recognition.
2. Review every cell; confidence colours indicate OCR certainty, not correctness.
3. Select the CRS that already describes the source numbers.
4. Set a layer base name and choose points, line and/or polygon.
5. Review warnings, measurements and geometry before creation.

## Manual entry and CSV

Open **Paste coordinates**, paste an Excel range or edit the DMS/DD cells. DMS
and decimal degrees update in both directions. Rows without point numbers are
numbered automatically. Export the reviewed table with **Save CSV**.

Assigning a CRS does not transform coordinates. Use standard QGIS reprojection
or export tools when a different CRS is required.
