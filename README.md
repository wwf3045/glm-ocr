English | [简体中文](README_CN.md)

# GLM-OCR — PDF/PPT/Image to Markdown OCR Converter

Batch convert documents to clean Markdown using [ZhipuAI GLM-4v-flash](https://open.bigmodel.cn/) API — the [#1 OCR model on OmniDocBench v1.5](https://opendatalab.com/omnidocbench) as of early 2026. Zero GPU required, LaTeX math support, resume from breakpoint.

## Features

- **PDF / PPT / PPTX -> Markdown**: segment-based OCR with automatic fallback (file upload -> per-page image)
- **Long screenshot support**: auto-splits tall images (e.g. chat screenshots) into overlapping segments (text OCR only, no image extraction)
- **Resume from breakpoint**: already-completed segments are skipped on re-run
- **Image extraction**: embedded images are saved to `images/` subfolder
- **Junk image cleaner**: removes common artifacts (background images, tiny icons) from OCR output
- **Math formula support**: LaTeX output (`$...$` inline, `$$...$$` block)

## Use Cases

- Convert lecture slides / textbooks to Markdown for note-taking and RAG knowledge bases
- **WeChat chat export via screenshots**: taking long screenshots is a safer alternative to third-party export tools (no API abuse, no risk of ToS violations). OCR the screenshots into text, then feed to AI for personal assistant training
- Batch digitize scanned documents
- Extract text from web page screenshots

## Why GLM?

The [OmniDocBench v1.5](https://opendatalab.com/omnidocbench) benchmark ([GitHub](https://github.com/opendatalab/OmniDocBench)) is the most comprehensive OCR evaluation. As of early February 2026, GLM-OCR ranked **#1** in a 5-model head-to-head test (vs DeepSeek OCR2, MinerU, PaddleOCR VL, PaddleOCR VL 1.5). Around late February 2026, [Unisound U1](https://www.prnewswire.com/news-releases/unisound-u1-ocr-the-first-industrial-grade-document-intelligence-foundation-model-ushering-in-the-ocr-3-0-era-302698482.html) surpassed GLM-OCR on the leaderboard (95.1 vs 94.62), particularly excelling in medical/clinical document scenarios.

### Pricing

GLM-OCR API starts at just **¥2.9** (~$0.40 / €0.37) for 50 million tokens via [ZhipuAI special deals](https://bigmodel.cn/special_area) — enough to OCR **~60 textbooks** (300 pages each). Standard rate: ¥0.2/M tokens (~$0.03 / €0.03), roughly 1/100 the cost of GPT-4o Vision.

> Full pricing tiers → [Appendix: API Pricing](#appendix-api-pricing-details)

### Comparison Summary

| Solution | OmniDocBench v1.5 | Best For | Weaknesses | Deployment |
|----------|--------------------|----------|------------|------------|
| **Unisound U1** (Unisound / 云知声) | **95.1** | Medical/clinical docs, field-level positioning & traceability, 50+ doc types (99%+ classification), extreme scenarios (blurred, multilingual) | Newer, less community testing, no public API pricing yet | Cloud API / On-premise |
| **GLM-OCR** (ZhipuAI / 智谱) | **94.62** | Structured documents, formulas, domain-specific text. 0.9B params, ~1.86 pages/sec, API ~0.2 CNY/M tokens (1/10 of traditional OCR) | Cannot extract images, no bounding box, hallucination on blurry text | Cloud API / VLLM local |
| **PaddleOCR VL 1.5** (Baidu / 百度) | **94.5** | Handwriting, tables, distorted images | CUDA dependency hell, weak at logical restructuring | Local GPU only |
| **MinerU** (OpenDataLab) | — | Clean PDFs with simple layout | Character errors on complex layouts | Local GPU only |
| **DeepSeek OCR2** (DeepSeek / 深度求索) | — | Tables (zero info loss) | Formula errors, images discarded | Cloud API |

### Why Cloud API?

This project is designed for **individual users** (students, researchers) who don't need to process thousands of documents. Cloud API means zero GPU requirements, no CUDA setup, no model downloads — just `pip install` and go. Local deployment only makes sense for enterprises with dedicated GPU servers.

The script architecture is model-agnostic — swapping to a different API (DeepSeek, Unisound U1, etc.) only requires changing the API client and model name in `ocr.py`.

> References:
> - [5-model OCR benchmark with detailed test cases (2026.02)](https://www.bilibili.com/video/BV1UjFjz1EdD/) by [@AI创客空间](https://space.bilibili.com/396997624)
> - [OCR model selection guide (2026.02)](https://www.bilibili.com/video/BV1GYF7z9E7n/) by [@从零开始学AI](https://space.bilibili.com/91394217)
> - [OmniDocBench v1.5 benchmark](https://github.com/opendatalab/OmniDocBench)
> - [Unisound U1 OCR announcement](https://www.bilibili.com/video/BV1rqAUzAE4z/)

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

---

## Appendix: Detailed Benchmark Test Results

> Source: [5-model OCR benchmark (2026.02)](https://www.bilibili.com/video/BV1UjFjz1EdD/) by [@AI创客空间](https://space.bilibili.com/396997624)

<details>
<summary>Click to expand</summary>

**Test 1 — Math-heavy PDF (formulas & equations)**:
| Model | Result |
|-------|--------|
| GLM-OCR | Formula hierarchy perfectly restored, complete layout with chapter titles |
| PaddleOCR VL 1.5 | Zero errors, equivalent LaTeX notation |
| MinerU | Zero text errors, complete LaTeX structure |
| DeepSeek OCR2 | Formula symbols missing, content loss |

**Test 2 — Complex magazine (images, blurry fonts, mixed layout)**:
| Model | Result |
|-------|--------|
| GLM-OCR | Only model to correctly identify all biological terms (e.g. "hemocyanin", "copper ions") |
| PaddleOCR VL 1.5 | Close but misread specialized terminology |
| MinerU | Many character errors on domain-specific terms |
| DeepSeek OCR2 | Text mostly correct but images discarded, page numbers lost |

**Test 3 — Handwritten vertical Chinese calligraphy**:
| Model | Result |
|-------|--------|
| PaddleOCR VL | Zero errors, all 10 lines perfectly recognized |
| GLM-OCR | Correct reading order, mostly accurate, but missed one character |
| MinerU | Correct order but weak on calligraphic forms |
| DeepSeek OCR2 | Completely wrong reading order |

**Test 4 — Complex handwritten table (checkboxes, handwritten numbers)**:
| Model | Result |
|-------|--------|
| PaddleOCR VL 1.5 | Best overall — handwritten digits correct, checkboxes detected, clean structure |
| GLM-OCR | Handwritten digits all correct, table format correct, but header info lost |
| MinerU | Table recognition completely wrong |
| DeepSeek OCR2 | Zero info loss but table separated from header |

</details>

---

## Appendix: API Pricing Details

> Source: [ZhipuAI Special Deals](https://bigmodel.cn/special_area) · [Standard Pricing](https://bigmodel.cn/pricing) (as of March 2026)

<details>
<summary>Click to expand</summary>

| Tier | Package | Price | Per M tokens | Limit |
|------|---------|-------|--------------|-------|
| **Flash sale** | 50M tokens / 3 months | ¥2.9 ($0.40 / €0.37) | ¥0.058 | 1× per account |
| **Developer** | 50M tokens / 3 months | ¥8 ($1.10 / €1.02) | ¥0.16 | 3× per account |
| **Education** | 50M tokens / 3 months | ¥8 ($1.10 / €1.02) | ¥0.16 | 3× per account |
| **Enterprise** | 10B tokens / 4 months | ¥1,600 ($221 / €204) | ¥0.16 | 3× per account |
| Standard (no package) | Pay-as-you-go | — | ¥0.2 ($0.03 / €0.03) | Unlimited |

**Cost estimate**: ~2,500 tokens per page (image input + markdown output). A 300-page textbook ≈ 750K tokens ≈ ¥0.15 at standard rate.

*Exchange rates: 1 USD ≈ 7.25 CNY, 1 EUR ≈ 7.85 CNY (approximate, March 2026)*

</details>
