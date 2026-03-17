from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import shutil

import ocr
from reference_book_metadata import write_directory_page


def parse_range(text: str) -> tuple[int, int]:
    raw = text.strip()
    if not raw:
        raise argparse.ArgumentTypeError("空页段")
    if "-" not in raw:
        raise argparse.ArgumentTypeError(f"页段格式错误：{text}")
    start_text, end_text = raw.split("-", 1)
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"页段格式错误：{text}") from exc
    if start <= 0 or end < start:
        raise argparse.ArgumentTypeError(f"页段范围非法：{text}")
    return start, end


def backup_existing_md(book_dir: Path, file_name: str) -> None:
    md_path = book_dir / file_name
    if not md_path.exists():
        return
    backup_root = book_dir / "_rerun_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(md_path, backup_root / file_name)


def rerun_segments(source_pdf: Path, book_dir: Path, ranges: list[tuple[int, int]], refresh_directory: bool) -> None:
    if not source_pdf.exists():
        raise SystemExit(f"源 PDF 不存在：{source_pdf}")
    if not book_dir.exists():
        raise SystemExit(f"OCR 目录不存在：{book_dir}")
    if not ocr.API_KEY:
        raise SystemExit("未读取到 GLM_API_KEY，请检查 .env")

    client = ocr.ZaiClient(api_key=ocr.API_KEY)
    images_dir = str(book_dir / "images")
    file_name = source_pdf.name

    print("=== 定向重跑失败分段 ===")
    print(f"源 PDF: {source_pdf}")
    print(f"OCR 目录: {book_dir}")
    print(f"页段: {', '.join(f'{start:04d}-{end:04d}' for start, end in ranges)}")
    print("")

    for start_page, end_page in ranges:
        md_name = f"{source_pdf.stem}_{start_page:04d}-{end_page:04d}.md"
        backup_existing_md(book_dir, md_name)

        failure_path = ocr.get_segment_failure_path(book_dir, source_pdf.stem, f"{start_page:04d}-{end_page:04d}")
        if failure_path.exists():
            failure_path.unlink()

        print(f"[rerun] {start_page:04d}-{end_page:04d}")
        ocr._process_one_segment(
            client=client,
            pdf_path=str(source_pdf),
            seg_start=start_page - 1,
            seg_end=end_page,
            book_dir=book_dir,
            images_dir=images_dir,
            file_name=file_name,
        )

    ocr.finalize_pdf_outputs(book_dir)
    if refresh_directory:
        write_directory_page(book_dir, source_file=source_pdf)
    print("")
    print("[ok] 重跑完成")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="定向重跑指定 PDF 页段的 GLM-OCR 结果")
    parser.add_argument("source_pdf", type=Path, help="原始 PDF 路径")
    parser.add_argument("book_dir", type=Path, help="目标 OCR 目录")
    parser.add_argument("ranges", nargs="+", type=parse_range, help="页段，如 0131-0140 0181-0190")
    parser.add_argument("--no-refresh-directory", action="store_true", help="完成后不刷新目录页/周边资源页")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rerun_segments(
        source_pdf=args.source_pdf,
        book_dir=args.book_dir,
        ranges=args.ranges,
        refresh_directory=not args.no_refresh_directory,
    )


if __name__ == "__main__":
    main()
