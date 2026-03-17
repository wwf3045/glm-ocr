from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from clean_junk_images import IMAGE_EXTS
from ocr_image_index import (
    audit_orphan_images,
    collect_referenced_image_counts,
    inspect_image_size,
    is_page_like_size,
    iter_image_targets,
    normalize_image_target,
)


LEGACY_PAGE_IMAGE_PATTERN = re.compile(r"^page_\d+_img_\d+\.(png|jpe?g|bmp|webp)$", re.IGNORECASE)
DEFAULT_ROOT = Path(r"F:\中间文件库")


@dataclass
class BookImageStats:
    book_dir: Path
    total_images: int
    referenced_images: int
    orphan_images: int
    page_like_orphans: int
    legacy_orphans: int
    broken_refs: int
    deleted_legacy: int = 0
    deleted_page_like: int = 0
    delete_failures: int = 0
    removed_images_dir: bool = False

    @property
    def deleted_total(self) -> int:
        return self.deleted_legacy + self.deleted_page_like

    def to_dict(self) -> dict:
        return {
            "book_dir": str(self.book_dir),
            "total_images": self.total_images,
            "referenced_images": self.referenced_images,
            "orphan_images": self.orphan_images,
            "page_like_orphans": self.page_like_orphans,
            "legacy_orphans": self.legacy_orphans,
            "broken_refs": self.broken_refs,
            "deleted_legacy": self.deleted_legacy,
            "deleted_page_like": self.deleted_page_like,
            "deleted_total": self.deleted_total,
            "delete_failures": self.delete_failures,
            "removed_images_dir": self.removed_images_dir,
        }


def iter_book_dirs(root: Path):
    for images_dir in sorted(root.rglob("images")):
        if images_dir.is_dir():
            yield images_dir.parent


def count_broken_refs(book_dir: Path) -> int:
    broken = 0
    images_dir = book_dir / "images"
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
            if not (images_dir / target_path.name).exists():
                broken += 1
    return broken


def audit_book_dir(book_dir: Path) -> BookImageStats:
    audit = audit_orphan_images(book_dir)
    legacy_orphans = 0
    referenced = collect_referenced_image_counts(book_dir)
    images_dir = book_dir / "images"
    if images_dir.exists():
        for image_path in images_dir.iterdir():
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
                continue
            if referenced.get(image_path.name, 0) > 0:
                continue
            if LEGACY_PAGE_IMAGE_PATTERN.match(image_path.name):
                legacy_orphans += 1

    return BookImageStats(
        book_dir=book_dir,
        total_images=audit["total_images"],
        referenced_images=audit["referenced_images"],
        orphan_images=audit["orphan_images"],
        page_like_orphans=audit["page_like_orphans"],
        legacy_orphans=legacy_orphans,
        broken_refs=count_broken_refs(book_dir),
    )


