from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from middle_library_image_maintenance import cleanup_book_dir


SCRIPT_DIR = Path(__file__).resolve().parent
DESKTOP_ROOT = Path(r"C:\Users\28033\Desktop")
PHYSICAL_DESKTOP_ROOT = Path(r"F:\实体桌面")
GLM_INPUT_ROOT = SCRIPT_DIR / "input"
GLM_OUTPUT_ROOT = SCRIPT_DIR / "output"
ORIGINAL_LIBRARY_ROOT = Path(r"F:\资料库")
MIDDLE_LIBRARY_ROOT = Path(r"F:\中间文件库")
REPORT_ROOT = SCRIPT_DIR / "audit_reports"

DEFAULT_BATCH_NAME = f"{datetime.now():%Y%m%d}_library_migration"
CHUNK_SIZE = 1024 * 1024
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z"}


DESKTOP_COURSE_ROOTS = {
    "人工智能基础": "人工智能基础",
    "信号与系统": "信号与系统",
    "凸优化": "线性优化与凸优化",
    "大学物理1": "大学物理1",
    "大学物理2": "大学物理2",
    "操作系统": "操作系统",
    "数据挖掘": "数据挖掘",
    "数理逻辑入门": "数理逻辑入门",
    "机器学习": "机器学习",
    "自然语言处理": "自然语言处理",
    "计算机“101计划”核心教材": "__101_textbooks__",
    "计算机“101计划”核心教材配套课件ppt": "__101_ppts__",
}

PHYSICAL_DESKTOP_ROOTS = {
    "1.考研": "考研",
    "2.数学": "数学",
    "3.计算机科学与技术": "计算机科学与技术",
    "4.人工智能": "人工智能",
    "5.集成电路": "集成电路",
    "6.电气工程与自动化": "电气工程与自动化",
    "Calibre书库": "Calibre书库",
    "大学英语": "大学英语",
    "高中": "高中",
}

SUBJECT_KEYWORDS = {
    "人工智能基础": ("人工智能引论", "人工智能基础", "吴飞", "潘云鹤"),
    "操作系统": ("操作系统", "ostep", "现代操作系统"),
    "数据库管理系统": ("数据库管理系统", "数据库系统"),
    "数据结构": ("数据结构",),
    "离散数学": ("离散数学",),
    "编译原理": ("编译原理",),
    "计算机科学导论": ("计算机科学导论", "计算+、互联网+与人工智能+", "人才培养战略研究报告"),
    "计算机系统": ("计算机系统", "risc-v", "linux平台"),
    "计算机组成与实现": ("计算机组成与实现",),
    "计算机网络": ("计算机网络",),
    "软件工程": ("软件工程",),
    "信号与系统": ("信号与系统",),
    "线性优化与凸优化": ("凸优化", "线性优化与凸优化"),
    "数理逻辑入门": ("数理逻辑", "逻辑"),
    "数据挖掘": ("数据挖掘",),
    "机器学习": ("机器学习",),
    "自然语言处理": ("自然语言处理", "nlp"),
    "大学物理1": ("大学物理1",),
    "大学物理2": ("大学物理2",),
}

FILE_BUCKET_HINTS = {
    "课件": ("课件", "slides", "lecture", "lec", "ppt", "pptx"),
    "教材及参考书": ("教材", "参考书", "book", "textbook", "z-library"),
    "作业答案与复习资料": ("作业", "答案", "solution", "solutions", "习题", "题解", "review", "hw", "assignment"),
    "实验": ("实验", "lab"),
    "课程信息": ("教学大纲", "syllabus", "说明"),
}

OCR_BUCKET_MAP = {
    "课件": "课件OCR扫描",
    "教材及参考书": "教材OCR扫描",
    "作业答案与复习资料": "作业答案OCR扫描",
    "实验": "实验OCR扫描",
    "课程信息": "课程信息OCR扫描",
    "补充资料": "补充资料OCR扫描",
    "课程资料": "课程资料OCR扫描",
}


