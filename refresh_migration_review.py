from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_PATH = SCRIPT_DIR / "academic_library_migration.py"


def load_module():
    spec = importlib.util.spec_from_file_location("alm", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="刷新学术资料迁移的终版复核文件。")
    parser.add_argument("--batch-name", required=True, help="待确认删除批次名。")
    parser.add_argument("--report-dir", required=True, help="要写入的报告目录。")
    parser.add_argument("--moved-originals", type=int, required=True)
    parser.add_argument("--moved-middle", type=int, required=True)
    parser.add_argument("--duplicates", type=int, required=True)
    parser.add_argument("--archives", type=int, required=True)
    parser.add_argument("--quarantine", type=int, required=True)
    parser.add_argument("--remaining-conflicts", type=int, required=True)
    parser.add_argument("--remaining-unclassified", type=int, required=True)
    parser.add_argument("--desktop-files", type=int, required=True)
    parser.add_argument("--desktop-dirs", type=int, required=True)
    parser.add_argument("--desktop-size-gb", required=True)
    parser.add_argument("--physical-files", type=int, required=True)
    parser.add_argument("--physical-dirs", type=int, required=True)
    parser.add_argument("--physical-size-gb", required=True)
    parser.add_argument("--glm-input-files", type=int, required=True)
    parser.add_argument("--glm-input-dirs", type=int, required=True)
    parser.add_argument("--glm-input-size-gb", required=True)
    parser.add_argument("--glm-output-files", type=int, required=True)
    parser.add_argument("--glm-output-dirs", type=int, required=True)
    parser.add_argument("--glm-output-size-gb", required=True)
    parser.add_argument("--postfinal-report-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mod = load_module()

    batch_root = Path(r"F:\待确认删除") / args.batch_name
    report_dir = Path(args.report_dir)
    postfinal_dir = Path(args.postfinal_report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    rows = mod.ReportRows()
    mod.build_discrete_math_audit(rows, batch_root)
    mod.build_plan101_audit(rows, batch_root)
    mod.write_csv(report_dir / "discrete_math_sync_final.csv", rows.discrete_math, False)
    mod.write_csv(report_dir / "plan101_sync_final.csv", rows.plan101, False)

    final_review = f"""# Final Review

- generated_at: {mod.now_str()}
- batch: `{args.batch_name}`

## cumulative summary
- moved originals: `{args.moved_originals}`
- moved OCR directories: `{args.moved_middle}`
- duplicate candidates moved to quarantine: `{args.duplicates}`
- archive review items: `{args.archives}`
- quarantine entries total: `{args.quarantine}`
- remaining conflicts after incremental fix: `{args.remaining_conflicts}`
- remaining unclassified items: `{args.remaining_unclassified}`

## quarantine sections
- Desktop: `{args.desktop_files}` files, `{args.desktop_dirs}` dirs, `{args.desktop_size_gb} GB`
- 实体桌面: `{args.physical_files}` files, `{args.physical_dirs}` dirs, `{args.physical_size_gb} GB`
- GLM-OCR_input: `{args.glm_input_files}` files, `{args.glm_input_dirs}` dirs, `{args.glm_input_size_gb} GB`
- GLM-OCR_output: `{args.glm_output_files}` files, `{args.glm_output_dirs}` dirs, `{args.glm_output_size_gb} GB`

## review focus
- remaining conflicts are all historical OCR directory conflicts in `GLM-OCR/output`
- the only unclassified item is the test OCR directory `测试_图论与代数结构_中间50页`
- `101` experiment-pack source conflicts were resolved by preserving relative paths inside the target bucket
- the pending-delete batch keeps original relative paths under `Desktop/`, `实体桌面/`, `GLM-OCR_input/`, `GLM-OCR_output/`

## report files
- `remaining_conflicts.csv`
- `remaining_unclassified.csv`
- `discrete_math_sync_final.csv`
- `plan101_sync_final.csv`
"""
    (report_dir / "final_review.md").write_text(final_review, encoding="utf-8")
    (report_dir / "remaining_conflicts.csv").write_bytes((postfinal_dir / "version_conflicts.csv").read_bytes())
    (report_dir / "remaining_unclassified.csv").write_bytes((postfinal_dir / "unclassified_items.csv").read_bytes())
    print("ok")


if __name__ == "__main__":
    main()