def cleanup_book_dir(
    book_dir: Path,
    dry_run: bool = False,
    remove_all_orphans: bool = False,
) -> BookImageStats:
    images_dir = book_dir / "images"
    stats_before = audit_book_dir(book_dir)
    deleted_legacy = 0
    deleted_page_like = 0
    deleted_other_orphans = 0
    delete_failures = 0
    removed_images_dir = False

    def try_unlink(image_path: Path) -> bool:
        nonlocal delete_failures
        if dry_run:
            return True
        try:
            image_path.unlink()
            return True
        except OSError:
            delete_failures += 1
            return False

    if images_dir.exists():
        referenced = collect_referenced_image_counts(book_dir)
        for image_path in sorted(images_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTS:
                continue
            if referenced.get(image_path.name, 0) > 0:
                continue
            if LEGACY_PAGE_IMAGE_PATTERN.match(image_path.name):
                if try_unlink(image_path):
                    deleted_legacy += 1
                continue
            size = inspect_image_size(image_path)
            if size and is_page_like_size(*size):
                if try_unlink(image_path):
                    deleted_page_like += 1
                continue
            if remove_all_orphans:
                if try_unlink(image_path):
                    deleted_other_orphans += 1

        if not dry_run and images_dir.is_dir() and not any(images_dir.iterdir()):
            images_dir.rmdir()
            removed_images_dir = True

    stats_after = audit_book_dir(book_dir)
    stats_after.deleted_legacy = deleted_legacy
    stats_after.deleted_page_like = deleted_page_like + deleted_other_orphans
    stats_after.delete_failures = delete_failures
    stats_after.removed_images_dir = removed_images_dir
    if dry_run:
        stats_after = stats_before
        stats_after.deleted_legacy = deleted_legacy
        stats_after.deleted_page_like = deleted_page_like + deleted_other_orphans
        stats_after.delete_failures = delete_failures
        stats_after.removed_images_dir = False
    return stats_after


def summarize_books(book_stats: list[BookImageStats]) -> dict:
    summary = Counter()
    summary["books"] = len(book_stats)
    for stats in book_stats:
        summary["total_images"] += stats.total_images
        summary["referenced_images"] += stats.referenced_images
        summary["orphan_images"] += stats.orphan_images
        summary["page_like_orphans"] += stats.page_like_orphans
        summary["legacy_orphans"] += stats.legacy_orphans
        summary["broken_refs"] += stats.broken_refs
        summary["deleted_legacy"] += stats.deleted_legacy
        summary["deleted_page_like"] += stats.deleted_page_like
        summary["deleted_total"] += stats.deleted_total
        summary["delete_failures"] += stats.delete_failures
        if stats.orphan_images:
            summary["books_with_orphans"] += 1
        if stats.page_like_orphans:
            summary["books_with_page_like_orphans"] += 1
        if stats.legacy_orphans:
            summary["books_with_legacy_orphans"] += 1
        if stats.broken_refs:
            summary["books_with_broken_refs"] += 1
        if stats.deleted_total:
            summary["books_changed"] += 1
        if stats.removed_images_dir:
            summary["removed_images_dirs"] += 1
    return dict(summary)


def write_report(root: Path, mode: str, stats: list[BookImageStats]) -> tuple[Path, Path]:
    report_dir = root / "_audit" / "image_maintenance"
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"{stamp}_{mode}.json"
    md_path = report_dir / f"{stamp}_{mode}.md"

    payload = {
        "root": str(root),
        "mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summarize_books(stats),
        "books": [item.to_dict() for item in stats],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    rows = sorted(
        [item for item in stats if item.orphan_images or item.deleted_total or item.broken_refs],
        key=lambda item: (item.deleted_total, item.orphan_images, item.page_like_orphans, item.broken_refs),
        reverse=True,
    )
    lines = [
        "# Middle Library Image Maintenance",
        "",
        f"- root: `{root}`",
        f"- mode: `{mode}`",
        f"- generated_at: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Problem Books", ""])
    if not rows:
        lines.append("- none")
    else:
        for item in rows[:200]:
            lines.extend(
                [
                    f"### `{item.book_dir}`",
                    f"- total_images: `{item.total_images}`",
                    f"- orphan_images: `{item.orphan_images}`",
                    f"- page_like_orphans: `{item.page_like_orphans}`",
                    f"- legacy_orphans: `{item.legacy_orphans}`",
                    f"- broken_refs: `{item.broken_refs}`",
                    f"- deleted_total: `{item.deleted_total}`",
                    f"- delete_failures: `{item.delete_failures}`",
                    "",
                ]
            )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def run(
    root: Path,
    mode: str,
    dry_run: bool = False,
    remove_all_orphans: bool = False,
) -> tuple[dict, Path, Path]:
    if mode not in {"audit", "cleanup"}:
        raise ValueError(f"unsupported mode: {mode}")
    stats: list[BookImageStats] = []
    for book_dir in iter_book_dirs(root):
        if mode == "cleanup":
            stats.append(
                cleanup_book_dir(
                    book_dir,
                    dry_run=dry_run,
                    remove_all_orphans=remove_all_orphans,
                )
            )
        else:
            stats.append(audit_book_dir(book_dir))
    mode_name = f"{mode}{'_dryrun' if dry_run else ''}{'_allorphans' if remove_all_orphans else ''}"
    json_path, md_path = write_report(root, mode_name, stats)
    return summarize_books(stats), json_path, md_path


def main():
    parser = argparse.ArgumentParser(description="审计并清理中间文件库中的 OCR 图片残留。")
    parser.add_argument("mode", choices=["audit", "cleanup"])
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="中间文件库根目录")
    parser.add_argument("--dry-run", action="store_true", help="仅统计将删除什么，不真正删除")
    parser.add_argument(
        "--all-orphans",
        action="store_true",
        help="清理所有未被正文引用的图片，而不仅是 legacy/整页候选图。",
    )
    args = parser.parse_args()

    root = Path(args.root)
    summary, json_path, md_path = run(
        root,
        args.mode,
        dry_run=args.dry_run,
        remove_all_orphans=args.all_orphans,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"json_report: {json_path}")
    print(f"md_report: {md_path}")


if __name__ == "__main__":
    main()