@dataclass
class ReportRows:
    duplicates: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    archives: list[dict[str, str]] = field(default_factory=list)
    quarantine: list[dict[str, str]] = field(default_factory=list)
    unclassified: list[dict[str, str]] = field(default_factory=list)
    moved_originals: list[dict[str, str]] = field(default_factory=list)
    moved_middle: list[dict[str, str]] = field(default_factory=list)
    discrete_math: list[dict[str, str]] = field(default_factory=list)
    plan101: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class SourceSpec:
    key: str
    root: Path
    kind: str
    library_mode: str
    quarantine_prefix: str = ""
    logical_root: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把桌面 / 实体桌面 / GLM-OCR 的学术资料归并到 F 盘资料库，并把旧副本移入待确认删除区。"
    )
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME, help="待确认删除与报告批次名。")
    parser.add_argument("--dry-run", action="store_true", help="仅生成报告，不执行复制和移动。")
    return parser.parse_args()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(path: Path, dry_run: bool) -> None:
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def normalize_name(name: str) -> str:
    text = name.lower().replace("（", "(").replace("）", ")")
    text = re.sub(r"\(\d+\)$", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_stem_for_collision(stem: str) -> str:
    text = re.sub(r"\(\d+\)$", "", stem)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def describe_file(path: Path) -> tuple[int, str]:
    stat = path.stat()
    return stat.st_size, datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")


def canonical_file_name(path: Path) -> str:
    return f"{normalize_stem_for_collision(path.stem)}{path.suffix}"


def subject_for_name(name: str, fallback: str | None = None) -> str | None:
    lower_name = name.lower()
    for subject, keywords in SUBJECT_KEYWORDS.items():
        if any(keyword.lower() in lower_name for keyword in keywords):
            return subject
    return fallback


def subject_for_relative_context(spec: SourceSpec, file_path: Path) -> str | None:
    relative = file_path.relative_to(spec.root)
    candidates = [file_path.stem]
    candidates.extend(part for part in reversed(relative.parts[:-1]) if part)
    for candidate in candidates:
        subject = subject_for_name(candidate)
        if subject:
            return subject
    return None


def classify_original_bucket(subject: str, name: str) -> str:
    lower_name = name.lower()
    for bucket, keywords in FILE_BUCKET_HINTS.items():
        if any(keyword in lower_name for keyword in keywords):
            return bucket
    if subject in {"信号与系统", "操作系统", "数据库管理系统", "数据结构", "编译原理", "计算机系统", "计算机组成与实现", "计算机网络"}:
        if lower_name.endswith((".ppt", ".pptx")):
            return "课件"
        if lower_name.endswith(".pdf"):
            return "教材及参考书"
    if lower_name.endswith((".ppt", ".pptx")):
        return "课件"
    if lower_name.endswith(".pdf"):
        return "补充资料"
    return "课程资料"


def classify_ocr_bucket(subject: str, name: str) -> str:
    return OCR_BUCKET_MAP[classify_original_bucket(subject, name)]


def file_target_for_spec(spec: SourceSpec, file_path: Path) -> tuple[Path | None, str | None, str | None]:
    if spec.kind == "glm_input":
        subject = subject_for_name(file_path.stem)
        if not subject:
            return None, None, None
        bucket = classify_original_bucket(subject, file_path.name)
        return ORIGINAL_LIBRARY_ROOT / subject / bucket / canonical_file_name(file_path), subject, bucket

    if spec.kind in {"desktop_101_textbooks", "desktop_101_ppts"}:
        subject = subject_for_relative_context(spec, file_path)
        if not subject:
            return None, None, None
        bucket = classify_original_bucket(subject, file_path.name)
        relative = file_path.relative_to(spec.root)
        tail = relative.parent / canonical_file_name(file_path) if relative.parent != Path(".") else Path(canonical_file_name(file_path))
        return ORIGINAL_LIBRARY_ROOT / subject / bucket / tail, subject, bucket

    if spec.kind in {"desktop_course", "physical_subject"}:
        subject = spec.logical_root
        if not subject:
            return None, None, None
        relative = file_path.relative_to(spec.root)
        return ORIGINAL_LIBRARY_ROOT / subject / relative, subject, ""

    return None, None, None


def output_target_for_dir(dir_path: Path) -> tuple[Path | None, str | None, str | None]:
    subject = subject_for_name(dir_path.name)
    if not subject:
        return None, None, None
    bucket = classify_ocr_bucket(subject, dir_path.name)
    return MIDDLE_LIBRARY_ROOT / subject / bucket / dir_path.name, subject, bucket


def walk_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: str(item).lower()):
        if path.is_file():
            yield path


