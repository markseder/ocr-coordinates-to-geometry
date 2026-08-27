# Third-party notices

OCR2Geometry is distributed under the MIT License; see `LICENSE`.

The plugin does not bundle its optional OCR runtime or model files. On explicit
user request, pip downloads them into the active QGIS user profile:

- **RapidOCR** — Apache License 2.0. OCR model copyright is held by Baidu.
  <https://github.com/RapidAI/RapidOCR>
- **ONNX Runtime** — MIT License.
  <https://github.com/microsoft/onnxruntime>

Those packages and downloaded models remain subject to their own upstream
licences and notices. Their declared version ranges are in
`requirements-ocr.txt`.
