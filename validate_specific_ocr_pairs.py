from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
AUDIT_MODULE_PATH = SCRIPT_DIR / "audit_ocr_integrity.py"


def load_audit_module():
    spec = importlib.util.spec_from_file_location("audit_mod", AUDIT_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="用 GLM-OCR 现有审计逻辑验证指定原件/OCR 目录对。")
    parser.add_argument("--report-json", required=True, help="输出 JSON 报告路径。")
    parser.add_argument("--report-md", required=True, help="输出 Markdown 报告路径。")
    parser.add_argument(
        "--pair",
        action="append",
        nargs=3,
        metavar=("NAME", "INPUT_FILE", "OUTPUT_DIR"),
        required=True,
        help="一组 name / input_file / output_dir，可重复传入。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit_mod = load_audit_module()

    items = []
    for name, input_file, output_dir in args.pair:
        item = audit_mod.analyze_output_dir(
            name=name,
            output_dir=Path(output_dir),
            input_file=Path(input_file),
            output_only=False,
        )
        items.append(item)

    status_counts: dict[str, int] = {}
    for item in items:
        status_counts[item.status] = status_counts.get(item.status, 0) + 1

    report = {
        "summary": {
            "audit_item_count": len(items),
            "status_counts": status_counts,
        },
        "items": [audit_mod.asdict(item) for item in items],
    }

    report_json = Path(args.report_json)
    report_md = Path(args.report_md)
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Specific OCR Validation",
        "",
        f"- checked_items: `{len(items)}`",
        "",
        "## Status Counts",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")
    lines.append("")

    for item in items:
        lines.extend(
            [
                f"## {item.name}",
                "",
                f"- status: `{item.status}`",
                f"- input_path: `{item.input_path}`",
                f"- output_path: `{item.output_path}`",
                f"- total_pages: `{item.total_pages}`",
                f"- range_md_count: `{item.range_md_count}`",
                f"- segment_md_count: `{item.segment_md_count}`",
                f"- full_failed_md_count: `{item.full_failed_md_count}`",
                f"- partial_failed_md_count: `{item.partial_failed_md_count}`",
                f"- failed_segment_report_count: `{item.failed_segment_report_count}`",
                f"- documented_non_glm_md_count: `{item.documented_non_glm_md_count}`",
                f"- old_image_count: `{item.old_image_count}`",
                f"- new_image_count: `{item.new_image_count}`",
                f"- total_image_count: `{item.total_image_count}`",
                f"- covered_pages: `{item.covered_pages}`",
                f"- missing_pages_count: `{len(item.missing_pages)}`",
                f"- reasons: `{'; '.join(item.reasons) if item.reasons else 'none'}`",
                "",
            ]
        )

    report_md.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {report_json}")
    print(f"wrote {report_md}")


if __name__ == "__main__":
    main()
