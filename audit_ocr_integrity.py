"""
OCR 完整性审计脚本
==================

比 verify_ocr.py 更严格，不只检查“有没有 md”，还会检查：
1. 页码段是否连续覆盖
2. 是否存在只写入“<!-- OCR 失败 -->”的假完成分段
3. 是否混入旧版 segment_*.md / page_*_img_* 残留
4. output/ 中是否保留了 PPT 转出的临时 PDF
5. output/ 下是否有不再对应 input/ 的孤儿目录
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from pdf_backend import get_pdf_page_count

ROOT = Path(__file__).parent
INPUT_DIR = ROOT / "input"
OUTPUT_DIR = ROOT / "output"
REPORT_DIR = ROOT / "audit_reports"
CACHE_DIR = ROOT / "_cache"
PPT_PDF_CACHE_DIR = CACHE_DIR / "ppt_pdf"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".pptx", ".ppt"}
RANGE_MD_RE = re.compile(r"_(\d{4})-(\d{4})\.md$")
OLD_IMAGE_RE = re.compile(r"page_\d+_img_\d+\.(png|jpe?g)$", re.I)
NEW_IMAGE_RE = re.compile(r"p\d{4}_fig\d{4}\.png$", re.I)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
WHITESPACE_RE = re.compile(r"\s+")
NON_GLM_AUDIT_RE = re.compile(r"OCR_AUDIT:\s*.*supplement=non_glm", re.I)


def clean_name(name: str, max_len: int = 80) -> str:
    for tag in ["(Z-Library)", "(z-library)", "(OCR)", "-- Anna's Archive", "-- Anna s Archive"]:
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


def get_pdf_pages(path: Path) -> int | None:
    try:
        return get_pdf_page_count(path)
    except Exception:
        return None


def strip_meaningful_text(text: str) -> str:
    text = HTML_COMMENT_RE.sub(" ", text)
    text = IMAGE_LINK_RE.sub(" ", text)
    text = WHITESPACE_RE.sub("", text)
    return text


def parse_range(md_path: Path) -> tuple[int, int] | None:
    m = RANGE_MD_RE.search(md_path.name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


@dataclass
class MdInfo:
    path: str
    size: int
    meaningful_chars: int
    has_failure_marker: bool
    full_failed: bool
    has_documented_non_glm_supplement: bool


@dataclass
class AuditItem:
    name: str
    source_kind: str
    input_path: str | None = None
    output_path: str | None = None
    ext: str | None = None
    total_pages: int | None = None
    range_md_count: int = 0
    segment_md_count: int = 0
    full_failed_md_count: int = 0
    partial_failed_md_count: int = 0
    low_text_md_count: int = 0
    extra_pdf_count: int = 0
    old_image_count: int = 0
    new_image_count: int = 0
    total_image_count: int = 0
    failed_segment_report_count: int = 0
    documented_non_glm_md_count: int = 0
    covered_pages: int | None = None
    missing_pages: list[int] = field(default_factory=list)
    status: str = "unknown"
    reasons: list[str] = field(default_factory=list)
    md_samples: list[MdInfo] = field(default_factory=list)


def analyze_md(md_path: Path) -> MdInfo:
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    meaningful = strip_meaningful_text(text)
    has_failure = ("OCR 失败" in text) or ("OCR 页失败" in text)
    full_failed = ("OCR 失败" in text) and not meaningful
    has_documented_non_glm = bool(NON_GLM_AUDIT_RE.search(text))
    return MdInfo(
        path=str(md_path),
        size=md_path.stat().st_size,
        meaningful_chars=len(meaningful),
        has_failure_marker=has_failure,
        full_failed=full_failed,
        has_documented_non_glm_supplement=has_documented_non_glm,
    )


def detect_total_pages(input_file: Path | None, output_dir: Path) -> int | None:
    if input_file is None:
        return None

    ext = input_file.suffix.lower()
    if ext == ".pdf":
        return get_pdf_pages(input_file)
    if ext in {".ppt", ".pptx"}:
        cleaned = clean_name(input_file.stem)
        converted = PPT_PDF_CACHE_DIR / cleaned / f"{cleaned}.pdf"
        if not converted.exists():
            converted = output_dir / f"{input_file.stem}.pdf"
        if converted.exists():
            return get_pdf_pages(converted)
    return None


def collect_coverage(range_mds: list[Path], total_pages: int | None) -> tuple[int | None, list[int]]:
    if total_pages is None:
        return None, []

    covered: set[int] = set()
    for md in range_mds:
        parsed = parse_range(md)
        if not parsed:
            continue
        start, end = parsed
        covered.update(range(start, end + 1))

    missing = [p for p in range(1, total_pages + 1) if p not in covered]
    return len(covered), missing


def classify_item(item: AuditItem, output_only: bool = False) -> None:
    if item.output_path is None:
        item.status = "missing_output"
        item.reasons.append("缺少输出目录")
        return

    if item.range_md_count == 0 and item.segment_md_count == 0:
        item.status = "missing_md"
        item.reasons.append("输出目录里没有 md")
        return

    if item.full_failed_md_count > 0:
        item.status = "failed_md_present"
        item.reasons.append(f"存在 {item.full_failed_md_count} 个只写入失败占位的 md")

    if item.failed_segment_report_count > 0:
        item.status = "failed_segment_report"
        item.reasons.append(f"存在 {item.failed_segment_report_count} 个失败分段报告")

    if item.partial_failed_md_count > 0 and item.status == "unknown":
        item.status = "partial_failed_md_present"
        item.reasons.append(f"存在 {item.partial_failed_md_count} 个含页级失败标记的 md")

    if item.total_pages is not None and item.range_md_count == 0:
        item.status = "no_ranged_md"
        item.reasons.append("已知是分页文档，但没有规范页码段 md")

    if item.total_pages is not None and item.missing_pages:
        item.status = "coverage_gap"
        item.reasons.append(f"缺少 {len(item.missing_pages)} 页覆盖")

    if output_only and item.range_md_count <= 1 and item.segment_md_count >= 1 and item.old_image_count >= 100:
        item.status = "legacy_partial_output"
        item.reasons.append("像是旧版管线留下的残缺输出：旧 segment 很少，旧式整页图片很多")

    if item.status == "unknown" and item.segment_md_count > 0:
        item.status = "legacy_mixed_output"
        item.reasons.append("目录里混有旧版 segment 输出")

    if item.documented_non_glm_md_count > 0:
        item.reasons.append(f"存在 {item.documented_non_glm_md_count} 个已登记的非 GLM 补页")

    if item.status == "unknown" and item.documented_non_glm_md_count > 0:
        item.status = "complete_with_documented_non_glm_pages"

    if item.status == "unknown" and item.extra_pdf_count > 0:
        item.status = "complete_with_temp_pdf"
        item.reasons.append("内容看起来完整，但 output 中保留了 PPT 转 PDF 临时件")

    if item.status == "unknown":
        item.status = "complete"


def analyze_output_dir(name: str, output_dir: Path, input_file: Path | None, output_only: bool) -> AuditItem:
    item = AuditItem(
        name=name,
        source_kind="output_only" if output_only else "input",
        input_path=str(input_file) if input_file else None,
        output_path=str(output_dir) if output_dir.exists() else None,
        ext=input_file.suffix.lower() if input_file else None,
    )

    if not output_dir.exists():
        classify_item(item, output_only=output_only)
        return item

    md_files = sorted(output_dir.glob("*.md"))
    range_mds = [p for p in md_files if parse_range(p)]
    segment_mds = [p for p in md_files if p.name.startswith("segment_")]
    pdf_files = list(output_dir.glob("*.pdf"))
    failed_segment_reports = list((output_dir / "_failed_segments").glob("*.failed.json")) if (output_dir / "_failed_segments").exists() else []

    images_dir = output_dir / "images"
    image_files = list(images_dir.glob("*")) if images_dir.exists() else []
    old_images = [p for p in image_files if OLD_IMAGE_RE.match(p.name)]
    new_images = [p for p in image_files if NEW_IMAGE_RE.match(p.name)]

    md_infos = [analyze_md(md) for md in md_files]

    item.total_pages = detect_total_pages(input_file, output_dir)
    item.range_md_count = len(range_mds)
    item.segment_md_count = len(segment_mds)
    item.full_failed_md_count = sum(1 for info in md_infos if info.full_failed)
    item.partial_failed_md_count = sum(
        1 for info in md_infos
        if info.has_failure_marker and not info.full_failed
    )
    item.low_text_md_count = sum(1 for info in md_infos if info.meaningful_chars < 30)
    item.extra_pdf_count = len(pdf_files)
    item.old_image_count = len(old_images)
    item.new_image_count = len(new_images)
    item.total_image_count = len(image_files)
    item.failed_segment_report_count = len(failed_segment_reports)
    item.documented_non_glm_md_count = sum(
        1 for info in md_infos if info.has_documented_non_glm_supplement
    )
    item.md_samples = md_infos[:10]
    item.covered_pages, item.missing_pages = collect_coverage(range_mds, item.total_pages)

    classify_item(item, output_only=output_only)
    return item


def build_report() -> dict:
    inputs = {
        clean_name(f.stem): f
        for f in sorted(INPUT_DIR.iterdir())
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    }

    output_dirs = {p.name: p for p in OUTPUT_DIR.iterdir() if p.is_dir()}

    items: list[AuditItem] = []
    for name, input_file in inputs.items():
        items.append(analyze_output_dir(name, OUTPUT_DIR / name, input_file, output_only=False))

    for name, output_dir in output_dirs.items():
        if name not in inputs:
            items.append(analyze_output_dir(name, output_dir, None, output_only=True))

    status_counts: dict[str, int] = {}
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1

    high_risk_status = {
        "missing_output",
        "missing_md",
        "failed_md_present",
        "failed_segment_report",
        "partial_failed_md_present",
        "coverage_gap",
        "no_ranged_md",
        "legacy_partial_output",
    }
    high_risk = [item for item in items if item.status in high_risk_status]

    return {
        "summary": {
            "input_count": len(inputs),
            "output_dir_count": len(output_dirs),
            "audit_item_count": len(items),
            "status_counts": status_counts,
            "high_risk_count": len(high_risk),
        },
        "items": [asdict(item) for item in items],
    }


def render_console(report: dict) -> str:
    summary = report["summary"]
    items = report["items"]

    lines = []
    lines.append("=== OCR 完整性审计报告 ===")
    lines.append(f"input 文件数: {summary['input_count']}")
    lines.append(f"output 目录数: {summary['output_dir_count']}")
    lines.append(f"审计对象数: {summary['audit_item_count']}")
    lines.append(f"高风险对象: {summary['high_risk_count']}")
    lines.append("")
    lines.append("状态统计:")
    for status, count in sorted(summary["status_counts"].items()):
        lines.append(f"  - {status}: {count}")

    lines.append("")
    lines.append("高风险清单:")
    high_risk_status = {
        "missing_output",
        "missing_md",
        "failed_md_present",
        "failed_segment_report",
        "partial_failed_md_present",
        "coverage_gap",
        "no_ranged_md",
        "legacy_partial_output",
    }
    high_risk_items = [item for item in items if item["status"] in high_risk_status]
    if not high_risk_items:
        lines.append("  (无)")
    else:
        for item in sorted(high_risk_items, key=lambda x: (x["status"], x["name"])):
            lines.append(
                f"  - [{item['status']}] {item['name']} | "
                f"range={item['range_md_count']} segment={item['segment_md_count']} "
                f"failed={item['full_failed_md_count']} old_img={item['old_image_count']} "
                f"reasons={'; '.join(item['reasons'])}"
            )

    lines.append("")
    lines.append("已登记的非 GLM 补页:")
    documented_items = [
        item for item in items if item.get("documented_non_glm_md_count", 0) > 0
    ]
    if not documented_items:
        lines.append("  (无)")
    else:
        for item in sorted(documented_items, key=lambda x: x["name"]):
            lines.append(
                f"  - {item['name']}: {item['documented_non_glm_md_count']} 个 | "
                f"status={item['status']} | reasons={'; '.join(item['reasons'])}"
            )

    return "\n".join(lines)


def save_report(report: dict) -> tuple[Path, Path]:
    REPORT_DIR.mkdir(exist_ok=True)
    json_path = REPORT_DIR / "ocr_integrity_report.json"
    md_path = REPORT_DIR / "ocr_integrity_report.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md_path.write_text(render_console(report), encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="审计 GLM-OCR 输出的真实性和完整性")
    parser.add_argument("--save", action="store_true", help="将报告保存到 audit_reports/")
    args = parser.parse_args()

    if not INPUT_DIR.exists() or not OUTPUT_DIR.exists():
        print("[!] 缺少 input/ 或 output/ 目录")
        sys.exit(1)

    report = build_report()
    text = render_console(report)
    print(text)

    if args.save:
        json_path, md_path = save_report(report)
        print("")
        print(f"[ok] 已保存 JSON 报告: {json_path}")
        print(f"[ok] 已保存 Markdown 报告: {md_path}")


if __name__ == "__main__":
    main()
