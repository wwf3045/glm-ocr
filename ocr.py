"""
GLM-OCR 批量文档识别脚本
=========================
将 PDF/PPT/PPTX/图片放入 input 文件夹，运行此脚本即可在 output 文件夹中获取 Markdown 结果。

功能：
- PDF 按固定页数切分，每段直传 API，每段输出一个 .md 文件
- PDF 直传返回空时自动回退为逐页转图片模式
- PPT/PPTX 通过 COM 自动化转为 PDF 后处理
- 自动裁剪 API 标注的图片区域，保存到 images 文件夹
- 支持超长截图（微信长截图等），自动分段识别后合并
- 断点续扫：已处理过的分段自动跳过
- 失败自动重试 3 次
"""

import base64
import io
import os
import queue
import re
import sys
import time
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Windows 下强制 UTF-8 输出，避免 GBK 编码错误
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
from zai import ZaiClient

# ============================================================
# 配置
# ============================================================
load_dotenv()
API_KEY = os.getenv("GLM_API_KEY", "")

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"

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
    doc = fitz.open(pdf_path)
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
    new_doc.save(out_path)
    new_doc.close()
    doc.close()


def pdf_pages_to_images(pdf_path: str, start: int, end: int, temp_dir: str) -> list[str]:
    """将 PDF 的 [start, end) 页渲染为 PNG，返回图片路径列表"""
    doc = fitz.open(pdf_path)
    zoom = FALLBACK_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    paths = []
    for i in range(start, end):
        pix = doc[i].get_pixmap(matrix=matrix)
        p = os.path.join(temp_dir, f"page_{i+1:04d}.png")
        pix.save(p)
        paths.append(p)
    doc.close()
    return paths


def file_to_data_uri(file_path: str) -> str:
    """将本地文件转为 base64 data URI"""
    ext = os.path.splitext(file_path)[1].lower()
    mime = MIME_MAP.get(ext, "application/octet-stream")
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:{mime};base64,{b64}"


def call_glm_ocr_raw(client: ZaiClient, file_path: str):
    """调用 GLM-OCR API，返回完整响应对象，带重试机制"""
    data_uri = file_to_data_uri(file_path)
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            return client.layout_parsing.create(
                model="glm-ocr",
                file=data_uri,
            )
        except Exception as e:
            _tprint(f"    [!] 第 {attempt} 次调用失败: {e}")
            if attempt < RETRY_TIMES:
                _tprint(f"    等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
            else:
                _tprint(f"    [x] 已达最大重试次数，跳过此段")
                return None


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


def replace_bbox_images(md_text: str, pdf_path: str, seg_start: int,
                        images_dir: str, page_sizes: dict) -> str:
    """
    将 md_results 中的 ![](page=X,bbox=[x0,y0,x1,y1]) 替换为实际裁剪的图片。
    page_sizes: 从 API layout_details 获取的每页渲染尺寸 {page_idx: (w, h)}
    """
    pattern = re.compile(r"!\[([^\]]*)\]\(page=(\d+),bbox=\[([^\]]+)\]\)")
    if not pattern.search(md_text):
        return md_text

    doc = fitz.open(pdf_path)
    os.makedirs(images_dir, exist_ok=True)
    img_count = 0

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

        # 获取该页的 API 渲染尺寸
        api_size = page_sizes.get(page_in_seg)
        if not api_size:
            for s in page_sizes.values():
                api_size = s
                break
            if not api_size:
                api_size = (2040, 2520)

        api_w, api_h = api_size
        page = doc[real_page]
        rect = page.rect

        # 将 API bbox 换算到 PDF 坐标
        sx = rect.width / api_w
        sy = rect.height / api_h
        x0, y0, x1, y1 = coords
        clip = fitz.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)

        # 用 3x 缩放裁剪，约 216dpi
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip)
        if pix.width < 5 or pix.height < 5:
            return match.group(0)

        img_count += 1
        img_name = f"p{real_page+1:04d}_fig{img_count:04d}.png"
        pix.save(os.path.join(images_dir, img_name))

        label = f"第{real_page+1}页-图{img_count}"
        return f"![{label}](images/{img_name})"

    new_text = pattern.sub(replace_match, md_text)
    doc.close()

    if img_count > 0:
        _tprint(f"    提取了 {img_count} 张图片")

    return new_text


