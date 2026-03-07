"""
GLM-OCR 核心脚本
将 input/ 下的 PDF/PPT/PPTX/图片 通过 GLM-4v-flash API 逐段 OCR，输出 Markdown 到 output/
支持超长截图（如微信聊天记录长截图），自动分段识别后合并。
"""
import os
import sys
import io
import base64
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

import fitz  # PyMuPDF
from PIL import Image
from zhipuai import ZhipuAI

INPUT_DIR = "input"
OUTPUT_DIR = "output"
PDF_SEGMENT_SIZE = 20   # PDF 每段页数
PPT_SEGMENT_SIZE = 50   # PPT 每段页数
IMAGE_SEGMENT_HEIGHT = 4000  # 长图每段高度（像素）
IMAGE_OVERLAP = 200          # 相邻段重叠像素（避免截断文字）
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

OCR_PROMPT = """请将这些页面的内容完整转换为 Markdown 格式。要求：
1. 保留所有文字内容，不要遗漏
2. 数学公式使用 LaTeX 格式（行内用 $...$，独立公式用 $$...$$）
3. 保留标题层级结构
4. 表格使用 Markdown 表格语法
5. 图片中的文字也要识别
6. 保持原文的段落结构"""


def get_client():
    api_key = os.getenv("GLM_API_KEY")
    if not api_key:
        print("错误：请在 .env 文件中设置 GLM_API_KEY")
        sys.exit(1)
    return ZhipuAI(api_key=api_key)


def ppt_to_pdf(ppt_path):
    """通过 LibreOffice 将 PPT/PPTX 转换为 PDF"""
    output_dir = os.path.dirname(ppt_path)
    try:
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf",
             "--outdir", output_dir, ppt_path],
            check=True, capture_output=True, timeout=120,
        )
        pdf_name = Path(ppt_path).stem + ".pdf"
        return os.path.join(output_dir, pdf_name)
    except Exception as e:
        print(f"  PPT 转 PDF 失败：{e}")
        return None


def page_to_base64(page):
    """将 PDF 页面渲染为 base64 图片"""
    pix = page.get_pixmap(dpi=200)
    img_bytes = pix.tobytes("png")
    return base64.b64encode(img_bytes).decode()


def extract_images(doc, page_idx, output_images_dir):
    """提取页面中的 bbox 图片"""
    page = doc[page_idx]
    images = page.get_images(full=True)
    for img_idx, img_info in enumerate(images):
        xref = img_info[0]
        try:
            base_image = doc.extract_image(xref)
            img_bytes = base_image["image"]
            img_ext = base_image["ext"]
            if len(img_bytes) < 1024:  # 跳过太小的图片
                continue
            img_name = f"page_{page_idx + 1}_img_{img_idx + 1}.{img_ext}"
            img_path = os.path.join(output_images_dir, img_name)
            with open(img_path, "wb") as f:
                f.write(img_bytes)
        except Exception:
            pass


def ocr_segment_images(client, doc, start, end):
    """逐页转图片上传 OCR（回退模式）"""
    content = [{"type": "text", "text": OCR_PROMPT}]
    for i in range(start, min(end, len(doc))):
        img_b64 = page_to_base64(doc[i])
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
        })

    try:
        response = client.chat.completions.create(
            model="glm-4v-flash",
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"    OCR 失败（图片模式）：{e}")
        return None


def ocr_segment_file(client, pdf_path, start, end):
    """整段 PDF 上传 OCR（优先模式）"""
    # 提取段落为临时 PDF
    doc = fitz.open(pdf_path)
    tmp_doc = fitz.open()
    for i in range(start, min(end, len(doc))):
        tmp_doc.insert_pdf(doc, from_page=i, to_page=i)

    tmp_path = f"_tmp_segment_{start}_{end}.pdf"
    tmp_doc.save(tmp_path)
    tmp_doc.close()
    doc.close()

    try:
        # 上传文件
        with open(tmp_path, "rb") as f:
            file_obj = client.files.create(file=f, purpose="file-extract")
        file_content = client.files.content(file_id=file_obj.id)
        content_text = file_content.content if hasattr(file_content, 'content') else str(file_content)

        # 用提取的内容请求格式化
        response = client.chat.completions.create(
            model="glm-4-flash",
            messages=[
                {"role": "system", "content": content_text},
                {"role": "user", "content": OCR_PROMPT},
            ],
        )
        os.remove(tmp_path)
        return response.choices[0].message.content
    except Exception as e:
        print(f"    文件上传模式失败（{e}），切换为图片模式...")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return None


IMAGE_OCR_PROMPT = """请将这张图片中的所有文字内容完整转换为 Markdown 格式。要求：
1. 保留所有文字内容，不要遗漏任何一行
2. 数学公式使用 LaTeX 格式（行内用 $...$，独立公式用 $$...$$）
3. 保留标题层级和段落结构
4. 如果是聊天记录截图，保留发言人和时间信息
5. 如果是网页截图，保留标题、正文和列表结构
6. 保持原文的段落和换行结构"""


def pil_to_base64(img, fmt="PNG"):
    """将 PIL Image 转为 base64"""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode()


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


def ocr_single_image(client, img_b64):
    """发送单张图片到 GLM-4v-flash OCR"""
    content = [
        {"type": "text", "text": IMAGE_OCR_PROMPT},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
    ]
    try:
        response = client.chat.completions.create(
            model="glm-4v-flash",
            messages=[{"role": "user", "content": content}],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"    OCR 失败：{e}")
        return None


