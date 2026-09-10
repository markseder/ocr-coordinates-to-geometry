"""Run CPU-bound OCR while the Qt event loop remains responsive."""

from qgis.PyQt.QtCore import QThread, QTimer, Qt
from qgis.PyQt.QtWidgets import QProgressDialog


class _Worker(QThread):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.operation()
        except Exception as error:
            self.error = error


class _Progress(QProgressDialog):
    def reject(self):
        # Inference cannot be safely terminated midway; keep its owner alive.
        pass

    def closeEvent(self, event):
        event.ignore()


def run_background(operation, title, parent):
    worker = _Worker(operation)
    progress = _Progress(title, "", 0, 0, parent)
    progress.setWindowTitle(title)
    progress.setCancelButton(None)
    progress.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    worker.finished.connect(progress.accept)
    # Starting inside exec avoids a race with very fast operations.
    QTimer.singleShot(0, worker.start)
    progress.exec()
    worker.wait()
    progress.deleteLater()
    if worker.error is not None:
        raise worker.error
    return worker.result
