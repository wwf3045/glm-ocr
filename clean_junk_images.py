from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
DEFAULT_ROOT = Path("output")
AUDIT_DIRNAME = "_junk_image_audit"

# Legacy size rules are kept only as an explicit fallback mode.
SUNFLOWER_SIZE = int(3.2 * 1024 * 1024)
GEAR_MAX_SIZE = int(3 * 1024)
SIDEBAR_MAX_SIZE = int(2.5 * 1024)


@dataclass
class ImageRecord:
    path: str
    md5: str
    size_bytes: int
    width: int
    height: int
    ahash: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OCR junk-image audit and cleanup helper."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser(
        "audit",
        help="Audit exact duplicate images and export a manual-review report.",
    )
    add_root_arg(audit_parser)
    audit_parser.add_argument(
        "--min-count",
        type=int,
        default=4,
        help="Only export exact duplicate groups with at least this many images.",
    )
    audit_parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory to write audit reports. Defaults to <root>/_junk_image_audit.",
    )
    audit_parser.add_argument(
        "--copy-samples",
        action="store_true",
        help="Copy one representative image for each group into the audit directory.",
    )

    similar_parser = subparsers.add_parser(
        "similar",
        help="Find images perceptually similar to a manually confirmed junk sample.",
    )
    add_root_arg(similar_parser)
    similar_parser.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="Representative junk image picked after manual review.",
    )
    similar_parser.add_argument(
        "--threshold",
        type=int,
        default=8,
        help="Maximum Hamming distance of average-hash similarity.",
    )
    similar_parser.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        help="Directory to write similarity reports. Defaults to <root>/_junk_image_audit.",
    )
    similar_parser.add_argument(
        "--copy-samples",
        action="store_true",
        help="Copy all matched images into the audit directory.",
    )

    purge_parser = subparsers.add_parser(
        "purge",
        help="Delete manually approved junk images from a manifest file.",
    )
    add_root_arg(purge_parser)
    purge_parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Text or JSON manifest listing image paths to delete.",
    )

    legacy_parser = subparsers.add_parser(
        "legacy-size-clean",
        help="Run the old size-based cleanup rules explicitly.",
    )
    add_root_arg(legacy_parser)

    return parser.parse_args()


def add_root_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Root directory containing OCR outputs or image trees.",
    )


def iter_images(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            yield path


def compute_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def average_hash(path: Path, size: int = 16) -> str:
    with Image.open(path) as image:
        image = image.convert("L").resize((size, size))
        pixels = list(image.getdata())
    average = sum(pixels) / len(pixels)
    return "".join("1" if pixel >= average else "0" for pixel in pixels)


def hamming_distance(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left, right))


def build_records(root: Path) -> list[ImageRecord]:
    records: list[ImageRecord] = []
    failures: list[str] = []
    for path in iter_images(root):
        try:
            with Image.open(path) as image:
                width, height = image.size
            records.append(
                ImageRecord(
                    path=str(path),
                    md5=compute_md5(path),
                    size_bytes=path.stat().st_size,
                    width=width,
                    height=height,
                    ahash=average_hash(path),
                )
            )
        except (UnidentifiedImageError, OSError) as exc:
            failures.append(f"{path}\t{exc}")

    if failures:
        print(f"[WARN] 跳过 {len(failures)} 张无法读取的图片")
    return records


def ensure_report_dir(root: Path, report_dir: Path | None) -> Path:
    target = report_dir or (root / AUDIT_DIRNAME)
    target.mkdir(parents=True, exist_ok=True)
    return target