def safe_copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    ensure_dir(dst.parent, dry_run)
    if not dry_run:
        shutil.copy2(src, dst)


def safe_copy_tree(src: Path, dst: Path, dry_run: bool) -> None:
    ensure_dir(dst.parent, dry_run)
    if dry_run:
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def safe_move(src: Path, dst: Path, dry_run: bool) -> None:
    ensure_dir(dst.parent, dry_run)
    if dry_run:
        return
    if dst.exists():
        raise FileExistsError(f"待确认删除目标已存在：{dst}")
    shutil.move(str(src), str(dst))


def remove_empty_dirs(root: Path, dry_run: bool) -> None:
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            if not any(path.iterdir()) and not dry_run:
                path.rmdir()
        except OSError:
            continue


def write_csv(path: Path, rows: list[dict[str, str]], dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) or ["note"]
    if not rows:
        rows = [{"note": "empty"}]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object], dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, content: str, dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def directory_fingerprint(path: Path) -> tuple[dict[str, object], str]:
    entries: list[dict[str, str | int]] = []
    total_size = 0
    md_count = 0
    image_count = 0
    failed_segment = False
    digest = hashlib.sha256()
    for file_path in sorted((p for p in path.rglob("*") if p.is_file()), key=lambda item: str(item.relative_to(path)).lower()):
        rel = file_path.relative_to(path).as_posix()
        size = file_path.stat().st_size
        total_size += size
        if file_path.suffix.lower() == ".md":
            md_count += 1
        if file_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            image_count += 1
        if file_path.name.endswith(".failed.json"):
            failed_segment = True
        file_hash = sha256_file(file_path)
        digest.update(rel.encode("utf-8"))
        digest.update(str(size).encode("utf-8"))
        digest.update(file_hash.encode("ascii"))
        entries.append({"path": rel, "size": size, "sha256": file_hash})
    meta = {
        "files": len(entries),
        "size_bytes": total_size,
        "md_files": md_count,
        "image_files": image_count,
        "has_failed_segments": failed_segment,
        "entries": entries,
    }
    return meta, digest.hexdigest()


def quarantine_destination(batch_root: Path, spec: SourceSpec, source_path: Path) -> Path:
    return batch_root / spec.quarantine_prefix / source_path.relative_to(spec.root)


def infer_extracted_dir(archive_path: Path) -> Path | None:
    candidate = archive_path.with_suffix("")
    if candidate.exists() and candidate.is_dir():
        return candidate
    return None


def validate_zip_coverage(archive_path: Path, extracted_dir: Path) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(archive_path) as zf:
            files = [info for info in zf.infolist() if not info.is_dir()]
    except zipfile.BadZipFile:
        return False, "bad_zip"

    for info in files:
        rel = Path(info.filename)
        target = extracted_dir / rel
        if not target.exists() or not target.is_file():
            return False, f"missing:{rel.as_posix()}"
        if info.file_size != target.stat().st_size:
            return False, f"size_mismatch:{rel.as_posix()}"
    return True, f"covered:{len(files)}"


