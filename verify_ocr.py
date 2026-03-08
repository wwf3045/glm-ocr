"""
OCR 验收脚本
=============
检查 input/ 中每个文件在 output/ 中是否有完整的 OCR 结果。

检查项：
1. output/ 下有对应目录
2. 目录下有 .md 文件
3. PDF/PPT 的 .md 分段覆盖到最后一页
4. .md 文件内容非空（>100 字节）
"""

import os
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    import fitz  # PyMuPDF
except ImportError:
    print("[!] 需要安装 PyMuPDF: pip install PyMuPDF")
    sys.exit(1)

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".pptx", ".ppt"}
MIN_MD_SIZE = 100  # 字节，低于此视为空文件


def clean_name(name: str, max_len: int = 80) -> str:
    for tag in ["(Z-Library)", "(z-library)", "(OCR)",
                "-- Anna's Archive", "-- Anna s Archive"]:
        name = name.replace(tag, "")
    name = re.sub(r"[0-9a-f]{16,}", "", name)
    name = re.sub(r"97[89]\d{10}", "", name)
    name = re.sub(r"\s*--\s*--\s*", " -- ", name)
    name = re.sub(r"(\s*--\s*)+$", "", name)
    name = re.sub(r"\s{2,}", " ", name)
    name = name.strip(" -_.")
    if len(name) > max_len:
        name = name[:max_len].rstrip(". ")
    return name


def get_max_page_from_mds(md_files):
    """从 .md 文件名中提取最大页码"""
    max_page = 0
    for md in md_files:
        m = re.search(r"_(\d{4})-(\d{4})\.md$", md.name)
        if m:
            max_page = max(max_page, int(m.group(2)))
    return max_page


def get_pdf_pages(path):
    """获取 PDF 总页数"""
    try:
        doc = fitz.open(str(path))
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0


def verify():
    if not INPUT_DIR.exists():
        print(f"[!] input/ 目录不存在: {INPUT_DIR}")
        return
    if not OUTPUT_DIR.exists():
        print(f"[!] output/ 目录不存在: {OUTPUT_DIR}")
        return

    files = sorted(
        f for f in INPUT_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not files:
        print("[!] input/ 目录为空")
        return

    total_ok = 0
    total_partial = 0
    total_missing = 0
    total_empty = 0
    issues = []

    for f in files:
        ext = f.suffix.lower()
        cleaned = clean_name(f.stem)
        book_dir = OUTPUT_DIR / cleaned

        # 检查 1：目录存在性
        if not book_dir.exists():
            issues.append(f"[NO DIR] {f.name}")
            total_missing += 1
            continue

        # 检查 2：md 文件存在
        md_files = sorted(book_dir.glob("*.md"))
        img_dir = book_dir / "images"
        img_count = len(list(img_dir.glob("*"))) if img_dir.exists() else 0

        if not md_files:
            issues.append(f"[NO MD] {f.name}")
            total_missing += 1
            continue

        # 检查 4：内容非空
        empty_mds = [md for md in md_files if md.stat().st_size < MIN_MD_SIZE]
        if empty_mds:
            total_empty += len(empty_mds)
            for md in empty_mds:
                issues.append(
                    f"[EMPTY] {f.name} -> {md.name} ({md.stat().st_size}B)"
                )

        # 检查 3：页码完整性（PDF / PPT）
        if ext == ".pdf":
            total_pages = get_pdf_pages(f)
            max_page = get_max_page_from_mds(md_files)
            if total_pages > 0 and max_page > 0 and max_page < total_pages:
                issues.append(
                    f"[PARTIAL] {f.name}: {len(md_files)} md, "
                    f"page {max_page}/{total_pages}, {img_count} img"
                )
                total_partial += 1
                continue
        elif ext in (".ppt", ".pptx"):
            pdf_path = book_dir / f"{f.stem}.pdf"
            if pdf_path.exists():
                total_pages = get_pdf_pages(pdf_path)
                max_page = get_max_page_from_mds(md_files)
                if total_pages > 0 and max_page > 0 and max_page < total_pages:
                    issues.append(
                        f"[PARTIAL] {f.name}: {len(md_files)} md, "
                        f"page {max_page}/{total_pages}, {img_count} img"
                    )
                    total_partial += 1
                    continue

        total_ok += 1

    # 输出报告
    total = total_ok + total_partial + total_missing
    print(f"=== OCR 验收报告 ===")
    print(f"总文件数: {total}")
    print(f"完全完成: {total_ok}")
    print(f"部分完成: {total_partial}")
    print(f"缺失/无输出: {total_missing}")
    print(f"空 md 文件(<{MIN_MD_SIZE}B): {total_empty}")
    print()

    if issues:
        print(f"=== 问题文件 ({len(issues)}) ===")
        for i in issues:
            print(f"  {i}")
    else:
        print("所有文件均已完整 OCR!")


if __name__ == "__main__":
    verify()
