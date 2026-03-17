from __future__ import annotations

import csv
import importlib.util
import sys
import argparse
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPT_DIR / "academic_library_migration.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对剩余 OCR 冲突目录做精确差异对比。")
    parser.add_argument("--conflict-csv", required=True, help="冲突 CSV 路径。")
    parser.add_argument("--output-csv", required=True, help="输出明细 CSV 路径。")
    parser.add_argument("--output-md", required=True, help="输出明细 Markdown 路径。")
    return parser.parse_args()


def load_module():
    spec = importlib.util.spec_from_file_location("alm", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    args = parse_args()
    mod = load_module()
    rows: list[dict[str, str]] = []

    conflict_csv = Path(args.conflict_csv)
    output_csv = Path(args.output_csv)
    output_md = Path(args.output_md)

    with conflict_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for item in reader:
            src = Path(item["source_path"])
            dst = Path(item["target_path"])
            src_meta, src_fp = mod.directory_fingerprint(src)
            dst_meta, dst_fp = mod.directory_fingerprint(dst)

            src_files = {str(e["path"]): str(e["sha256"]) for e in src_meta["entries"]}
            dst_files = {str(e["path"]): str(e["sha256"]) for e in dst_meta["entries"]}
            only_src = sorted(set(src_files) - set(dst_files))
            only_dst = sorted(set(dst_files) - set(src_files))
            diff_common = sorted(p for p in (set(src_files) & set(dst_files)) if src_files[p] != dst_files[p])

            rows.append(
                {
                    "name": src.name,
                    "source_path": str(src),
                    "target_path": str(dst),
                    "source_files": str(src_meta["files"]),
                    "target_files": str(dst_meta["files"]),
                    "source_size_bytes": str(src_meta["size_bytes"]),
                    "target_size_bytes": str(dst_meta["size_bytes"]),
                    "source_md_files": str(src_meta["md_files"]),
                    "target_md_files": str(dst_meta["md_files"]),
                    "source_image_files": str(src_meta["image_files"]),
                    "target_image_files": str(dst_meta["image_files"]),
                    "source_failed_segments": str(src_meta["has_failed_segments"]),
                    "target_failed_segments": str(dst_meta["has_failed_segments"]),
                    "source_fingerprint": src_fp,
                    "target_fingerprint": dst_fp,
                    "only_source_count": str(len(only_src)),
                    "only_target_count": str(len(only_dst)),
                    "different_common_count": str(len(diff_common)),
                    "only_source_examples": " | ".join(only_src[:10]),
                    "only_target_examples": " | ".join(only_dst[:10]),
                    "different_common_examples": " | ".join(diff_common[:10]),
                }
            )

    with output_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Remaining OCR Conflict Details",
        "",
    ]
    for row in rows:
        lines.extend(
            [
                f"## {row['name']}",
                "",
                f"- source_files: `{row['source_files']}`",
                f"- target_files: `{row['target_files']}`",
                f"- source_size_bytes: `{row['source_size_bytes']}`",
                f"- target_size_bytes: `{row['target_size_bytes']}`",
                f"- source_md_files: `{row['source_md_files']}`",
                f"- target_md_files: `{row['target_md_files']}`",
                f"- source_image_files: `{row['source_image_files']}`",
                f"- target_image_files: `{row['target_image_files']}`",
                f"- only_source_count: `{row['only_source_count']}`",
                f"- only_target_count: `{row['only_target_count']}`",
                f"- different_common_count: `{row['different_common_count']}`",
                "",
                f"- only_source_examples: `{row['only_source_examples'] or '-'}'",
                f"- only_target_examples: `{row['only_target_examples'] or '-'}'",
                f"- different_common_examples: `{row['different_common_examples'] or '-'}'",
                "",
            ]
        )

    output_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {output_csv}")
    print(f"wrote {output_md}")


if __name__ == "__main__":
    main()