def archive_coverage_status(archive_path: Path) -> tuple[str, str]:
    extracted_dir = infer_extracted_dir(archive_path)
    if not extracted_dir:
        return "no_extracted_dir", ""
    if archive_path.suffix.lower() == ".zip":
        covered, detail = validate_zip_coverage(archive_path, extracted_dir)
        return ("covered" if covered else "not_covered"), detail
    return "unsupported_archive_type", extracted_dir.as_posix()


def record_archive_row(rows: ReportRows, archive_path: Path, status: str, detail: str, target: str = "") -> None:
    size, mtime = describe_file(archive_path)
    rows.archives.append(
        {
            "source_path": str(archive_path),
            "status": status,
            "detail": detail,
            "size_bytes": str(size),
            "modified_time": mtime,
            "target_path": target,
        }
    )


def file_hash_if_needed(src: Path, dst: Path) -> tuple[str, str]:
    return sha256_file(src), sha256_file(dst)


def process_file_source(spec: SourceSpec, batch_root: Path, rows: ReportRows, dry_run: bool) -> dict[str, int]:
    stats = {"migrated": 0, "duplicates": 0, "conflicts": 0, "quarantined": 0, "unclassified": 0, "archives": 0}

    archive_paths = {path for path in walk_files(spec.root) if path.suffix.lower() in ARCHIVE_EXTENSIONS}
    covered_archives: set[Path] = set()
    for archive_path in sorted(archive_paths, key=lambda item: str(item).lower()):
        status, detail = archive_coverage_status(archive_path)
        target_path, _, _ = file_target_for_spec(spec, archive_path)
        record_archive_row(rows, archive_path, status, detail, str(target_path or ""))
        if status == "covered":
            covered_archives.add(archive_path)
            quarantine_path = quarantine_destination(batch_root, spec, archive_path)
            safe_move(archive_path, quarantine_path, dry_run)
            rows.quarantine.append(
                {
                    "source_path": str(archive_path),
                    "quarantine_path": str(quarantine_path),
                    "reason": "archive_covered_by_extracted_dir",
                    "batch": batch_root.name,
                }
            )
            stats["archives"] += 1
            stats["quarantined"] += 1

    for file_path in walk_files(spec.root):
        if file_path in covered_archives:
            continue

        target_path, subject, bucket = file_target_for_spec(spec, file_path)
        if not target_path or not subject:
            size, mtime = describe_file(file_path)
            rows.unclassified.append(
                {
                    "source_path": str(file_path),
                    "size_bytes": str(size),
                    "modified_time": mtime,
                    "source_group": spec.key,
                    "reason": "unable_to_classify_subject",
                }
            )
            stats["unclassified"] += 1
            continue

        if target_path.exists():
            src_size, src_mtime = describe_file(file_path)
            dst_size, dst_mtime = describe_file(target_path)
            if src_size == dst_size:
                src_hash, dst_hash = file_hash_if_needed(file_path, target_path)
                if src_hash == dst_hash:
                    quarantine_path = quarantine_destination(batch_root, spec, file_path)
                    safe_move(file_path, quarantine_path, dry_run)
                    rows.duplicates.append(
                        {
                            "source_path": str(file_path),
                            "target_path": str(target_path),
                            "size_bytes": str(src_size),
                            "source_mtime": src_mtime,
                            "target_mtime": dst_mtime,
                            "sha256": src_hash,
                        }
                    )
                    rows.quarantine.append(
                        {
                            "source_path": str(file_path),
                            "quarantine_path": str(quarantine_path),
                            "reason": "duplicate_of_target",
                            "batch": batch_root.name,
                        }
                    )
                    stats["duplicates"] += 1
                    stats["quarantined"] += 1
                    continue

            rows.conflicts.append(
                {
                    "source_path": str(file_path),
                    "target_path": str(target_path),
                    "source_size": str(src_size),
                    "target_size": str(dst_size),
                    "source_mtime": src_mtime,
                    "target_mtime": dst_mtime,
                    "recommended_keep": str(target_path),
                    "conflict_type": "file_content_differs",
                }
            )
            stats["conflicts"] += 1
            continue

        safe_copy_file(file_path, target_path, dry_run)
        quarantine_path = quarantine_destination(batch_root, spec, file_path)
        safe_move(file_path, quarantine_path, dry_run)
        rows.moved_originals.append(
            {
                "source_path": str(file_path),
                "target_path": str(target_path),
                "subject": subject,
                "bucket": bucket or "",
            }
        )
        rows.quarantine.append(
            {
                "source_path": str(file_path),
                "quarantine_path": str(quarantine_path),
                "reason": "copied_to_original_library",
                "batch": batch_root.name,
            }
        )
        stats["migrated"] += 1
        stats["quarantined"] += 1

    remove_empty_dirs(spec.root, dry_run)
    return stats


