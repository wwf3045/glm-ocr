from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy import ndimage

from pdf_backend import PdfRenderDocument

REVIEW_ROOT = Path(r"C:\Users\28033\Desktop\codex_short_sessions\recovered_orphan_review")


@dataclass(frozen=True)
class RecoverySpec:
    key: str
    display_name: str
    middle_dir: Path
    source_pdf: Path
    pages: list[int]
    note: str


SPECS: list[RecoverySpec] = [
    RecoverySpec(
        key="discrete_qu_wanling",
        display_name="离散数学（屈婉玲）",
        middle_dir=Path(r"F:\中间文件库\数学\离散数学\教材OCR扫描\离散数学（屈婉玲）"),
        source_pdf=Path(
            r"F:\资料库\数学\离散数学\教材及参考书\离散数学教材\离散数学及其应用（第2版） -- 屈婉玲 -- 2018 -- Higher Education Press -- 9787040500387 -- c80b4e67750da450c72aa431a1b49a9d -- Anna’s Archive.pdf"
        ),
        pages=[161, 162, 163],
        note="这本原先删掉的是普通孤儿图，页码只能从残留记录里反推出 161-163 页。",
    ),
    RecoverySpec(
        key="graph_algebra_structure",
        display_name="图论与代数结构",
        middle_dir=Path(r"F:\中间文件库\数学\离散数学\教材OCR扫描\图论与代数结构"),
        source_pdf=Path(r"F:\资料库\数学\离散数学\教材及参考书\离散数学教材\图论与代数结构（第2版） (崔勇, 张小平) (Z-Library).pdf"),
        pages=[131, 132, 133, 135, 136, 139, 181],
        note="这几页在误删前只有孤儿图，没有正文引用图。",
    ),
    RecoverySpec(
        key="signal_textbook_zhengjunli_vol1",
        display_name="信号与系统（上册）第四版 郑君里",
        middle_dir=Path(r"F:\中间文件库\电气工程与自动化\信号与系统\教材OCR扫描\信号与系统_参考书_信号与系统（上册）第四版 郑君里"),
        source_pdf=Path(r"F:\资料库\电气工程与自动化\信号与系统\教材及参考书\信号与系统_参考书_信号与系统（上册）第四版 郑君里.pdf"),
        pages=[34, 35, 36, 37, 38, 40],
        note="这些页原来既有正文引用图，也有被误删的普通孤儿图，恢复时会尽量排除与现存图重复的候选。",
    ),
    RecoverySpec(
        key="signal_lecture_l4_20250928",
        display_name="信号与系统_课件_L4-20250928",
        middle_dir=Path(r"F:\中间文件库\电气工程与自动化\信号与系统\课件OCR扫描\信号与系统_课件_L4-20250928"),
        source_pdf=Path(r"F:\资料库\电气工程与自动化\信号与系统\课件\信号与系统_课件_L4-20250928.pdf"),
        pages=[7, 8, 9, 10, 13],
        note="这本课件原来误删的是页内残留候选图，恢复时同样会排除与现存引用图重复的候选。",
    ),
    RecoverySpec(
        key="dbms_101_core",
        display_name="(101)数据库管理系统：从基本原理到系统构建",
        middle_dir=Path(r"F:\中间文件库\计算机科学与技术\数据库原理\课程资料OCR扫描\(101)数据库管理系统：从基本原理到系统构建"),
        source_pdf=Path(r"F:\资料库\计算机科学与技术\数据库原理\教材及参考书\(101)数据库管理系统：从基本原理到系统构建.pdf"),
        pages=[521],
        note="这本有 output_backups，但备份里没有页 521 的候选图，所以还是按原件页做恢复候选。",
    ),
]


def normalize_slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", text)
    slug = slug.strip("._-")
    return slug or "item"


