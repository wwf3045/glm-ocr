from __future__ import annotations

import argparse
from pathlib import Path

from markdown_cleanup import repair_markdown_file, write_math_audit_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-fix OCR Markdown math delimiters like `$ x $` -> `$x$`."
    )
    parser.add_argument(
        "root",
        type=Path,
        help="Root directory to scan recursively for Markdown files.",
    )
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="只生成数学命令审计报告，不执行修复。",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="审计报告输出路径。默认写到 root/_math_command_audit.md",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"找不到目录：{root}")

    scanned = 0
    changed = 0
    if not args.audit_only:
        for path in root.rglob("*.md"):
            scanned += 1
            if repair_markdown_file(path):
                changed += 1
        print(f"[OK] 扫描 {scanned} 个 Markdown 文件，修复 {changed} 个文件")

    if args.audit_only or args.report:
        audit = write_math_audit_report(root, args.report)
        print(
            "[AUDIT] "
            f"扫描 {audit['scanned_files']} 个 Markdown，"
            f"命中文件 {audit['files_with_findings']} 个，"
            f"可疑项 {audit['total_findings']} 个 -> {audit['report_path']}"
        )


if __name__ == "__main__":
    main()