def process_output_source(spec: SourceSpec, batch_root: Path, rows: ReportRows, dry_run: bool) -> dict[str, int]:
    stats = {"migrated": 0, "duplicates": 0, "conflicts": 0, "quarantined": 0, "unclassified": 0}

    for dir_path in sorted((p for p in spec.root.iterdir() if p.is_dir()), key=lambda item: item.name.lower()):
        target_path, subject, bucket = output_target_for_dir(dir_path)
        if not target_path or not subject:
            rows.unclassified.append(
                {
                    "source_path": str(dir_path),
                    "size_bytes": str(sum(p.stat().st_size for p in dir_path.rglob('*') if p.is_file())),
                    "modified_time": now_str(),
                    "source_group": spec.key,
                    "reason": "unable_to_classify_ocr_directory",
                }
            )
            stats["unclassified"] += 1
            continue

        src_meta, src_fingerprint = directory_fingerprint(dir_path)
        if target_path.exists():
            dst_meta, dst_fingerprint = directory_fingerprint(target_path)
            if src_fingerprint == dst_fingerprint:
                quarantine_path = quarantine_destination(batch_root, spec, dir_path)
                safe_move(dir_path, quarantine_path, dry_run)
                rows.duplicates.append(
                    {
                        "source_path": str(dir_path),
                        "target_path": str(target_path),
                        "size_bytes": str(src_meta["size_bytes"]),
                        "source_mtime": now_str(),
                        "target_mtime": now_str(),
                        "sha256": src_fingerprint,
                    }
                )
                rows.quarantine.append(
                    {
                        "source_path": str(dir_path),
                        "quarantine_path": str(quarantine_path),
                        "reason": "duplicate_ocr_directory",
                        "batch": batch_root.name,
                    }
                )
                stats["duplicates"] += 1
                stats["quarantined"] += 1
                continue

            rows.conflicts.append(
                {
                    "source_path": str(dir_path),
                    "target_path": str(target_path),
                    "source_size": str(src_meta["size_bytes"]),
                    "target_size": str(dst_meta["size_bytes"]),
                    "source_mtime": now_str(),
                    "target_mtime": now_str(),
                    "recommended_keep": str(target_path),
                    "conflict_type": "ocr_directory_differs",
                }
            )
            stats["conflicts"] += 1
            continue

        safe_copy_tree(dir_path, target_path, dry_run)
        if not dry_run:
            cleanup_stats = cleanup_book_dir(target_path)
            if cleanup_stats.deleted_total:
                print(
                    f"[cleanup] {target_path} 清理图片 {cleanup_stats.deleted_total} 张"
                    f" (legacy={cleanup_stats.deleted_legacy}, page_like={cleanup_stats.deleted_page_like})"
                )
        quarantine_path = quarantine_destination(batch_root, spec, dir_path)
        safe_move(dir_path, quarantine_path, dry_run)
        rows.moved_middle.append(
            {
                "source_path": str(dir_path),
                "target_path": str(target_path),
                "subject": subject,
                "bucket": bucket or "",
            }
        )
        rows.quarantine.append(
            {
                "source_path": str(dir_path),
                "quarantine_path": str(quarantine_path),
                "reason": "copied_to_middle_library",
                "batch": batch_root.name,
            }
        )
        stats["migrated"] += 1
        stats["quarantined"] += 1

    return stats


