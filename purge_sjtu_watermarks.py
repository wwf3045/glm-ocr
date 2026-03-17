from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clean_junk_images import IMAGE_EXTS, clean_md_references
from duplicate_image_reviewer import ImageEntry, build_image_entry


@dataclass(frozen=True)
class WatermarkFamily:
    name: str
    width: int
    height: int
    ahash: int
    dhash: int
    threshold: int
    max_aspect_diff: float
    max_width_ratio: float
    max_height_ratio: float


KNOWN_FAMILIES = [
    WatermarkFamily(
        name="sjtu_square_logo",
        width=150,
        height=152,
        ahash=18150493454499693559,
        dhash=16764883468265777384,
        threshold=10,
        max_aspect_diff=0.22,
        max_width_ratio=2.6,
        max_height_ratio=2.6,
    ),
    WatermarkFamily(
        name="sjtu_banner_watermark",
        width=596,
        height=164,
        ahash=13780491630198857791,
        dhash=11508302015949023922,
        threshold=10,
        max_aspect_diff=0.30,
        max_width_ratio=2.8,
        max_height_ratio=2.8,
    ),
]


def iter_images(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS
    ]


def matches_family(entry: ImageEntry, family: WatermarkFamily) -> bool:
    entry_aspect = entry.width / max(entry.height, 1)
    family_aspect = family.width / max(family.height, 1)
    if abs(entry_aspect - family_aspect) > family.max_aspect_diff:
        return False

    width_ratio = max(entry.width, family.width) / max(1, min(entry.width, family.width))
    height_ratio = max(entry.height, family.height) / max(1, min(entry.height, family.height))
    if width_ratio > family.max_width_ratio or height_ratio > family.max_height_ratio:
        return False

    distance = (entry.ahash ^ family.ahash).bit_count() + (entry.dhash ^ family.dhash).bit_count()
    return distance <= family.threshold


def scan_matches(root: Path) -> dict[str, list[str]]:
    entries: list[ImageEntry] = []
    for path in iter_images(root):
        try:
            entries.append(build_image_entry(path))
        except Exception:
            continue

    matched: dict[str, list[str]] = {family.name: [] for family in KNOWN_FAMILIES}
    for entry in entries:
        for family in KNOWN_FAMILIES:
            if matches_family(entry, family):
                matched[family.name].append(entry.path)
                break
    return matched


def purge_paths(root: Path, paths: list[str]) -> dict[str, Any]:
    by_folder: dict[Path, list[str]] = {}
    deleted = 0
    freed_bytes = 0

    for item in paths:
        image_path = Path(item)
        if not image_path.is_absolute():
            image_path = (root / image_path).resolve()
        if not image_path.exists() or not image_path.is_file():
            continue
        freed_bytes += image_path.stat().st_size
        by_folder.setdefault(image_path.parent.parent, []).append(image_path.name)
        image_path.unlink()
        deleted += 1

    cleaned_md = 0
    for ocr_folder, image_names in by_folder.items():
        if not ocr_folder.exists():
            continue
        for md_path in ocr_folder.glob("*.md"):
            before = md_path.read_text(encoding="utf-8")
            clean_md_references(md_path, image_names)
            after = md_path.read_text(encoding="utf-8")
            if before != after:
                cleaned_md += 1

    return {
        "deleted": deleted,
        "freed_bytes": freed_bytes,
        "cleaned_md": cleaned_md,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Purge known SJTU logo/watermark OCR junk images by grayscale family signatures."
    )
    parser.add_argument(
        "--root",
        type=Path,
        required=True,
        help="Root directory to scan.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Delete matched watermark images and clean Markdown references.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"找不到目录：{root}")

    matched = scan_matches(root)
    report = {
        "root": str(root),
        "families": [
            {"name": family.name, "count": len(matched[family.name]), "paths": matched[family.name]}
            for family in KNOWN_FAMILIES
        ],
    }

    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(len(paths) for paths in matched.values())
    print(f"[INFO] 命中水印图片 {total} 张")
    for family in KNOWN_FAMILIES:
        print(f"- {family.name}: {len(matched[family.name])}")

    if args.purge:
        unique_paths = sorted({path for paths in matched.values() for path in paths})
        result = purge_paths(root, unique_paths)
        print(
            f"[OK] 删除 {result['deleted']} 张图片，清理 {result['cleaned_md']} 个 Markdown 文件，"
            f"释放 {result['freed_bytes'] / 1024 / 1024:.2f} MB"
        )


if __name__ == "__main__":
    main()