def average_hash(image: Image.Image, size: int = 16) -> int:
    gray = ImageOps.grayscale(image).resize((size, size), Image.Resampling.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    avg = arr.mean()
    bits = arr > avg
    value = 0
    for bit in bits.flatten():
        value = (value << 1) | int(bool(bit))
    return int(value)


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def load_existing_page_hashes(book_dir: Path) -> dict[int, list[int]]:
    page_hashes: dict[int, list[int]] = {}
    images_dir = book_dir / "images"
    if not images_dir.exists():
        return page_hashes
    for image_path in images_dir.iterdir():
        name = image_path.name
        if not (name.startswith("p") and "_fig" in name):
            continue
        try:
            page = int(name[1:5])
        except ValueError:
            continue
        try:
            with Image.open(image_path) as image:
                page_hashes.setdefault(page, []).append(average_hash(image))
        except OSError:
            continue
    return page_hashes


def build_text_mask(
    doc: PdfRenderDocument,
    page_index: int,
    width: int,
    height: int,
    zoom: float,
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    padding = int(round(8 * zoom))
    for x0, y0, x1, y1 in doc.iter_text_rects(page_index):
        left = max(0, int(round(x0 * zoom)) - padding)
        top = max(0, int(round(y0 * zoom)) - padding)
        right = min(width, int(round(x1 * zoom)) + padding)
        bottom = min(height, int(round(y1 * zoom)) + padding)
        if right > left and bottom > top:
            mask[top:bottom, left:right] = True
    return mask


def detect_candidates(image: Image.Image, text_mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = np.asarray(ImageOps.grayscale(image))
    foreground = gray < 244
    foreground &= ~text_mask
    # 用更强的形态学过滤把细碎文字压掉，尽量只留下图形/公式块。
    foreground = ndimage.binary_opening(foreground, structure=np.ones((5, 5), dtype=bool))
    foreground = ndimage.binary_closing(foreground, structure=np.ones((7, 7), dtype=bool))
    foreground = ndimage.binary_dilation(foreground, iterations=1)

    labels, count = ndimage.label(foreground)
    boxes = ndimage.find_objects(labels)
    height, width = foreground.shape
    page_area = width * height
    candidates: list[tuple[int, int, int, int]] = []
    for idx, slc in enumerate(boxes, start=1):
        if slc is None:
            continue
        ys, xs = slc
        top, bottom = ys.start, ys.stop
        left, right = xs.start, xs.stop
        box_w = right - left
        box_h = bottom - top
        area = int((labels[slc] == idx).sum())
        if box_w < 60 or box_h < 50:
            continue
        if area < 6000:
            continue
        if box_w * box_h >= 0.82 * page_area:
            continue
        pad = 12
        left = max(0, left - pad)
        top = max(0, top - pad)
        right = min(width, right + pad)
        bottom = min(height, bottom + pad)
        candidates.append((left, top, right, bottom))

    candidates.sort(key=lambda box: (box[1], box[0]))
    return candidates


def candidate_is_duplicate(crop: Image.Image, existing_hashes: list[int], threshold: int = 8) -> bool:
    if not existing_hashes:
        return False
    candidate_hash = average_hash(crop)
    return any(hamming_distance(candidate_hash, value) <= threshold for value in existing_hashes)


def recover_spec(spec: RecoverySpec, review_root: Path) -> dict:
    if not spec.source_pdf.exists():
        raise FileNotFoundError(spec.source_pdf)
    if not spec.middle_dir.exists():
        raise FileNotFoundError(spec.middle_dir)

    target_book_dir = review_root / spec.key
    if target_book_dir.exists():
        shutil.rmtree(target_book_dir)
    target_book_dir.mkdir(parents=True, exist_ok=True)

    existing_hashes = load_existing_page_hashes(spec.middle_dir)
    manifest = {
        "key": spec.key,
        "display_name": spec.display_name,
        "middle_dir": str(spec.middle_dir),
        "source_pdf": str(spec.source_pdf),
        "note": spec.note,
        "pages": [],
    }

    with PdfRenderDocument(spec.source_pdf) as doc:
        for page_no in spec.pages:
            if page_no < 1 or page_no > len(doc):
                continue
            page_index = page_no - 1
            page_dir = target_book_dir / f"page_{page_no:04d}"
            page_dir.mkdir(parents=True, exist_ok=True)

            render = doc.render_page(page_index, dpi=158.4)
            preview_path = page_dir / "page_preview.png"
            render.save(preview_path)

            text_mask = build_text_mask(doc, page_index, render.width, render.height, zoom=2.2)
            boxes = detect_candidates(render, text_mask)
            saved = []
            page_hashes = existing_hashes.get(page_no, [])

            for index, (left, top, right, bottom) in enumerate(boxes, start=1):
                crop = render.crop((left, top, right, bottom))
                if candidate_is_duplicate(crop, page_hashes):
                    continue
                image_name = f"cand_{index:02d}_{left}_{top}_{right}_{bottom}.png"
                image_path = page_dir / image_name
                crop.save(image_path)
                saved.append(
                    {
                        "name": image_name,
                        "path": str(image_path),
                        "bbox": [left, top, right, bottom],
                        "width": crop.width,
                        "height": crop.height,
                    }
                )

            page_manifest = {
                "page": page_no,
                "preview": str(preview_path),
                "candidate_count": len(saved),
                "candidates": saved,
            }
            (page_dir / "manifest.json").write_text(
                json.dumps(page_manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            manifest["pages"].append(page_manifest)

    (target_book_dir / "book_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main():
    if REVIEW_ROOT.exists():
        shutil.rmtree(REVIEW_ROOT)
    REVIEW_ROOT.mkdir(parents=True, exist_ok=True)

    summary = {"review_root": str(REVIEW_ROOT), "books": []}
    for spec in SPECS:
        summary["books"].append(recover_spec(spec, REVIEW_ROOT))

    summary_path = REVIEW_ROOT / "recovery_manifest.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(
        {
            "review_root": str(REVIEW_ROOT),
            "books": len(summary["books"]),
            "pages": sum(len(book["pages"]) for book in summary["books"]),
            "candidates": sum(page["candidate_count"] for book in summary["books"] for page in book["pages"]),
        },
        ensure_ascii=False,
        indent=2,
    ))
    print(f"manifest: {summary_path}")


if __name__ == "__main__":
    main()
