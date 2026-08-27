# Troubleshooting

- **OCR is unavailable:** use **Install OCR**, keep QGIS open until completion,
  then retry. A proxy or antivirus may block pip downloads.
- **Geometry appears in the wrong place:** verify axis order and source CRS.
  Assigning CRS does not reproject numbers.
- **Paste starts in the wrong column:** copy only the data range; supported
  two-, three-, seven-, eight- and nine-column layouts are detected automatically.
- **Need support:** copy diagnostics from **About** and attach a sanitized sample
  and exact reproduction steps to a GitHub issue.
