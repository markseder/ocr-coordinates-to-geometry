"""Dependency-free structural checks for an OCR2Geometry plugin package."""

from __future__ import annotations

import configparser
from pathlib import Path
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "dist" / "ocr_coordinates_to_geometry.zip"
PLUGIN_ROOT = "ocr_coordinates_to_geometry/"
REQUIRED = {
    "__init__.py",
    "metadata.txt",
    "plugin.py",
    "dialog.py",
    "core.py",
    "ocr.py",
    "dependencies.py",
    "i18n.py",
    "icon.svg",
}
FORBIDDEN_PARTS = {"__pycache__", ".git", ".github"}


def validate(path: Path = ZIP_PATH) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"Package not found: {path}"]
    if path.stat().st_size > 25 * 1024 * 1024:
        errors.append("Package exceeds the 25 MB QGIS repository limit")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if any(not name.startswith(PLUGIN_ROOT) for name in names):
            errors.append("Every file must be inside the plugin root directory")
        relative = {name.removeprefix(PLUGIN_ROOT) for name in names}
        missing = REQUIRED - relative
        if missing:
            errors.append("Missing files: " + ", ".join(sorted(missing)))
        for name in names:
            parts = set(Path(name).parts)
            if parts & FORBIDDEN_PARTS or name.endswith((".pyc", ".pyo", ".exe", ".dll")):
                errors.append(f"Forbidden packaged file: {name}")
        try:
            metadata_text = archive.read(PLUGIN_ROOT + "metadata.txt").decode("utf-8")
            parser = configparser.ConfigParser()
            parser.read_string(metadata_text)
            general = parser["general"]
            for key in (
                "name",
                "description",
                "version",
                "qgisMinimumVersion",
                "homepage",
                "repository",
                "tracker",
                "icon",
            ):
                if not general.get(key, "").strip():
                    errors.append(f"Missing metadata key: {key}")
        except Exception as error:
            errors.append(f"Invalid metadata.txt: {error}")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("\n".join(f"ERROR: {problem}" for problem in problems))
        sys.exit(1)
    print(f"Package validation passed: {ZIP_PATH}")
