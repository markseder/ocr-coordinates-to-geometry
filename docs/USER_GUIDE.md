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


## Validation and precision in 1.0.2

- Invalid DMS/DM components and coordinates beyond ±90° latitude / ±180° longitude
  are rejected before normalization.
- Second decimals affect display only. Opening a cell editor exposes its exact
  stored value; geometry and CSV decimal-degree columns use that value. CSV DMS
  follows display precision, while CSV decimal degrees use eight decimal places.
- Invalid manual input clears derived cells and prevents acceptance until repaired.
- Incomplete OCR rows remain red in the main table. Hover to read the original
  source text, then repair the DMS cells or deliberately delete the row after
  comparing it with the image. Unparseable DD/DM rows need manual DMS entry,
  including the point ID if it is blank.
- Color represents minimum OCR confidence for the whole row, not the probability
  that a particular calculated coordinate is correct.
- Select a geographic source CRS using degrees. Projected CRS and planar X/Y input
  are not supported yet; use QGIS tools for subsequent reprojection.
- OCR runs in a worker thread. Individual inference calls cannot be interrupted;
  its progress window closes on completion.
- Installation can be cancelled while pip is silent; total timeout is 20 minutes.