def build_source_specs() -> list[SourceSpec]:
    specs: list[SourceSpec] = []

    for source_name, logical_root in DESKTOP_COURSE_ROOTS.items():
        root = DESKTOP_ROOT / source_name
        if root.exists():
            kind = "desktop_course"
            if logical_root == "__101_textbooks__":
                kind = "desktop_101_textbooks"
            elif logical_root == "__101_ppts__":
                kind = "desktop_101_ppts"
            specs.append(
                SourceSpec(
                    key=f"desktop:{source_name}",
                    root=root,
                    kind=kind,
                    library_mode="original",
                    quarantine_prefix="Desktop",
                    logical_root=None if logical_root.startswith("__101_") else logical_root,
                )
            )

    for source_name, logical_root in PHYSICAL_DESKTOP_ROOTS.items():
        root = PHYSICAL_DESKTOP_ROOT / source_name
        if root.exists():
            specs.append(
                SourceSpec(
                    key=f"physical:{source_name}",
                    root=root,
                    kind="physical_subject",
                    library_mode="original",
                    quarantine_prefix="实体桌面",
                    logical_root=logical_root,
                )
            )

    if GLM_INPUT_ROOT.exists():
        specs.append(
            SourceSpec(
                key="glm_input",
                root=GLM_INPUT_ROOT,
                kind="glm_input",
                library_mode="original",
                quarantine_prefix="GLM-OCR_input",
            )
        )

    if GLM_OUTPUT_ROOT.exists():
        specs.append(
            SourceSpec(
                key="glm_output",
                root=GLM_OUTPUT_ROOT,
                kind="glm_output",
                library_mode="middle",
                quarantine_prefix="GLM-OCR_output",
            )
        )

    return specs


def collect_candidate_output_dirs(batch_root: Path, prefix: str) -> list[Path]:
    candidates: dict[str, Path] = {}
    if GLM_OUTPUT_ROOT.exists():
        for path in GLM_OUTPUT_ROOT.iterdir():
            if path.is_dir() and path.name.startswith(prefix):
                candidates[path.name] = path
    quarantine_root = batch_root / "GLM-OCR_output"
    if quarantine_root.exists():
        for path in quarantine_root.rglob("*"):
            if path.is_dir() and path.name.startswith(prefix):
                candidates[path.name] = path
    return sorted(candidates.values(), key=lambda item: item.name.lower())


def collect_candidate_input_files(batch_root: Path, prefix: str) -> list[Path]:
    candidates: dict[str, Path] = {}
    if GLM_INPUT_ROOT.exists():
        for path in GLM_INPUT_ROOT.iterdir():
            if path.is_file() and path.name.startswith(prefix):
                candidates[path.name] = path
    quarantine_root = batch_root / "GLM-OCR_input"
    if quarantine_root.exists():
        for path in quarantine_root.rglob("*"):
            if path.is_file() and path.name.startswith(prefix):
                candidates[path.name] = path
    return sorted(candidates.values(), key=lambda item: item.name.lower())


def build_discrete_math_audit(rows: ReportRows, batch_root: Path) -> None:
    output_dirs = collect_candidate_output_dirs(batch_root, "(101)离散数学_")
    middle_root = MIDDLE_LIBRARY_ROOT / "离散数学"
    original_root = ORIGINAL_LIBRARY_ROOT / "离散数学"
    existing_middle_names = {p.name for p in middle_root.rglob("*") if p.is_dir()} if middle_root.exists() else set()
    existing_original_names = {p.name for p in original_root.rglob("*") if p.is_file()} if original_root.exists() else set()

    for dir_path in output_dirs:
        status = "尚未迁入"
        if dir_path.name in existing_middle_names:
            status = "已完整代表"
        else:
            suffix = dir_path.name.replace("(101)离散数学_", "")
            if any(suffix in name for name in existing_middle_names | existing_original_names):
                status = "同内容但换了人类命名"
        rows.discrete_math.append(
            {
                "ocr_directory": dir_path.name,
                "status": status,
                "source_path": str(dir_path),
            }
        )