def call_glm_ocr_with_fallback(client: ZaiClient, pdf_path: str,
                                start: int, end: int, temp_dir: str):
    """
    先用 PDF 直传调 API；如果返回空，自动回退为逐页转图片模式。
    返回 (md_text, page_sizes)
    """
    seg_pdf = os.path.join(temp_dir, f"seg_{start+1}-{end}.pdf")
    extract_pdf_segment(pdf_path, start, end, seg_pdf)
    resp = call_glm_ocr_raw(client, seg_pdf)
    md_text = get_md_from_response(resp)
    page_sizes = get_api_page_sizes(resp) if resp else {}

    if md_text.strip():
        return md_text, page_sizes

    # 回退：逐页转图片
    _tprint(f"    PDF 直传返回空，回退为图片模式...", flush=True)
    img_paths = pdf_pages_to_images(pdf_path, start, end, temp_dir)
    page_results = []
    for j, img_path in enumerate(img_paths):
        _tprint(f"    第 {start+j+1} 页(图片模式)...", flush=True)
        resp_img = call_glm_ocr_raw(client, img_path)
        page_results.append(get_md_from_response(resp_img))
        if j < len(img_paths) - 1:
            time.sleep(0.5)
    return "\n\n".join(page_results), {}


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
            return get_md_from_response(resp)
        except Exception as e:
            _tprint(f"    [!] 第 {attempt} 次调用失败: {e}")
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY)
            else:
                return None


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
            results.append(seg_md.read_text(encoding="utf-8"))
            continue

        print(f"  段 {i + 1}/{total}...", flush=True)
        img_b64 = pil_to_base64(seg)
        result = ocr_single_image_b64(client, img_b64)

        if result:
            seg_md.write_text(result, encoding="utf-8")
            results.append(result)
            print(f"  段 {i + 1} 完成")
        else:
            print(f"  段 {i + 1} 失败！")

    img.close()

    # 合并所有段为单个 md（如果多于1段）
    if len(results) > 1:
        merged_path = book_dir / f"{file_path.stem}.md"
        merged_path.write_text("\n\n".join(results), encoding="utf-8")
        print(f"  已合并 {len(results)} 段 -> {file_path.stem}.md")


# ============================================================
# 处理 PDF（支持并发）
# ============================================================

def _process_one_segment(client: ZaiClient, pdf_path: str, seg_start: int,
                         seg_end: int, book_dir: Path, images_dir: str,
                         file_name: str):
    """处理 PDF 的一个分段（供线程池调用）"""
    page_label = f"{seg_start+1:04d}-{seg_end:04d}"
    md_filename = f"{clean_name(Path(pdf_path).stem)}_{page_label}.md"
    md_path = book_dir / md_filename

    _tprint(f"  [{seg_start+1}-{seg_end}] 调用 API...", flush=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        md_text, page_sizes = call_glm_ocr_with_fallback(
            client, pdf_path, seg_start, seg_end, temp_dir
        )

    # 将 ![](page=X,bbox=[...]) 替换为实际裁剪的图片
    md_text = replace_bbox_images(md_text, pdf_path, seg_start,
                                   images_dir, page_sizes)

    # 加元信息注释头
    header = f"<!-- PDF页码: {seg_start+1}-{seg_end} | 文件: {file_name} -->\n\n"
    md_path.write_text(header + md_text, encoding="utf-8")

    _tprint(f"    -> {md_filename}")
    return md_filename


def process_pdf(client: ZaiClient, pdf_path: Path, book_dir: Path,
                pages_per_md: int = None):
    """
    处理一个 PDF 文件。
    按 pages_per_md 切分，每段调 API，自动裁剪图片。
    使用 MAX_WORKERS 并发处理多个分段。
    """
    if pages_per_md is None:
        pages_per_md = PAGES_PER_MD_PDF

    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    doc.close()

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

    # 清理空的 images 文件夹
    if os.path.isdir(images_dir) and not os.listdir(images_dir):
        os.rmdir(images_dir)

    print(f"  [ok] 本次完成 {completed} 个分段" +
          (f"，失败 {failed_segs} 个" if failed_segs else ""))


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
        print(f"  [跳过] 已存在: {md_path.name}")
        return

    print(f"  调用 API...")
    resp = call_glm_ocr_raw(client, str(img_path))
    md_text = get_md_from_response(resp)

    md_path.write_text(md_text, encoding="utf-8")
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
        pdf_path = book_dir / f"{file_path.stem}.pdf"
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
    check_config()
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    client = ZaiClient(api_key=API_KEY)
    print(f"[ok] API 客户端已初始化")
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

    # 分离：可直接 OCR 的文件 vs 需要先转 PDF 的 PPT 文件
    ready_files = []
    ppt_files = []
    for f in files:
        if f.suffix.lower() in (".ppt", ".pptx"):
            ppt_files.append(f)
        else:
            ready_files.append(f)

    total = len(files)
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
    start_time = time.time()

    def _process_converted_ppts():
        """处理所有已转换完成的 PPT（从队列中取出）"""
        nonlocal done, success, failed
        while not converted_queue.empty():
            try:
                f = converted_queue.get_nowait()
            except queue.Empty:
                break
            done += 1
            print(f"[{done}/{total}] {f.name}")
            try:
                process_file(client, f)
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
            process_file(client, file_path)
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


if __name__ == "__main__":
    main()