def process_image(client, file_path):
    """处理单张图片文件（支持超长截图自动分段）"""
    fname = Path(file_path).stem
    out_dir = os.path.join(OUTPUT_DIR, fname)
    os.makedirs(out_dir, exist_ok=True)

    img = Image.open(file_path)
    w, h = img.size
    segments = split_long_image(img)
    total = len(segments)
    print(f"  尺寸 {w}x{h}，分 {total} 段处理")

    for i, seg in enumerate(segments):
        seg_file = os.path.join(out_dir, f"segment_{i + 1}.md")

        # 断点续传
        if os.path.exists(seg_file) and os.path.getsize(seg_file) > 0:
            print(f"  段 {i + 1}/{total} 已完成，跳过")
            continue

        print(f"  段 {i + 1}/{total}（y={i * (IMAGE_SEGMENT_HEIGHT - IMAGE_OVERLAP)}-{min((i + 1) * IMAGE_SEGMENT_HEIGHT - i * IMAGE_OVERLAP, h)}）...")
        img_b64 = pil_to_base64(seg)
        result = ocr_single_image(client, img_b64)

        if result:
            with open(seg_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"  段 {i + 1} 完成")
        else:
            print(f"  段 {i + 1} 失败！")

    img.close()

    # 合并所有段为单个 md（如果多于1段）
    seg_files = sorted(
        [f for f in os.listdir(out_dir) if f.startswith("segment_") and f.endswith(".md")],
        key=lambda x: int(x.split("_")[1].split(".")[0])
    )
    if len(seg_files) > 1:
        merged_path = os.path.join(out_dir, f"{fname}.md")
        with open(merged_path, "w", encoding="utf-8") as out:
            for sf in seg_files:
                with open(os.path.join(out_dir, sf), "r", encoding="utf-8") as inp:
                    out.write(inp.read())
                out.write("\n\n")
        print(f"  已合并 {len(seg_files)} 段 → {fname}.md")

    # 删除源文件
    os.remove(file_path)
    print(f"  已删除源文件：{os.path.basename(file_path)}")


def process_file(client, file_path):
    """处理单个文件"""
    fname = Path(file_path).stem
    ext = Path(file_path).suffix.lower()

    # PPT 先转 PDF
    actual_pdf = file_path
    if ext in (".ppt", ".pptx"):
        print(f"  转换 PPT → PDF...")
        actual_pdf = ppt_to_pdf(file_path)
        if not actual_pdf:
            return

    doc = fitz.open(actual_pdf)
    total_pages = len(doc)
    segment_size = PPT_SEGMENT_SIZE if ext in (".ppt", ".pptx") else PDF_SEGMENT_SIZE

    # 输出目录
    out_dir = os.path.join(OUTPUT_DIR, fname)
    images_dir = os.path.join(out_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    segments = (total_pages + segment_size - 1) // segment_size
    print(f"  共 {total_pages} 页，分 {segments} 段处理")

    for seg in range(segments):
        start = seg * segment_size
        end = min(start + segment_size, total_pages)
        seg_file = os.path.join(out_dir, f"segment_{seg + 1}.md")

        # 断点续传
        if os.path.exists(seg_file) and os.path.getsize(seg_file) > 0:
            print(f"  段 {seg + 1}/{segments} 已完成，跳过")
            continue

        print(f"  段 {seg + 1}/{segments}（第 {start + 1}-{end} 页）...")

        # 提取图片
        for i in range(start, end):
            extract_images(doc, i, images_dir)

        # 优先尝试文件上传模式
        result = ocr_segment_file(client, actual_pdf, start, end)

        # 回退到图片模式
        if result is None:
            result = ocr_segment_images(client, doc, start, end)

        if result:
            with open(seg_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"  段 {seg + 1} 完成")
        else:
            print(f"  段 {seg + 1} 失败！")

    doc.close()

    # 清理临时 PDF
    if ext in (".ppt", ".pptx") and actual_pdf != file_path:
        os.remove(actual_pdf)

    # 删除源文件
    os.remove(file_path)
    print(f"  已删除源文件：{os.path.basename(file_path)}")


def main():
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    supported = (".pdf", ".ppt", ".pptx") + IMAGE_EXTENSIONS
    files = [
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith(supported)
    ]
    if not files:
        print(f"未找到文件，请将 PDF/PPT/图片 放入 {INPUT_DIR}/ 目录")
        return

    client = get_client()
    print(f"找到 {len(files)} 个文件")

    for fname in files:
        file_path = os.path.join(INPUT_DIR, fname)
        stem = Path(fname).stem
        ext = Path(fname).suffix.lower()
        out_dir = os.path.join(OUTPUT_DIR, stem)

        # 已处理过的跳过
        if os.path.exists(out_dir) and any(
            f.endswith(".md") for f in os.listdir(out_dir)
        ):
            print(f"跳过（已有输出）：{fname}")
            continue

        print(f"处理：{fname}")
        try:
            if ext in IMAGE_EXTENSIONS:
                process_image(client, file_path)
            else:
                process_file(client, file_path)
        except Exception as e:
            print(f"  错误：{e}")

    print("全部完成！")


if __name__ == "__main__":
    main()
