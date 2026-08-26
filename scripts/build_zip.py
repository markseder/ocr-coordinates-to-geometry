from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "ocr_coordinates_to_geometry"
DIST = ROOT / "dist"
OUTPUT = DIST / "ocr_coordinates_to_geometry.zip"


def build():
    DIST.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT))
    print(OUTPUT)


if __name__ == "__main__":
    build()