def safe_name(text: str) -> str:
    text = re.sub(r"[^0-9A-Za-z._-]+", "_", text)
    text = text.strip("._")
    return text[:120] or "sample"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def audit_exact_duplicates(
    root: Path, min_count: int, report_dir: Path | None, copy_samples: bool
) -> None:
    records = build_records(root)
    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        groups[record.md5].append(record)

    duplicate_groups = [group for group in groups.values() if len(group) >= min_count]
    duplicate_groups.sort(key=lambda group: len(group), reverse=True)

    report_root = ensure_report_dir(root, report_dir)
    sample_dir = report_root / "exact_duplicate_samples"
    if copy_samples:
        sample_dir.mkdir(parents=True, exist_ok=True)

    payload = []
    md_lines = [
        "# OCR 重复图片审计报告",
        "",
        f"- 扫描根目录：`{root}`",
        f"- 图片总数：`{len(records)}`",
        f"- 重复图组数（至少 {min_count} 张）：`{len(duplicate_groups)}`",
        "",
        "## 审核建议",
        "",
        "- 先看高频组的样本图，优先处理 logo、页眉页脚、标题横幅、统一背景。",
        "- 不要直接按尺寸删图；先人工确认，再把待删路径写入 manifest 用 `purge` 删除。",
        "",
    ]

    for index, group in enumerate(duplicate_groups, start=1):
        representative = group[0]
        group_id = f"G{index:04d}"
        sample_name = safe_name(
            f"{group_id}_n{len(group)}_{Path(representative.path).name}"
        )
        sample_target = sample_dir / sample_name if copy_samples else None
        if sample_target is not None:
            shutil.copy2(representative.path, sample_target)

        payload.append(
            {
                "group_id": group_id,
                "count": len(group),
                "md5": representative.md5,
                "representative": representative.path,
                "representative_size": [representative.width, representative.height],
                "sample_copy": str(sample_target) if sample_target else None,
                "paths": [record.path for record in group],
            }
        )

        md_lines.extend(
            [
                f"### {group_id}",
                "",
                f"- 数量：`{len(group)}`",
                f"- 代表图：`{representative.path}`",
                f"- 尺寸：`{representative.width}x{representative.height}`",
                f"- MD5：`{representative.md5}`",
            ]
        )
        if sample_target is not None:
            md_lines.append(f"- 样本复制：`{sample_target}`")
        md_lines.extend(["", "路径示例：", ""])
        md_lines.extend(f"- `{record.path}`" for record in group[:10])
        if len(group) > 10:
            md_lines.append(f"- ... 共 `{len(group)}` 张")
        md_lines.append("")

    write_json(report_root / "exact_duplicate_groups.json", payload)
    (report_root / "exact_duplicate_groups.md").write_text(
        "\n".join(md_lines).rstrip() + "\n",
        encoding="utf-8",
    )
    print(f"[OK] 重复图审计完成：{report_root}")


def find_similar_images(
    root: Path,
    reference: Path,
    threshold: int,
    report_dir: Path | None,
    copy_samples: bool,
) -> None:
    records = build_records(root)
    reference = reference.resolve()
    reference_hash = average_hash(reference)
    report_root = ensure_report_dir(root, report_dir)
    sample_dir = report_root / "similar_samples"
    if copy_samples:
        sample_dir.mkdir(parents=True, exist_ok=True)

    matches = []
    for record in records:
        distance = hamming_distance(reference_hash, record.ahash)
        if distance <= threshold:
            matches.append(
                {
                    "path": record.path,
                    "distance": distance,
                    "size": [record.width, record.height],
                    "md5": record.md5,
                }
            )

    matches.sort(key=lambda item: (item["distance"], item["path"]))
    if copy_samples:
        for index, item in enumerate(matches, start=1):
            src = Path(item["path"])
            target = sample_dir / safe_name(
                f"S{index:04d}_d{item['distance']}_{src.name}"
            )
            shutil.copy2(src, target)
            item["sample_copy"] = str(target)

    md_lines = [
        "# OCR 相似图片检索报告",
        "",
        f"- 扫描根目录：`{root}`",
        f"- 参考图：`{reference}`",
        f"- 相似阈值：`{threshold}`",
        f"- 命中数量：`{len(matches)}`",
        "",
        "## 命中列表",
        "",
    ]
    for item in matches:
        md_lines.extend(
            [
                f"- 距离 `{item['distance']}` | `{item['size'][0]}x{item['size'][1]}` | `{item['path']}`",
            ]
        )

    write_json(report_root / "similar_matches.json", matches)
    (report_root / "similar_matches.md").write_text(
        "\n".join(md_lines).rstrip() + "\n",
        encoding="utf-8",
    )
    print(f"[OK] 相似图检索完成：{report_root}")


