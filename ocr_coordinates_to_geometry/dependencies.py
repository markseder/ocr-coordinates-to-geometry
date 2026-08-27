"""Install and load optional OCR packages inside the active QGIS profile."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from qgis.core import QgsApplication


PACKAGES = tuple(
    line.strip()
    for line in Path(__file__).with_name("requirements-ocr.txt").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.lstrip().startswith("#")
)


def vendor_directory() -> Path:
    path = Path(QgsApplication.qgisSettingsDirPath()) / "python" / "ocr_coordinates_to_geometry_vendor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def activate_vendor_directory() -> Path:
    path = vendor_directory()
    value = os.fspath(path)
    if value not in sys.path:
        sys.path.insert(0, value)
    return path


def rapidocr_available() -> bool:
    activate_vendor_directory()
    try:
        from rapidocr import RapidOCR  # noqa: F401

        return True
    except Exception:
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401

            return True
        except Exception:
            return False


def qgis_python_executable() -> Path:
    executable = Path(sys.executable)
    if executable.name.lower().startswith("python"):
        return executable
    candidates = [
        Path(sys.prefix) / "python.exe",
        Path(sys.prefix) / "python3.exe",
        Path(sys.prefix) / "bin" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        "Не найден Python, поставляемый с QGIS. "
        "Переустановите QGIS с компонентом Python/PIP."
    )


def install_rapidocr(progress_callback=None, cancelled_callback=None) -> tuple[bool, str]:
    """Install OCR into the user profile and return success plus captured log."""
    target = activate_vendor_directory()
    python = qgis_python_executable()
    command = [
        os.fspath(python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--upgrade",
        "--target",
        os.fspath(target),
        *PACKAGES,
    ]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # The executable is the QGIS-bundled Python and every argument is built
    # locally from fixed package requirements; no user input reaches command.
    process = subprocess.Popen(  # nosec B603
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags,
    )
    output: list[str] = []
    while process.poll() is None:
        if cancelled_callback and cancelled_callback():
            process.terminate()
            return False, "Установка отменена пользователем."
        line = process.stdout.readline() if process.stdout else ""
        if line:
            output.append(line)
            if progress_callback:
                progress_callback(line.strip())
    if process.stdout:
        output.extend(process.stdout.readlines())
    log = "".join(output)
    if process.returncode != 0:
        return False, log or f"pip завершился с кодом {process.returncode}"
    # Python may have cached failed imports while the package was absent.
    for name in tuple(sys.modules):
        if name == "rapidocr" or name.startswith("rapidocr."):
            sys.modules.pop(name, None)
    return rapidocr_available(), log
