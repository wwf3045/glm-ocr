"""
GLM-OCR 批量文档识别脚本
=========================
将 PDF/PPT/PPTX/图片放入 input 文件夹，运行此脚本即可在 output 文件夹中获取 Markdown 结果。

功能：
- PDF 按固定页数切分，每段直传 API，每段输出一个 .md 文件
- PDF 直传返回空时自动回退为逐页转图片模式
- PPT/PPTX 通过 COM 自动化转为 PDF 后处理
- 自动裁剪 API 标注的图片区域，保存到 images 文件夹
- 自动抑制页眉页脚、页码角标、logo、水印和单字符公式碎片图
- 输出前自动规整 Markdown / LaTeX 分隔符，减少下游 Obsidian 渲染问题
- 收尾时清理未引用的 legacy 页面对象图和整页候选截图
- 支持超长截图（微信长截图等），自动分段识别后合并
- 断点续扫：已处理过的分段自动跳过
- 失败自动重试 3 次
"""

import argparse
import base64
import io
import json
import os
import queue
import re
import sys
import time
import tempfile
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Windows 下强制 UTF-8 输出，避免 GBK 编码错误
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image
from dotenv import load_dotenv
from zai import ZaiClient, ZhipuAiClient
from junk_image_blacklist import (
    DEFAULT_BLACKLIST_PATH,
    build_signature_from_image,
    ensure_registry as ensure_blacklist_registry,
    matches_family as image_matches_blacklist_family,
)
from markdown_cleanup import (
    normalize_ocr_markdown,
    repair_markdown_file,
    write_markdown_text,
    write_math_audit_report,
)
from ocr_image_index import (
    audit_orphan_images,
    collect_referenced_image_counts,
    inspect_image_size,
    is_page_like_size,
)
from pdf_backend import (
    PdfRenderDocument,
    extract_pdf_page_text as backend_extract_pdf_page_text,
    extract_pdf_segment as backend_extract_pdf_segment,
    get_pdf_page_count,
)

# ============================================================
# 配置
# ============================================================
load_dotenv()
API_KEY = os.getenv("GLM_API_KEY", "")

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_DIR = Path(__file__).parent / "_cache"
PPT_PDF_CACHE_DIR = CACHE_DIR / "ppt_pdf"

PAGES_PER_MD_PDF = 20        # PDF：每 20 页一个 .md
PAGES_PER_MD_PPT = 50        # PPT/PPTX：每 50 页(slide)一个 .md
RETRY_TIMES = 3              # 失败重试次数
RETRY_DELAY = 5              # 重试间隔（秒）
FALLBACK_DPI = 300           # 回退图片模式的 DPI
MAX_WORKERS = 2              # API 最大并发数
IMAGE_SEGMENT_HEIGHT = 4000  # 长图每段高度（像素）
IMAGE_OVERLAP = 200          # 相邻段重叠像素（避免截断文字）

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".pptx", ".ppt"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}

IMAGE_OCR_PROMPT = """请将这张图片中的所有文字内容完整转换为 Markdown 格式。要求：
1. 保留所有文字内容，不要遗漏任何一行
2. 数学公式使用 LaTeX 格式（行内用 $...$，独立公式用 $$...$$）
3. 保留标题层级和段落结构
4. 如果是聊天记录截图，保留发言人和时间信息
5. 如果是网页截图，保留标题、正文和列表结构
6. 保持原文的段落和换行结构"""

BBOX_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(page=(\d+),bbox=\[([^\]]+)\]\)")
LEGACY_PAGE_IMAGE_PATTERN = re.compile(r"^page_\d+_img_\d+\.(png|jpe?g|bmp|webp)$", re.IGNORECASE)


# ============================================================
# 工具函数
# ============================================================

# 线程锁：保护 print 输出不交叉
_print_lock = threading.Lock()

def _tprint(*args, **kwargs):
    """线程安全的 print"""
    with _print_lock:
        print(*args, **kwargs)


def check_config():
    if not API_KEY or API_KEY == "your-api-key-here":
        print("[!] 请先在 .env 文件中填入你的 GLM_API_KEY")
        print("    获取地址: https://open.bigmodel.cn/ -> API Keys")
        sys.exit(1)


def clean_name(name: str, max_len: int = 80) -> str:
    """清理文件/文件夹名：去掉下载来源标记、哈希、多余符号，截断过长名称"""
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


def has_meaningful_md_content(md_text: str) -> bool:
    """判断 OCR 结果是否真的有内容，而不只是失败占位注释。"""
    text = re.sub(r"<!--.*?-->", " ", md_text, flags=re.S)
    text = re.sub(r"\s+", "", text)
    return bool(text)


def sanitize_error_message(err) -> str:
    """压缩异常文本，便于写入失败报告。"""
    if err is None:
        return ""
    msg = str(err).strip()
    msg = re.sub(r"\s+", " ", msg)
    return msg[:300]


def get_segment_failure_path(book_dir: Path, stem: str, page_label: str) -> Path:
    failed_dir = book_dir / "_failed_segments"
    failed_dir.mkdir(parents=True, exist_ok=True)
    return failed_dir / f"{stem}_{page_label}.failed.json"


def convert_ppt_to_pdf(ppt_path: str, pdf_path: str):
    """使用 PowerPoint/WPS COM 自动化将 PPTX/PPT 转为 PDF"""
    try:
        import win32com.client
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
    except Exception:
        try:
            import comtypes.client
            ppt_app = comtypes.client.CreateObject("Kwpp.Application")
        except Exception:
            try:
                import comtypes.client
                ppt_app = comtypes.client.CreateObject("PowerPoint.Application")
            except Exception as e:
                print(f"  [!] PPT 转 PDF 失败：无法启动 PowerPoint/WPS ({e})")
                return False

    try:
        ppt_app.Visible = True   # Must be True for PDF export to work
        abs_ppt = os.path.abspath(ppt_path)
        abs_pdf = os.path.abspath(pdf_path)
        presentation = ppt_app.Presentations.Open(abs_ppt, WithWindow=False)
        presentation.SaveAs(abs_pdf, 32)  # 32 = ppSaveAsPDF
        presentation.Close()
        ppt_app.Quit()
        return True
    except Exception as e:
        print(f"  [!] PPT 转 PDF 失败：{e}")
        try:
            ppt_app.Quit()
        except Exception:
            pass
        return False


