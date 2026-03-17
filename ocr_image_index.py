from __future__ import annotations

import json
import re
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

from clean_junk_images import IMAGE_EXTS


MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE_PATTERN = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.IGNORECASE)


def normalize_image_target(target: str) -> str:
    normalized = urllib.parse.unquote(target.strip().strip("<>").strip())
    normalized = normalized.split("#", 1)[0].split("?", 1)[0]
    return normalized.replace("\\", "/")


def iter_image_targets(markdown_text: str) -> Iterable[str]:
    for match in MARKDOWN_IMAGE_PATTERN.finditer(markdown_text):
        yield match.group(1)
    for match in HTML_IMAGE_PATTERN.finditer(markdown_text):
        yield match.group(1)


def get_ocr_folder_for_image(image_path: Path) -> Path:
    if image_path.parent.name.lower() == "images":
        return image_path.parent.parent
    return image_path.parent


def collect_referenced_image_counts(book_dir: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not book_dir.exists():
        return counts

    for md_path in book_dir.glob("*.md"):
        try:
            markdown_text = md_path.read_text(encoding="utf-8")
        except OSError:
            continue

        for raw_target in iter_image_targets(markdown_text):
            target = normalize_image_target(raw_target)
            if not target or target.startswith(("http://", "https://", "data:")):
                continue
            target_path = Path(target)
            if not target_path.name:
                continue
            if "images" not in {part.lower() for part in target_path.parts}:
                continue
            counts[target_path.name] += 1
    return counts


def collect_markdown_image_name_counts(md_path: Path) -> Counter[str]:
    counts: Counter[str] = Counter()
    try:
        markdown_text = md_path.read_text(encoding="utf-8")
    except OSError:
        return counts

    for raw_target in iter_image_targets(markdown_text):
        target = normalize_image_target(raw_target)
        if not target or target.startswith(("http://", "https://", "data:")):
            continue
        target_path = Path(target)
        if not target_path.name:
            continue
        if "images" not in {part.lower() for part in target_path.parts}:
            continue
        counts[target_path.name] += 1
    return counts


def build_reference_index(root: Path) -> dict[str, int]:
    index: dict[str, int] = {}
    for images_dir in root.rglob("images"):
        if not images_dir.is_dir():
            continue
        book_dir = images_dir.parent
        referenced = collect_referenced_image_counts(book_dir)
        for image_path in images_dir.iterdir():
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
                continue
            index[str(image_path.resolve())] = referenced.get(image_path.name, 0)
    return index


def inspect_image_size(image_path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(image_path) as image:
            return image.size
    except (OSError, UnidentifiedImageError):
        return None


def is_page_like_size(width: int, height: int) -> bool:
    if min(width, height) < 420 or max(width, height) < 650:
        return False

    aspect = width / max(height, 1)
    portrait_like = 0.55 <= aspect <= 0.88
    landscape_like = 1.10 <= aspect <= 1.95
    return portrait_like or landscape_like


def audit_orphan_images(book_dir: Path, report_name: str = "orphan_images.json") -> dict:
    images_dir = book_dir / "images"
    if not images_dir.exists():
        return {
            "book_dir": str(book_dir),
            "images_dir": str(images_dir),
            "report_path": None,
            "total_images": 0,
            "referenced_images": 0,
            "orphan_images": 0,
            "page_like_orphans": 0,
            "orphans": [],
            "page_like_orphan_records": [],
        }

    referenced = collect_referenced_image_counts(book_dir)
    orphan_records: list[dict] = []
    page_like_records: list[dict] = []
    total_images = 0
    referenced_images = 0

    for image_path in sorted(images_dir.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
            continue
        total_images += 1
        reference_count = referenced.get(image_path.name, 0)
        if reference_count > 0:
            referenced_images += 1
            continue

        size = inspect_image_size(image_path)
        if size is None:
            continue
        width, height = size
        filename_page_like = bool(re.match(r"^page[_-]\d+.*\.(png|jpe?g|webp|bmp)$", image_path.name, re.IGNORECASE))
        page_like = filename_page_like or is_page_like_size(width, height)
        record = {
            "path": str(image_path),
            "name": image_path.name,
            "width": width,
            "height": height,
            "reference_count": 0,
            "page_like": page_like,
            "filename_page_like": filename_page_like,
        }
        orphan_records.append(record)
        if page_like:
            page_like_records.append(record)

    audit_dir = book_dir / "_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    report_path = audit_dir / report_name
    payload = {
        "book_dir": str(book_dir),
        "images_dir": str(images_dir),
        "total_images": total_images,
        "referenced_images": referenced_images,
        "orphan_images": len(orphan_records),
        "page_like_orphans": len(page_like_records),
        "orphans": orphan_records,
        "page_like_orphan_records": page_like_records,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["report_path"] = str(report_path)
    return payload
