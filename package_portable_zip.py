from __future__ import annotations

import argparse
from pathlib import Path
import zipfile


def build_zip(source_dir: Path, zip_path: Path) -> None:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    root = source_dir.parent
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(root))


def main() -> None:
    parser = argparse.ArgumentParser(description="Package a portable zip from a built dist folder.")
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    build_zip(args.source_dir.resolve(), args.zip_path.resolve())


if __name__ == "__main__":
    main()