def extract_pdf_segment(pdf_path: str, start: int, end: int, out_path: str):
    """从 PDF 中提取 [start, end) 页（0-indexed），保存到 out_path"""
    backend_extract_pdf_segment(pdf_path, start, end, out_path)


def pdf_pages_to_images(pdf_path: str, start: int, end: int, temp_dir: str) -> list[str]:
    """将 PDF 的 [start, end) 页渲染为 PNG，返回图片路径列表"""
    paths = []
    with PdfRenderDocument(pdf_path) as doc:
        total_pages = len(doc)
        for i in range(start, min(end, total_pages)):
            image = doc.render_page(i, dpi=FALLBACK_DPI)
            p = os.path.join(temp_dir, f"page_{i+1:04d}.png")
            image.save(p)
            paths.append(p)
    return paths


def extract_pdf_page_text_fallback(pdf_path: str, page_index: int) -> str:
    """最后兜底：直接从 PDF 页抽文本，适合可编辑 PDF 被 OCR 安全策略误拦的情况。"""
    text = backend_extract_pdf_page_text(pdf_path, page_index)
    return text.strip() if text else ""


def file_to_data_uri(file_path: str) -> str:
    """将本地文件转为 base64 data URI"""
    ext = os.path.splitext(file_path)[1].lower()
    mime = MIME_MAP.get(ext, "application/octet-stream")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def call_glm_ocr_raw(client: ZaiClient, file_path: str):
    """调用 GLM-OCR API，返回 (响应对象, 最后一次错误文本)。"""
    data_uri = file_to_data_uri(file_path)
    last_error = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = client.layout_parsing.create(
                model="glm-ocr",
                file=data_uri,
            )
            return resp, None
        except Exception as e:
            last_error = sanitize_error_message(e)
            _tprint(f"    [!] 第 {attempt} 次调用失败: {e}")
            if attempt < RETRY_TIMES:
                _tprint(f"    等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
            else:
                _tprint(f"    [x] 已达最大重试次数，跳过此段")
                return None, last_error


def get_md_from_response(resp) -> str:
    """从 API 响应中提取 md_results 文本"""
    if resp is None:
        return "\n\n<!-- OCR 失败 -->\n\n"
    if hasattr(resp, "md_results"):
        return resp.md_results or ""
    if hasattr(resp, "data"):
        data = resp.data
        if isinstance(data, dict) and "md_results" in data:
            return data["md_results"] or ""
        return str(data)
    return str(resp)


def get_api_page_sizes(resp) -> dict:
    """
    从 layout_details 提取每页的 API 渲染尺寸。
    返回 {page_index: (width, height)}
    """
    sizes = {}
    if resp is None or not hasattr(resp, "layout_details") or not resp.layout_details:
        return sizes

    for page_idx, page_details in enumerate(resp.layout_details):
        for item in page_details:
            w = getattr(item, "width", None)
            h = getattr(item, "height", None)
            if w and h:
                sizes[page_idx] = (w, h)
                break
    return sizes


def normalize_text_for_coverage(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text.lower())
    return text


def page_text_is_covered(page_md: str, segment_md: str) -> bool:
    page_normalized = normalize_text_for_coverage(page_md)
    segment_normalized = normalize_text_for_coverage(segment_md)
    if len(page_normalized) >= 6 and page_normalized in segment_normalized:
        return True

    lines = [
        normalize_text_for_coverage(line)
        for line in page_md.splitlines()
    ]
    lines = [line for line in lines if len(line) >= 4]
    lines.sort(key=len, reverse=True)
    return any(line in segment_normalized for line in lines[:5])


def page_to_small_grayscale(image: Image.Image, max_edge: int = 480) -> Image.Image:
    image = image.convert("L")
    image.thumbnail((max_edge, max_edge))
    return image


def detect_sparse_title_page_candidates(pdf_path: str, start: int, end: int) -> list[int]:
    candidates: list[int] = []
    with PdfRenderDocument(pdf_path) as doc:
        for page_index in range(start, min(end, len(doc))):
            image = page_to_small_grayscale(doc.render_page(page_index, dpi=72.0, grayscale=True))
            width, height = image.size
            if width <= 0 or height <= 0:
                continue

            binary = image.point(lambda pixel: 255 if pixel < 232 else 0)
            bbox = binary.getbbox()
            if bbox is None:
                continue

            dark_pixels = sum(1 for pixel in binary.getdata() if pixel > 0)
            dark_ratio = dark_pixels / max(width * height, 1)
            bbox_width = bbox[2] - bbox[0]
            bbox_height = bbox[3] - bbox[1]
            bbox_area_ratio = (bbox_width * bbox_height) / max(width * height, 1)
            bbox_width_ratio = bbox_width / max(width, 1)
            bbox_height_ratio = bbox_height / max(height, 1)
            center_x = ((bbox[0] + bbox[2]) / 2) / max(width, 1)
            center_y = ((bbox[1] + bbox[3]) / 2) / max(height, 1)

            if (
                0.0003 <= dark_ratio <= 0.03
                and bbox_area_ratio <= 0.45
                and bbox_width_ratio <= 0.92
                and bbox_height_ratio <= 0.78
                and 0.18 <= center_x <= 0.82
                and 0.05 <= center_y <= 0.90
            ):
                candidates.append(page_index)
    return candidates


def bbox_is_near_full_page(coords: list[float], api_size: tuple[float, float]) -> bool:
    api_w, api_h = api_size
    if api_w <= 0 or api_h <= 0:
        return False

    x0, y0, x1, y1 = coords
    width = max(0.0, x1 - x0)
    height = max(0.0, y1 - y0)
    area_ratio = (width * height) / max(api_w * api_h, 1.0)
    width_ratio = width / api_w
    height_ratio = height / api_h
    return area_ratio >= 0.55 or (width_ratio >= 0.78 and height_ratio >= 0.78)


def bbox_is_header_footer_like(coords: list[float], api_size: tuple[float, float]) -> bool:
    """抑制页眉页脚、章节横条、页码角标等窄条型 bbox。"""
    api_w, api_h = api_size
    if api_w <= 0 or api_h <= 0:
        return False

    x0, y0, x1, y1 = coords
    width = max(0.0, x1 - x0)
    height = max(0.0, y1 - y0)
    if width <= 0 or height <= 0:
        return False

    width_ratio = width / api_w
    height_ratio = height / api_h
    top_ratio = y0 / api_h
    bottom_ratio = (api_h - y1) / api_h
    left_ratio = x0 / api_w
    right_ratio = (api_w - x1) / api_w
    near_top_or_bottom = top_ratio <= 0.08 or bottom_ratio <= 0.06
    near_side = left_ratio <= 0.08 or right_ratio <= 0.08

    if near_top_or_bottom and width_ratio >= 0.45 and height_ratio <= 0.10:
        return True

    if near_top_or_bottom and width_ratio >= 0.25 and height_ratio <= 0.06 and near_side:
        return True

    if near_top_or_bottom and width_ratio <= 0.12 and height_ratio <= 0.08 and near_side:
        return True

    if near_top_or_bottom and near_side and width_ratio <= 0.28 and height_ratio <= 0.10:
        return True

    return False


def find_suspicious_bbox_pages(md_text: str, page_sizes: dict) -> set[int]:
    suspicious: set[int] = set()
    for match in BBOX_IMAGE_PATTERN.finditer(md_text):
        page_in_seg = int(match.group(2))
        coords = [float(x.strip()) for x in match.group(3).split(",")]
        if len(coords) != 4:
            continue
        api_size = page_sizes.get(page_in_seg)
        if not api_size:
            continue
        if bbox_is_near_full_page(coords, api_size):
            suspicious.add(page_in_seg)
    return suspicious


_BLACKLIST_FAMILIES_CACHE: list[dict] | None = None


def load_blacklist_families() -> list[dict]:
    global _BLACKLIST_FAMILIES_CACHE
    if _BLACKLIST_FAMILIES_CACHE is None:
        registry = ensure_blacklist_registry(DEFAULT_BLACKLIST_PATH)
        _BLACKLIST_FAMILIES_CACHE = registry.get("families", [])
    return _BLACKLIST_FAMILIES_CACHE


def estimate_background_brightness(gray: Image.Image) -> float:
    width, height = gray.size
    edge = max(1, min(width, height) // 8)
    samples = []
    for box in [
        (0, 0, edge, edge),
        (width - edge, 0, width, edge),
        (0, height - edge, edge, height),
        (width - edge, height - edge, width, height),
    ]:
        region = gray.crop(box)
        samples.extend(region.getdata())
    if not samples:
        return 255.0
    samples.sort()
    return float(samples[len(samples) // 2])


def detect_binary_foreground(gray: Image.Image) -> Image.Image:
    background = estimate_background_brightness(gray)
    if background < 128:
        threshold = min(255, int(background + 42))
        return gray.point(lambda pixel: 255 if pixel > threshold else 0)
    threshold = max(0, int(background - 42))
    return gray.point(lambda pixel: 255 if pixel < threshold else 0)


def classify_cropped_image_for_suppression(image: Image.Image) -> tuple[bool, str]:
    signature = build_signature_from_image(image)
    for family in load_blacklist_families():
        if image_matches_blacklist_family(signature, family):
            return True, f"blacklisted_family:{family['name']}"

    gray = image.convert("L")
    binary = detect_binary_foreground(gray)
    bbox = binary.getbbox()
    if bbox is None:
        return True, "empty_crop"

    width, height = binary.size
    fg_pixels = sum(1 for pixel in binary.getdata() if pixel > 0)
    fg_ratio = fg_pixels / max(width * height, 1)
    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    bbox_area_ratio = (bbox_width * bbox_height) / max(width * height, 1)
    max_dim = max(width, height)

    if (
        max_dim <= 420
        and fg_ratio <= 0.14
        and bbox_area_ratio <= 0.20
        and bbox_width / max(width, 1) <= 0.42
        and bbox_height / max(height, 1) <= 0.55
    ):
        return True, "glyph_fragment"

    return False, ""


def ocr_single_pdf_page_image(client: ZaiClient, pdf_path: str, page_index: int, temp_dir: str) -> tuple[str, str | None]:
    image_paths = pdf_pages_to_images(pdf_path, page_index, page_index + 1, temp_dir)
    if not image_paths:
        return "", "page_image_render_failed"

    resp, page_error = call_glm_ocr_raw(client, image_paths[0])
    page_md = get_md_from_response(resp)
    if has_meaningful_md_content(page_md):
        return page_md, None

    fallback_text = extract_pdf_page_text_fallback(pdf_path, page_index)
    if has_meaningful_md_content(fallback_text):
        return f"<!-- 第 {page_index+1} 页使用 PDF 文本回退 -->\n\n{fallback_text}", None

    return "", page_error or "empty_result"


def inject_page_supplements(md_text: str, supplements: list[dict]) -> str:
    if not supplements:
        return md_text

    blocks = []
    for supplement in supplements:
        blocks.append(
            f"<!-- 第 {supplement['page']} 页单页补录 | reason: {supplement['reason']} -->\n\n"
            f"{supplement['text']}"
        )
    return "\n\n".join(blocks) + "\n\n---\n\n" + md_text


def replace_bbox_images(md_text: str, pdf_path: str, seg_start: int,
                        images_dir: str, page_sizes: dict,
                        suppressed_pages: set[int] | None = None) -> str:
    """
    将 md_results 中的 ![](page=X,bbox=[x0,y0,x1,y1]) 替换为实际裁剪的图片。
    page_sizes: 从 API layout_details 获取的每页渲染尺寸 {page_idx: (w, h)}
    """
    if not BBOX_IMAGE_PATTERN.search(md_text):
        return md_text

    os.makedirs(images_dir, exist_ok=True)
    img_count = 0
    rendered_pages: dict[int, Image.Image] = {}

    with PdfRenderDocument(pdf_path) as doc:
        def replace_match(match):
            nonlocal img_count
            alt = match.group(1)
            page_in_seg = int(match.group(2))
            coords = [float(x.strip()) for x in match.group(3).split(",")]
            if len(coords) != 4:
                return match.group(0)

            real_page = seg_start + page_in_seg
            if real_page >= len(doc):
                return match.group(0)

            api_size = page_sizes.get(page_in_seg)
            if not api_size:
                for size_candidate in page_sizes.values():
                    api_size = size_candidate
                    break
                if not api_size:
                    api_size = (2040, 2520)

            if suppressed_pages and page_in_seg in suppressed_pages and bbox_is_near_full_page(coords, api_size):
                return ""

            if bbox_is_header_footer_like(coords, api_size):
                _tprint(f"    [skip] 第{real_page+1}页 bbox 图被抑制：header_footer_like")
                return ""

            try:
                rendered_page = rendered_pages.get(real_page)
                if rendered_page is None:
                    rendered_page = doc.render_page(real_page, dpi=216.0)
                    rendered_pages[real_page] = rendered_page
                cropped_image = doc.render_bbox_crop(
                    real_page,
                    tuple(coords),
                    api_size,
                    dpi=216.0,
                    rendered_page=rendered_page,
                )
            except Exception:
                return match.group(0)

            if cropped_image.width < 5 or cropped_image.height < 5:
                return match.group(0)

            suppress, reason = classify_cropped_image_for_suppression(cropped_image)
            if suppress:
                _tprint(f"    [skip] 第{real_page+1}页 bbox 图被抑制：{reason}")
                return ""

            img_count += 1
            img_name = f"p{real_page+1:04d}_fig{img_count:04d}.png"
            cropped_image.save(os.path.join(images_dir, img_name))

            label = alt or f"第{real_page+1}页-图{img_count}"
            return f"![{label}](images/{img_name})"

        new_text = BBOX_IMAGE_PATTERN.sub(replace_match, md_text)

    if img_count > 0:
        _tprint(f"    提取了 {img_count} 张图片")

    return new_text


def call_glm_ocr_with_fallback(client: ZaiClient, pdf_path: str,
                                start: int, end: int, temp_dir: str):
    """
    先用 PDF 直传调 API；如果返回空，自动回退为逐页转图片模式。
    返回包含主文本、页尺寸、失败页、单页补录和整页 bbox 抑制页的字典。
    """
    seg_pdf = os.path.join(temp_dir, f"seg_{start+1}-{end}.pdf")
    extract_pdf_segment(pdf_path, start, end, seg_pdf)
    resp, seg_error = call_glm_ocr_raw(client, seg_pdf)
    md_text = get_md_from_response(resp)
    page_sizes = get_api_page_sizes(resp) if resp else {}
    sparse_candidates = detect_sparse_title_page_candidates(pdf_path, start, end)

    if has_meaningful_md_content(md_text):
        suspicious_pages = set(sparse_candidates) | find_suspicious_bbox_pages(md_text, page_sizes)
        supplements: list[dict] = []
        suppressed_pages: set[int] = set()

        for page_index in sorted(suspicious_pages):
            absolute_page = start + page_index
            page_md, page_error = ocr_single_pdf_page_image(client, pdf_path, absolute_page, temp_dir)
            if not has_meaningful_md_content(page_md):
                if page_error:
                    _tprint(f"    [warn] 第 {absolute_page+1} 页单页补录失败：{page_error}")
                continue
            suppressed_pages.add(page_index)
            if page_text_is_covered(page_md, md_text):
                continue
            supplements.append(
                {
                    "page": absolute_page + 1,
                    "reason": "sparse_title_page" if page_index in sparse_candidates else "full_page_bbox",
                    "text": page_md,
                }
            )

        return {
            "md_text": md_text,
            "page_sizes": page_sizes,
            "failed_pages": [],
            "supplements": supplements,
            "suppressed_pages": sorted(suppressed_pages),
            "sparse_candidates": [page + 1 for page in sparse_candidates],
        }

    # 回退：逐页转图片
    _tprint(f"    PDF 直传返回空，回退为图片模式...", flush=True)
    img_paths = pdf_pages_to_images(pdf_path, start, end, temp_dir)
    page_results = []
    failed_pages = []
    for j, img_path in enumerate(img_paths):
        page_no = start + j + 1
        _tprint(f"    第 {page_no} 页(图片模式)...", flush=True)
        resp_img, page_error = call_glm_ocr_raw(client, img_path)
        page_md = get_md_from_response(resp_img)
        if has_meaningful_md_content(page_md):
            page_results.append(page_md)
        else:
            fallback_text = extract_pdf_page_text_fallback(pdf_path, page_no - 1)
            if has_meaningful_md_content(fallback_text):
                page_results.append(
                    f"<!-- 第 {page_no} 页使用 PDF 文本回退 -->\n\n{fallback_text}"
                )
                continue
            failed_pages.append({
                "page": page_no,
                "reason": page_error or seg_error or "empty_result",
            })
            page_results.append(
                f"<!-- OCR 页失败: {page_no} | reason: {page_error or seg_error or 'empty_result'} -->"
            )
        if j < len(img_paths) - 1:
            time.sleep(0.5)
    return {
        "md_text": "\n\n".join(page_results),
        "page_sizes": {},
        "failed_pages": failed_pages,
        "supplements": [],
        "suppressed_pages": [],
        "sparse_candidates": [page + 1 for page in sparse_candidates],
    }


# ============================================================
# 处理长图（微信截图等）
# ============================================================

def split_long_image(img):
    """将长图切分为多段，相邻段有重叠"""
    w, h = img.size
    if h <= IMAGE_SEGMENT_HEIGHT:
        return [img]

    segments = []
    y = 0
    while y < h:
        y_end = min(y + IMAGE_SEGMENT_HEIGHT, h)
        seg = img.crop((0, y, w, y_end))
        segments.append(seg)
        y = y_end - IMAGE_OVERLAP
        if y_end == h:
            break
    return segments


def pil_to_base64(img, fmt="PNG"):
    """将 PIL Image 转为 base64"""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


def ocr_single_image_b64(client: ZaiClient, img_b64: str):
    """发送单张 base64 图片到 GLM-OCR API"""
    data_uri = f"data:image/png;base64,{img_b64}"
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = client.layout_parsing.create(
                model="glm-ocr",
                file=data_uri,
            )
            return get_md_from_response(resp), None
        except Exception as e:
            _tprint(f"    [!] 第 {attempt} 次调用失败: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)
            else:
                return None, sanitize_error_message(e)


def process_long_image(client: ZaiClient, file_path: Path, book_dir: Path):
    """处理单张图片文件（支持超长截图自动分段）"""
    img = Image.open(str(file_path))
    w, h = img.size
    segments = split_long_image(img)
    total = len(segments)
    print(f"  尺寸 {w}x{h}，分 {total} 段处理")

    results = []
    for i, seg in enumerate(segments):
        seg_md = book_dir / f"segment_{i + 1}.md"

        # 断点续扫
        if seg_md.exists() and seg_md.stat().st_size > 0:
            print(f"  段 {i + 1}/{total} 已完成，跳过")
            content = seg_md.read_text(encoding="utf-8")
            normalized = normalize_ocr_markdown(content)
            if normalized != content:
                write_markdown_text(seg_md, content)
            results.append(normalized)
            continue

        print(f"  段 {i + 1}/{total}...", flush=True)
        img_b64 = pil_to_base64(seg)
        result, error = ocr_single_image_b64(client, img_b64)

        if result and has_meaningful_md_content(result):
            write_markdown_text(seg_md, result)
            results.append(normalize_ocr_markdown(result))
            print(f"  段 {i + 1} 完成")
        else:
            print(f"  段 {i + 1} 失败！{(' ' + error) if error else ''}")

    img.close()

    # 合并所有段为单个 md（如果多于1段）
    if len(results) > 1:
        merged_path = book_dir / f"{file_path.stem}.md"
        write_markdown_text(merged_path, "\n\n".join(results))
        print(f"  已合并 {len(results)} 段 -> {file_path.stem}.md")


# ============================================================
# 手写识别（ZhipuAiClient.ocr.handwriting_ocr）
# ============================================================

def call_handwrite_ocr(client: ZhipuAiClient, img_bytes: bytes) -> str:
    """调用手写识别 API，返回纯文本（每行一个 words），带重试"""
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = client.ocr.handwriting_ocr(
                file=img_bytes,
                tool_type="hand_write",
            )
            if not resp.words_result:
                return ""
            return "\n".join(wr.words for wr in resp.words_result)
        except Exception as e:
            _tprint(f"    [!] 第 {attempt} 次调用失败: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)
            else:
                _tprint(f"    [x] 已达最大重试次数，跳过")
                return ""


def process_handwrite_image(client: ZhipuAiClient, img_path: Path, book_dir: Path):
    """手写识别：处理单张图片"""
    md_path = book_dir / f"{img_path.stem}.md"
    if md_path.exists():
        repair_markdown_file(md_path)
        print(f"  [跳过] 已存在: {md_path.name}")
        return

    print(f"  调用手写识别 API...")
    with open(str(img_path), "rb") as f:
        img_bytes = f.read()
    text = call_handwrite_ocr(client, img_bytes)
    write_markdown_text(md_path, text)
    print(f"  [ok] 完成 -> {md_path.name}")


def process_handwrite_pdf(client: ZhipuAiClient, pdf_path: Path, book_dir: Path,
                          pages_per_md: int = None):
    """手写识别：处理 PDF（逐页转图片后识别）"""
    if pages_per_md is None:
        pages_per_md = PAGES_PER_MD_PDF

    total_pages = get_pdf_page_count(pdf_path)

    total_segments = -(-total_pages // pages_per_md)
    print(f"  共 {total_pages} 页，将输出 {total_segments} 个 .md 文件")

    for seg_idx in range(total_segments):
        seg_start = seg_idx * pages_per_md
        seg_end = min(seg_start + pages_per_md, total_pages)
        page_label = f"{seg_start+1:04d}-{seg_end:04d}"
        md_filename = f"{clean_name(pdf_path.stem)}_{page_label}.md"
        md_path = book_dir / md_filename

        if md_path.exists():
            repair_markdown_file(md_path)
            print(f"  [{seg_start+1}-{seg_end}] 已完成，跳过")
            continue

        print(f"  [{seg_start+1}-{seg_end}] 逐页手写识别...", flush=True)
        page_texts = []
        with PdfRenderDocument(pdf_path) as doc:
            for page_idx in range(seg_start, seg_end):
                image = doc.render_page(page_idx, dpi=FALLBACK_DPI)
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                img_bytes = buf.getvalue()
                print(f"    第 {page_idx+1} 页...", flush=True)
                text = call_handwrite_ocr(client, img_bytes)
                if text:
                    page_texts.append(f"<!-- 第{page_idx+1}页 -->\n\n{text}")
                else:
                    page_texts.append(f"<!-- 第{page_idx+1}页：识别为空 -->")

        header = f"<!-- PDF页码: {seg_start+1}-{seg_end} | 文件: {pdf_path.name} | 模式: 手写识别 -->\n\n"
        write_markdown_text(md_path, header + "\n\n".join(page_texts))
        print(f"    -> {md_filename}")

    print(f"  [ok] 手写识别完成")


def process_handwrite_file(client: ZhipuAiClient, file_path: Path):
    """手写识别模式：处理单个文件"""
    book_dir = OUTPUT_DIR / clean_name(file_path.stem)
    book_dir.mkdir(parents=True, exist_ok=True)
    ext = file_path.suffix.lower()

    if ext in (".pptx", ".ppt"):
        pdf_path = book_dir / f"{file_path.stem}.pdf"
        if not pdf_path.exists():
            print(f"  转换 PPT -> PDF...", flush=True)
            if not convert_ppt_to_pdf(str(file_path), str(pdf_path)):
                return
            print(f"  转换完成")
        process_handwrite_pdf(client, pdf_path, book_dir,
                              pages_per_md=PAGES_PER_MD_PPT)
    elif ext == ".pdf":
        process_handwrite_pdf(client, file_path, book_dir)
    elif ext in IMAGE_EXTENSIONS:
        process_handwrite_image(client, file_path, book_dir)
    else:
        print(f"  [!] 不支持的文件格式: {ext}")
        return None

    math_audit = run_math_command_audit(book_dir)
    math_audit["book_name"] = book_dir.name
    return {
        "book_dir": book_dir,
        "math_audit": math_audit,
    }


# ============================================================
# 处理 PDF（支持并发）
# ============================================================

def _process_one_segment(client: ZaiClient, pdf_path: str, seg_start: int,
                         seg_end: int, book_dir: Path, images_dir: str,
                         file_name: str):
    """处理 PDF 的一个分段（供线程池调用）"""
    page_label = f"{seg_start+1:04d}-{seg_end:04d}"
    stem = clean_name(Path(pdf_path).stem)
    md_filename = f"{stem}_{page_label}.md"
    md_path = book_dir / md_filename
    failure_path = get_segment_failure_path(book_dir, stem, page_label)

    _tprint(f"  [{seg_start+1}-{seg_end}] 调用 API...", flush=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        segment_result = call_glm_ocr_with_fallback(
            client, pdf_path, seg_start, seg_end, temp_dir
        )

    md_text = segment_result["md_text"]
    page_sizes = segment_result["page_sizes"]
    failed_pages = segment_result["failed_pages"]

    if segment_result["supplements"]:
        _tprint(
            f"    [info] 第 {seg_start+1}-{seg_end} 页补入 {len(segment_result['supplements'])} 个稀疏章节页/整页截图页",
            flush=True,
        )
        md_text = inject_page_supplements(md_text, segment_result["supplements"])

    # 将 ![](page=X,bbox=[...]) 替换为实际裁剪的图片
    md_text = replace_bbox_images(md_text, pdf_path, seg_start,
                                   images_dir, page_sizes,
                                   suppressed_pages=set(segment_result["suppressed_pages"]))
    md_text = normalize_ocr_markdown(md_text)

    if failed_pages:
        failure_path.write_text(
            json.dumps({
                "file": file_name,
                "page_range": page_label,
                "failed_pages": failed_pages,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise RuntimeError(
            f"第 {seg_start+1}-{seg_end} 页有 {len(failed_pages)} 页逐页回退后仍失败"
        )

    if not has_meaningful_md_content(md_text):
        failure_path.write_text(
            json.dumps({
                "file": file_name,
                "page_range": page_label,
                "failed_pages": [{
                    "page": f"{seg_start+1}-{seg_end}",
                    "reason": "empty_or_failure_placeholder",
                }],
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        raise RuntimeError(
            f"第 {seg_start+1}-{seg_end} 页 OCR 为空或只返回失败占位"
        )

    # 加元信息注释头
    header = f"<!-- PDF页码: {seg_start+1}-{seg_end} | 文件: {file_name} -->\n\n"
    write_markdown_text(md_path, header + md_text)
    if failure_path.exists():
        failure_path.unlink()

    _tprint(f"    -> {md_filename}")
    return md_filename


def finalize_pdf_outputs(book_dir: Path):
    images_dir = book_dir / "images"
    if images_dir.exists():
        referenced = collect_referenced_image_counts(book_dir)
        purged_legacy = 0
        purged_page_like = 0
        for image_path in images_dir.iterdir():
            if not image_path.is_file():
                continue
            if referenced.get(image_path.name, 0) > 0:
                continue
            if LEGACY_PAGE_IMAGE_PATTERN.match(image_path.name):
                image_path.unlink()
                purged_legacy += 1
                continue

            size = inspect_image_size(image_path)
            if size and is_page_like_size(*size):
                image_path.unlink()
                purged_page_like += 1
                continue
        if purged_legacy:
            print(f"  [cleanup] 清理未引用的 legacy 页面对象图 {purged_legacy} 张")
        if purged_page_like:
            print(f"  [cleanup] 清理未引用的整页候选截图 {purged_page_like} 张")

    if images_dir.is_dir() and not any(images_dir.iterdir()):
        images_dir.rmdir()

    audit = audit_orphan_images(book_dir)
    report_path = audit.get("report_path")
    if report_path and audit["orphan_images"]:
        print(
            f"  [audit] 孤儿图 {audit['orphan_images']} 张，整页候选 {audit['page_like_orphans']} 张 -> {report_path}"
        )
    elif report_path:
        print("  [audit] 未发现孤儿图")
    return audit


def run_math_command_audit(book_dir: Path) -> dict:
    report_path = book_dir / "_math_command_audit.md"
    audit = write_math_audit_report(book_dir, report_path)
    if audit["total_findings"]:
        print(
            f"  [math-audit] 命中 {audit['total_findings']} 个可疑数学命令，"
            f"涉及 {audit['files_with_findings']} 个文件 -> {report_path}"
        )
    else:
        print("  [math-audit] 未发现剩余可疑数学命令")
    return audit


def write_run_math_audit_summary(audits: list[dict]) -> Path | None:
    if not audits:
        return None

    summary_path = OUTPUT_DIR / "_math_command_audit_summary.md"
    total_findings = sum(audit["total_findings"] for audit in audits)
    total_books = len(audits)
    books_with_findings = sum(1 for audit in audits if audit["total_findings"])

    lines = [
        "# 本次 OCR 数学命令审计汇总",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- 本次书目数：`{total_books}`",
        f"- 命中可疑项书目：`{books_with_findings}`",
        f"- 可疑项总数：`{total_findings}`",
        "",
        "## 书目结果",
        "",
    ]

    for audit in audits:
        report_path = Path(audit["report_path"])
        rel_report = report_path.relative_to(OUTPUT_DIR)
        lines.append(
            f"- `{audit['book_name']}`：`{audit['total_findings']}` 项，"
            f"`{audit['files_with_findings']}` 个文件 -> `{rel_report}`"
        )

    lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[math-audit] 本次汇总 -> {summary_path}")
    return summary_path


def process_pdf(client: ZaiClient, pdf_path: Path, book_dir: Path,
                pages_per_md: int = None):
    """
    处理一个 PDF 文件。
    按 pages_per_md 切分，每段调 API，自动裁剪图片。
    使用 MAX_WORKERS 并发处理多个分段。
    """
    if pages_per_md is None:
        pages_per_md = PAGES_PER_MD_PDF

    total_pages = get_pdf_page_count(pdf_path)

    total_segments = -(-total_pages // pages_per_md)
    print(f"  共 {total_pages} 页，将输出 {total_segments} 个 .md 文件")

    images_dir = str(book_dir / "images")
    file_name = pdf_path.name

    # 收集待处理的分段
    pending = []
    skipped = 0
    for seg_start in range(0, total_pages, pages_per_md):
        seg_end = min(seg_start + pages_per_md, total_pages)
        page_label = f"{seg_start+1:04d}-{seg_end:04d}"
        md_filename = f"{clean_name(pdf_path.stem)}_{page_label}.md"
        md_path = book_dir / md_filename

        if md_path.exists():
            skipped += 1
        else:
            pending.append((seg_start, seg_end))

    if skipped > 0:
        print(f"  [跳过] {skipped} 个已完成的分段")

    if not pending:
        print(f"  [ok] 所有分段已完成")
        finalize_pdf_outputs(book_dir)
        return

    # 并发处理分段
    completed = 0
    failed_segs = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for seg_start, seg_end in pending:
            f = executor.submit(
                _process_one_segment, client, str(pdf_path),
                seg_start, seg_end, book_dir, images_dir, file_name
            )
            futures[f] = (seg_start, seg_end)

        for f in as_completed(futures):
            seg_start, seg_end = futures[f]
            try:
                f.result()
                completed += 1
            except Exception as e:
                _tprint(f"  [x] 段 {seg_start+1}-{seg_end} 处理失败: {e}")
                failed_segs += 1

    print(f"  [ok] 本次完成 {completed} 个分段" +
          (f"，失败 {failed_segs} 个" if failed_segs else ""))
    finalize_pdf_outputs(book_dir)


# ============================================================
# 处理图片
# ============================================================

def process_image(client: ZaiClient, img_path: Path, book_dir: Path):
    """处理一张图片（短图直传，长图自动分段）"""
    # 检查是否为长图
    try:
        img = Image.open(str(img_path))
        w, h = img.size
        img.close()
        if h > IMAGE_SEGMENT_HEIGHT:
            process_long_image(client, img_path, book_dir)
            return
    except Exception:
        pass

    md_path = book_dir / f"{img_path.stem}.md"

    if md_path.exists():
        repair_markdown_file(md_path)
        print(f"  [跳过] 已存在: {md_path.name}")
        return

    print(f"  调用 API...")
    resp, error = call_glm_ocr_raw(client, str(img_path))
    md_text = get_md_from_response(resp)

    if not has_meaningful_md_content(md_text):
        raise RuntimeError(
            f"图片 OCR 为空或只返回失败占位{(': ' + error) if error else ''}"
        )

    write_markdown_text(md_path, md_text)
    print(f"  [ok] 完成 -> {md_path.name}")


# ============================================================
# 主流程
# ============================================================

def process_file(client: ZaiClient, file_path: Path):
    """处理单个文件（PDF、PPTX/PPT 或图片），输出到对应子文件夹"""
    book_dir = OUTPUT_DIR / clean_name(file_path.stem)
    book_dir.mkdir(parents=True, exist_ok=True)
    ext = file_path.suffix.lower()

    if ext in (".pptx", ".ppt"):
        # PPT 先转 PDF 再处理
        cache_dir = PPT_PDF_CACHE_DIR / clean_name(file_path.stem)
        cache_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = cache_dir / f"{clean_name(file_path.stem)}.pdf"
        if not pdf_path.exists():
            print(f"  转换 PPT -> PDF...", flush=True)
            if not convert_ppt_to_pdf(str(file_path), str(pdf_path)):
                return
            print(f"  转换完成")
        process_pdf(client, pdf_path, book_dir, pages_per_md=PAGES_PER_MD_PPT)
    elif ext == ".pdf":
        process_pdf(client, file_path, book_dir, pages_per_md=PAGES_PER_MD_PDF)
    else:
        process_image(client, file_path, book_dir)

    math_audit = run_math_command_audit(book_dir)
    math_audit["book_name"] = book_dir.name
    return {
        "book_dir": book_dir,
        "math_audit": math_audit,
    }


def _batch_convert_ppts(ppt_files: list, converted_queue: queue.Queue,
                        done_event: threading.Event):
    """
    后台线程：批量将 PPT/PPTX 转为 PDF。
    复用单个 PowerPoint 实例（比每文件创建/销毁快得多）。
    转换完成的文件放入 converted_queue，供主线程 OCR。
    """
    import pythoncom
    pythoncom.CoInitialize()

    ppt_app = None
    try:
        import win32com.client
        ppt_app = win32com.client.Dispatch("PowerPoint.Application")
        ppt_app.Visible = True  # Must be True for PDF export

        for f in ppt_files:
            book_dir = OUTPUT_DIR / clean_name(f.stem)
            book_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = book_dir / f"{f.stem}.pdf"

            if pdf_path.exists():
                _tprint(f"  [PPT→PDF] {f.name} 已转换，跳过")
                converted_queue.put(f)
                continue

            try:
                abs_ppt = os.path.abspath(str(f))
                abs_pdf = os.path.abspath(str(pdf_path))
                pres = ppt_app.Presentations.Open(abs_ppt, WithWindow=False)
                pres.SaveAs(abs_pdf, 32)  # 32 = ppSaveAsPDF
                pres.Close()
                _tprint(f"  [PPT→PDF] {f.name} -> 转换完成")
                converted_queue.put(f)
            except Exception as e:
                _tprint(f"  [PPT→PDF] {f.name} 失败: {e}")

        ppt_app.Quit()
    except Exception as e:
        _tprint(f"  [!] PPT 转换器错误: {e}")
        if ppt_app:
            try:
                ppt_app.Quit()
            except Exception:
                pass
    finally:
        pythoncom.CoUninitialize()
        done_event.set()


def main():
    parser = argparse.ArgumentParser(description="GLM-OCR 批量文档识别")
    parser.add_argument("--handwrite", action="store_true",
                        help="使用手写识别模式（ZhipuAI handwriting_ocr）")
    args = parser.parse_args()

    check_config()
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(exist_ok=True)
    PPT_PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    mode = "手写识别" if args.handwrite else "GLM-OCR"

    if args.handwrite:
        hw_client = ZhipuAiClient(api_key=API_KEY)
        print(f"[ok] 手写识别客户端已初始化（ZhipuAiClient）")
    else:
        client = ZaiClient(api_key=API_KEY)
        print(f"[ok] API 客户端已初始化")

    print(f"[ok] 模式: {mode}")
    print(f"[ok] 输入文件夹: {INPUT_DIR}")
    print(f"[ok] 输出文件夹: {OUTPUT_DIR}")
    print(f"[ok] PDF 每 {PAGES_PER_MD_PDF} 页一个 .md, PPT 每 {PAGES_PER_MD_PPT} 页一个 .md")

    # 收集待处理文件（按文件名排序，支持优先级前缀）
    def _sort_key(f):
        """按前缀分优先级：凸优化 > 操作系统 > 信号与系统 > 其他 > (101)课件"""
        name = f.name
        if name.startswith("凸优化"):
            return (0, name)
        elif name.startswith("操作系统"):
            return (1, name)
        elif name.startswith("信号与系统"):
            return (2, name)
        elif name.startswith("(101)") and f.suffix.lower() == ".pdf":
            return (3, name)
        elif name.startswith("(101)"):
            return (4, name)
        else:
            return (5, name)

    files = sorted(
        (f for f in INPUT_DIR.iterdir()
         if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS),
        key=_sort_key
    )

    if not files:
        print(f"\n[!] input 文件夹为空，请将 PDF/PPT/图片 放入: {INPUT_DIR}")
        return

    total = len(files)

    # ---- 手写识别模式：简单顺序处理 ----
    if args.handwrite:
        print(f"\n找到 {total} 个文件:")
        for f in files:
            print(f"  - {f.name}")

        print(f"\n{'='*50}")
        print("开始手写识别")
        print(f"{'='*50}\n")

        success, failed = 0, 0
        run_math_audits: list[dict] = []
        start_time = time.time()

        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{total}] {file_path.name}")
            try:
                result = process_handwrite_file(hw_client, file_path)
                if result and result.get("math_audit"):
                    run_math_audits.append(result["math_audit"])
                success += 1
            except Exception as e:
                print(f"  [x] 处理失败: {e}")
                failed += 1
            print()

        elapsed = time.time() - start_time
        minutes, seconds = int(elapsed // 60), int(elapsed % 60)

        print(f"{'='*50}")
        print(f"手写识别完毕!")
        print(f"  成功: {success}")
        if failed:
            print(f"  失败: {failed}")
        print(f"  耗时: {minutes}分{seconds}秒")
        print(f"  输出: {OUTPUT_DIR}")
        print(f"{'='*50}")
        write_run_math_audit_summary(run_math_audits)
        return

    # ---- 标准 GLM-OCR 模式 ----

    # 分离：可直接 OCR 的文件 vs 需要先转 PDF 的 PPT 文件
    ready_files = []
    ppt_files = []
    for f in files:
        if f.suffix.lower() in (".ppt", ".pptx"):
            ppt_files.append(f)
        else:
            ready_files.append(f)

    print(f"\n找到 {total} 个文件（{len(ready_files)} 个可直接 OCR，"
          f"{len(ppt_files)} 个 PPT 需转换）:")
    for f in files:
        tag = " [PPT]" if f.suffix.lower() in (".ppt", ".pptx") else ""
        print(f"  - {f.name}{tag}")

    # ---- 后台启动 PPT→PDF 批量转换 ----
    converted_queue = queue.Queue()
    converter_done = threading.Event()

    if ppt_files:
        converter_thread = threading.Thread(
            target=_batch_convert_ppts,
            args=(ppt_files, converted_queue, converter_done),
            daemon=True,
        )
        converter_thread.start()
        print(f"\n[ok] 后台开始转换 {len(ppt_files)} 个 PPT 文件（与 OCR 并行）")
    else:
        converter_done.set()

    print(f"\n{'='*50}")
    print("开始批量识别")
    print(f"{'='*50}\n")

    success, failed = 0, 0
    done = 0
    run_math_audits: list[dict] = []
    start_time = time.time()

    def _process_converted_ppts():
        """处理所有已转换完成的 PPT（从队列中取出）"""
        nonlocal done, success, failed, run_math_audits
        while not converted_queue.empty():
            try:
                f = converted_queue.get_nowait()
            except queue.Empty:
                break
            done += 1
            print(f"[{done}/{total}] {f.name}")
            try:
                result = process_file(client, f)
                if result and result.get("math_audit"):
                    run_math_audits.append(result["math_audit"])
                success += 1
            except Exception as e:
                print(f"  [x] 处理失败: {e}")
                failed += 1
            print()

    # ---- 阶段 1：先处理可直接 OCR 的文件（PDF / 图片）----
    for file_path in ready_files:
        done += 1
        print(f"[{done}/{total}] {file_path.name}")
        try:
            result = process_file(client, file_path)
            if result and result.get("math_audit"):
                run_math_audits.append(result["math_audit"])
            success += 1
        except Exception as e:
            print(f"  [x] 处理失败: {e}")
            failed += 1
        print()

        # 每处理完一个，检查是否有 PPT 已转换好，随到随处理
        _process_converted_ppts()

    # ---- 阶段 2：等待剩余 PPT 转换完成并处理 ----
    if ppt_files and not converter_done.is_set():
        print(f"[等待] PDF/图片已全部 OCR 完毕，等待剩余 PPT 转换...")
        while not converter_done.is_set():
            converter_done.wait(timeout=2)
            _process_converted_ppts()

    # 处理最后一批
    _process_converted_ppts()

    elapsed = time.time() - start_time
    minutes, seconds = int(elapsed // 60), int(elapsed % 60)

    print(f"{'='*50}")
    print(f"处理完毕!")
    print(f"  成功: {success}")
    if failed:
        print(f"  失败: {failed}")
    print(f"  耗时: {minutes}分{seconds}秒")
    print(f"  输出: {OUTPUT_DIR}")
    print(f"{'='*50}")
    write_run_math_audit_summary(run_math_audits)


if __name__ == "__main__":
    main()
