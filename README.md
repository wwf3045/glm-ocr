English | [简体中文](README_CN.md)

# GLM-OCR

Batch convert PDF / PPT / images to Markdown using [ZhipuAI GLM-4v-flash](https://open.bigmodel.cn/) API. Outputs clean Markdown with LaTeX math formulas.

## Why GLM?

As of early 2026, ZhipuAI's GLM-OCR is the **top-performing model for structured document OCR** ([OmniDocBench v1.5](https://github.com/opendatalab/OmniDocBench)), especially for converting PDF to Markdown. Here's how it compares:

| Solution | Strengths | Weaknesses |
|----------|-----------|------------|
| **GLM-OCR** | Best Markdown structure output, semantic understanding of cross-page tables and complex layouts, ~2 pages/sec, low VRAM (2-3GB), VLLM acceleration | Hallucination on blurry text (guesses plausible values instead of returning garbage), weak on distorted/crumpled paper |
| **PaddleOCR v1.5** | Best for physically distorted images (receipts, crumpled paper, skewed photos), pixel-level precision | Deployment nightmare (CUDA conflicts, dependency hell), weak at logical document restructuring |
| **MinerU** | Good open-source document parser | Requires local GPU deployment, heavy dependencies |

**Why cloud API instead of local models?** This project is designed for **individual users** (students, researchers) who don't need to process thousands of documents. Cloud API means zero GPU requirements, no CUDA setup, no model downloads — just `pip install` and go. Local deployment (PaddleOCR, MinerU) only makes sense for enterprises with dedicated GPU servers and massive batch processing needs.

**Bottom line**: If your input is clean digital documents (PDF, PPT, screenshots), GLM-OCR produces the cleanest Markdown output with minimal post-processing — ideal for RAG knowledge bases and study notes. For physically damaged or handwritten documents, consider PaddleOCR or Claude/GPT.

> Reference: [OCR model comparison (2026.02)](https://www.bilibili.com/video/BV1GYF7z9E7n/) by [@从零开始学AI](https://space.bilibili.com/91394217)

## Features

- **PDF / PPT / PPTX -> Markdown**: segment-based OCR with automatic fallback (file upload -> per-page image)
- **Long screenshot support**: auto-splits tall images (e.g. chat screenshots) into overlapping segments (text OCR only, no image extraction)
- **Resume from breakpoint**: already-completed segments are skipped on re-run
- **Image extraction**: embedded images are saved to `images/` subfolder
- **Junk image cleaner**: removes common artifacts (background images, tiny icons) from OCR output
- **Math formula support**: LaTeX output (`$...$` inline, `$$...$$` block)

## Quick Start

### 1. Get API Key

Register at [ZhipuAI Open Platform](https://open.bigmodel.cn/) and create an API key.

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure

Create a `.env` file in the project root:

```
GLM_API_KEY=your_api_key_here
```

### 4. Run

```bash
# Put PDF/PPT/images in input/ directory
python ocr.py
# Markdown output in output/
```

## Output Structure

```
output/
└── filename/
    ├── segment_1.md      # Pages 1-20
    ├── segment_2.md      # Pages 21-40
    ├── ...
    └── images/           # Extracted images
        ├── page_3_img_1.png
        └── ...
```

## Clean Junk Images

```bash
python clean_junk_images.py
```

Removes common OCR artifacts (background images ~3.2MB, icons <3KB) and cleans up Markdown references.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PDF_SEGMENT_SIZE` | 20 | Pages per segment for PDF |
| `PPT_SEGMENT_SIZE` | 50 | Pages per segment for PPT |
| `IMAGE_SEGMENT_HEIGHT` | 4000px | Max height per segment for long images |
| `IMAGE_OVERLAP` | 200px | Overlap between adjacent image segments |

## Use Cases

- Convert lecture slides / textbooks to Markdown for note-taking and RAG knowledge bases
- **WeChat chat export via screenshots**: taking long screenshots is a safer alternative to third-party export tools (no API abuse, no risk of ToS violations). OCR the screenshots into text, then feed to AI for personal assistant training
- Batch digitize scanned documents
- Extract text from web page screenshots

## Requirements

- Python 3.8+
- [ZhipuAI API key](https://open.bigmodel.cn/) (GLM-4v-flash is free-tier)
- LibreOffice (only for PPT/PPTX conversion)

## Known Limitations

- **Hallucination**: GLM may guess plausible values for blurry text instead of returning errors — avoid for financial/medical documents requiring exact precision
- **Repetition bug**: Occasionally loops on dense Excel screenshots, repeating the same row
- **Handwriting**: Weak on handwritten content — use Claude or GPT instead
- PPT/PPTX files are first converted to PDF via LibreOffice before OCR
- Source files are automatically deleted from `input/` after successful processing

## License

MIT