def build_plan101_audit(rows: ReportRows, batch_root: Path) -> None:
    input_files = collect_candidate_input_files(batch_root, "(101)")
    output_dirs = {normalize_stem_for_collision(p.name): p.name for p in collect_candidate_output_dirs(batch_root, "(101)")}

    for file_path in input_files:
        subject = subject_for_name(file_path.stem) or "未识别课程"
        bucket = classify_original_bucket(subject, file_path.name) if subject != "未识别课程" else ""
        target_file = ""
        if subject != "未识别课程":
            target_file = str(ORIGINAL_LIBRARY_ROOT / subject / bucket / canonical_file_name(file_path))
        normalized_stem = normalize_stem_for_collision(file_path.stem)
        rows.plan101.append(
            {
                "source_file": str(file_path),
                "subject": subject,
                "bucket": bucket,
                "target_file": target_file,
                "ocr_directory_name": file_path.stem,
                "ocr_status": "有对应OCR目录" if normalized_stem in output_dirs else "缺 OCR 目录",
            }
        )


def touched_subjects(rows: ReportRows) -> tuple[set[str], set[str]]:
    return (
        {row["subject"] for row in rows.moved_originals if row.get("subject")},
        {row["subject"] for row in rows.moved_middle if row.get("subject")},
    )


def build_library_index(root: Path, title: str) -> str:
    lines = [f"# {title}", "", f"- 生成时间：{now_str()}", ""]
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if path.is_dir():
            files = sum(1 for p in path.rglob("*") if p.is_file())
            extras: list[str] = []
            if (path / "目录页.md").exists():
                extras.append("含目录页")
            qr_dir = path / "_front_assets" / "qrcodes"
            qr_count = len(list(qr_dir.glob("*.png"))) if qr_dir.exists() else 0
            if (path / "周边资源-全部.md").exists():
                extras.append("含周边资源页")
            if qr_count:
                extras.append(f"二维码 {qr_count} 个")
            suffix = f" | {'；'.join(extras)}" if extras else ""
            lines.append(f"- `{path.name}/` ({files} files){suffix}")
        else:
            lines.append(f"- `{path.name}`")
    lines.append("")
    return "\n".join(lines)


def refresh_touched_indexes(rows: ReportRows, dry_run: bool) -> None:
    original_subjects, middle_subjects = touched_subjects(rows)
    for subject in sorted(original_subjects):
        root = ORIGINAL_LIBRARY_ROOT / subject
        if root.exists():
            write_markdown(root / "目录.md", build_library_index(root, f"{subject} 资料库目录"), dry_run)
    for subject in sorted(middle_subjects):
        root = MIDDLE_LIBRARY_ROOT / subject
        if root.exists():
            write_markdown(root / "目录.md", build_library_index(root, f"{subject} OCR 中间文件库目录"), dry_run)