def load_manifest_paths(manifest: Path) -> list[Path]:
    if manifest.suffix.lower() == ".json":
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            paths: list[Path] = []
            for item in payload:
                if isinstance(item, str):
                    paths.append(Path(item))
                elif isinstance(item, dict) and "path" in item:
                    paths.append(Path(item["path"]))
                elif isinstance(item, dict) and "paths" in item:
                    paths.extend(Path(path) for path in item["paths"])
            return paths
        raise ValueError("JSON manifest 必须是路径列表或包含 paths/path 字段的对象列表")

    lines = manifest.read_text(encoding="utf-8").splitlines()
    return [Path(line.strip()) for line in lines if line.strip() and not line.startswith("#")]


def clean_md_references(md_path: Path, deleted_images: list[str]) -> None:
    if not deleted_images:
        return

    content = md_path.read_text(encoding="utf-8")
    original = content
    for image_name in deleted_images:
        pattern = rf"!\[.*?\]\([^)]*{re.escape(image_name)}[^)]*\)"
        content = re.sub(pattern, "", content)

    if content != original:
        md_path.write_text(content, encoding="utf-8")


def purge_manifest(root: Path, manifest: Path) -> None:
    deleted_count = 0
    freed_bytes = 0
    cleaned_md = 0

    by_folder: dict[Path, list[str]] = defaultdict(list)
    for image_path in load_manifest_paths(manifest):
        if not image_path.is_absolute():
            image_path = (root / image_path).resolve()
        if not image_path.exists() or not image_path.is_file():
            continue

        freed_bytes += image_path.stat().st_size
        by_folder[image_path.parent.parent].append(image_path.name)
        image_path.unlink()
        deleted_count += 1

    for ocr_folder, image_names in by_folder.items():
        if not ocr_folder.exists():
            continue
        for md_path in ocr_folder.glob("*.md"):
            before = md_path.read_text(encoding="utf-8")
            clean_md_references(md_path, image_names)
            after = md_path.read_text(encoding="utf-8")
            if before != after:
                cleaned_md += 1

    print(
        f"[OK] 删除 {deleted_count} 张图片，清理 {cleaned_md} 个 Markdown 文件，释放 {freed_bytes / 1024 / 1024:.2f} MB"
    )


def is_legacy_junk(filesize: int) -> bool:
    if abs(filesize - SUNFLOWER_SIZE) < 100 * 1024:
        return True
    if filesize < GEAR_MAX_SIZE:
        return True
    if filesize < SIDEBAR_MAX_SIZE:
        return True
    return False


def legacy_size_clean(root: Path) -> None:
    deleted_count = 0
    freed_bytes = 0

    for images_dir in root.rglob("images"):
        if not images_dir.is_dir():
            continue
        deleted_names: list[str] = []
        for image_path in images_dir.iterdir():
            if not image_path.is_file():
                continue
            filesize = image_path.stat().st_size
            if is_legacy_junk(filesize):
                image_path.unlink()
                deleted_names.append(image_path.name)
                deleted_count += 1
                freed_bytes += filesize

        if deleted_names:
            ocr_folder = images_dir.parent
            for md_path in ocr_folder.glob("*.md"):
                clean_md_references(md_path, deleted_names)

    print(
        f"[OK] 旧尺寸规则删除 {deleted_count} 张图片，释放 {freed_bytes / 1024 / 1024:.2f} MB"
    )


def main() -> None:
    args = parse_args()
    root = args.root.resolve()

    if not root.exists():
        raise FileNotFoundError(f"找不到目录：{root}")

    if args.command == "audit":
        audit_exact_duplicates(root, args.min_count, args.report_dir, args.copy_samples)
        return

    if args.command == "similar":
        find_similar_images(
            root,
            args.reference.resolve(),
            args.threshold,
            args.report_dir,
            args.copy_samples,
        )
        return

    if args.command == "purge":
        purge_manifest(root, args.manifest.resolve())
        return

    if args.command == "legacy-size-clean":
        legacy_size_clean(root)
        return

    raise ValueError(f"未知命令：{args.command}")


if __name__ == "__main__":
    main()