def build_overview(rows: ReportRows, stats_by_source: dict[str, dict[str, int]], batch_root: Path, dry_run: bool) -> str:
    lines = [
        "# 迁移总览",
        "",
        f"- 生成时间：{now_str()}",
        f"- 批次：`{batch_root.name}`",
        f"- 模式：`{'dry-run' if dry_run else 'apply'}`",
        "",
        "## 汇总",
        f"- 迁入原件文件数：`{len(rows.moved_originals)}`",
        f"- 迁入 OCR 目录数：`{len(rows.moved_middle)}`",
        f"- 完全重复候选：`{len(rows.duplicates)}`",
        f"- 版本冲突：`{len(rows.conflicts)}`",
        f"- 压缩包复核项：`{len(rows.archives)}`",
        f"- 待人工归类：`{len(rows.unclassified)}`",
        f"- 已进入待确认删除区：`{len(rows.quarantine)}`",
        "",
        "## 来源统计",
    ]
    for source_key, stats in stats_by_source.items():
        lines.append(f"### {source_key}")
        for key in ("migrated", "duplicates", "conflicts", "quarantined", "unclassified", "archives"):
            if key in stats:
                lines.append(f"- {key}: `{stats[key]}`")
        lines.append("")

    lines.extend(
        [
            "## 专项提示",
            f"- 离散数学专项条目：`{len(rows.discrete_math)}`",
            f"- 101 计划专项条目：`{len(rows.plan101)}`",
            "",
            "## 报告文件",
            "- `duplicate_candidates.csv`",
            "- `version_conflicts.csv`",
            "- `archive_coverage.csv`",
            "- `quarantine_manifest.csv`",
            "- `unclassified_items.csv`",
            "- `discrete_math_sync.csv`",
            "- `plan101_sync.csv`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    batch_root = Path(r"F:\待确认删除") / args.batch_name
    report_dir = REPORT_ROOT / args.batch_name
    dry_run = args.dry_run

    rows = ReportRows()
    stats_by_source: dict[str, dict[str, int]] = {}

    ensure_dir(batch_root, dry_run)
    ensure_dir(report_dir, dry_run)
    ensure_dir(ORIGINAL_LIBRARY_ROOT, dry_run)
    ensure_dir(MIDDLE_LIBRARY_ROOT, dry_run)

    for spec in build_source_specs():
        if spec.kind == "glm_output":
            stats = process_output_source(spec, batch_root, rows, dry_run)
        else:
            stats = process_file_source(spec, batch_root, rows, dry_run)
        stats_by_source[spec.key] = stats

    build_discrete_math_audit(rows, batch_root)
    build_plan101_audit(rows, batch_root)
    if not dry_run:
        refresh_touched_indexes(rows, dry_run)

    overview = build_overview(rows, stats_by_source, batch_root, dry_run)
    write_markdown(report_dir / "迁移总览.md", overview, dry_run)
    write_csv(report_dir / "duplicate_candidates.csv", rows.duplicates, dry_run)
    write_csv(report_dir / "version_conflicts.csv", rows.conflicts, dry_run)
    write_csv(report_dir / "archive_coverage.csv", rows.archives, dry_run)
    write_csv(report_dir / "quarantine_manifest.csv", rows.quarantine, dry_run)
    write_csv(report_dir / "unclassified_items.csv", rows.unclassified, dry_run)
    write_csv(report_dir / "moved_originals.csv", rows.moved_originals, dry_run)
    write_csv(report_dir / "moved_middle.csv", rows.moved_middle, dry_run)
    write_csv(report_dir / "discrete_math_sync.csv", rows.discrete_math, dry_run)
    write_csv(report_dir / "plan101_sync.csv", rows.plan101, dry_run)
    write_json(
        report_dir / "summary.json",
        {
            "generated_at": now_str(),
            "batch": batch_root.name,
            "dry_run": dry_run,
            "stats_by_source": stats_by_source,
            "counts": {
                "moved_originals": len(rows.moved_originals),
                "moved_middle": len(rows.moved_middle),
                "duplicates": len(rows.duplicates),
                "conflicts": len(rows.conflicts),
                "archives": len(rows.archives),
                "unclassified": len(rows.unclassified),
                "quarantine": len(rows.quarantine),
            },
        },
        dry_run,
    )

    print("=== Academic Library Migration ===")
    print(f"mode: {'dry-run' if dry_run else 'apply'}")
    print(f"batch: {batch_root}")
    print(f"report: {report_dir}")
    print(f"moved originals: {len(rows.moved_originals)}")
    print(f"moved middle: {len(rows.moved_middle)}")
    print(f"duplicates: {len(rows.duplicates)}")
    print(f"conflicts: {len(rows.conflicts)}")
    print(f"archives: {len(rows.archives)}")
    print(f"unclassified: {len(rows.unclassified)}")
    print(f"quarantine entries: {len(rows.quarantine)}")


if __name__ == "__main__":
    main()
