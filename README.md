English | [简体中文](README_CN.md)

# GLM-OCR — PDF/PPT/Image to Markdown OCR Converter

Batch convert documents to clean Markdown using [ZhipuAI GLM-OCR](https://open.bigmodel.cn/) API — the [#1 OCR model on OmniDocBench v1.5](https://opendatalab.com/omnidocbench) as of early 2026. Zero GPU required, LaTeX math support, concurrent processing, resume from breakpoint.

## Features

- **PDF / PPT / PPTX -> Markdown**: segment-based OCR with failure-safe fallback (`PDF upload -> per-page image -> native PDF text fallback`)
- **Handwriting recognition**: `--handwrite` mode uses ZhipuAI handwriting OCR API for handwritten content
- **Concurrent processing**: when a file has multiple segments, processes 2 segments in parallel (GLM-OCR API max concurrency is 2)
- **Long screenshot support**: auto-splits tall images (e.g. chat screenshots) into overlapping segments (text OCR only, no image extraction)
- **Resume from breakpoint**: already-completed segments are skipped on re-run
- **Image extraction**: embedded images are saved to `images/` subfolder
- **Explicit failure reporting**: segments that still fail after fallback are recorded in `_failed_segments/*.failed.json` and are never silently treated as complete
- **Strict validation**: `verify_ocr.py` checks directory/md/page coverage/failure reports, and `audit_ocr_integrity.py` catches legacy mixed-output problems
- **Clean output tree**: converted PPT PDFs are cached under `_cache/ppt_pdf/` instead of being mixed into `output/`
- **Junk image cleaner**: removes common artifacts (background images, tiny icons) from OCR output
- **Math formula support**: LaTeX output (`$...$` inline, `$$...$$` block)
- **AI coding assistant support**: includes `CLAUDE.md` and `AGENTS.md` for Claude Code, Codex, OpenCode, and OpenClaw

## Use Cases

- Convert lecture slides / textbooks to Markdown for note-taking and RAG knowledge bases
- **WeChat chat export via screenshots**: taking long screenshots is a safer alternative to third-party export tools (no API abuse, no risk of ToS violations). OCR the screenshots into text, then feed to AI for personal assistant training
- Batch digitize scanned documents
- Extract text from web page screenshots

## Why GLM?

The [OmniDocBench v1.5](https://opendatalab.com/omnidocbench) benchmark ([GitHub](https://github.com/opendatalab/OmniDocBench)) is the most comprehensive OCR evaluation. As of early February 2026, GLM-OCR ranked **#1** in a 5-model head-to-head test (vs DeepSeek OCR2, MinerU, PaddleOCR VL, PaddleOCR VL 1.5). Around late February 2026, [Unisound U1](https://www.prnewswire.com/news-releases/unisound-u1-ocr-the-first-industrial-grade-document-intelligence-foundation-model-ushering-in-the-ocr-3-0-era-302698482.html) surpassed GLM-OCR on the leaderboard (95.1 vs 94.62), particularly excelling in medical/clinical document scenarios.

For context, general-purpose VLMs score significantly lower on OmniDocBench: **GPT-4o** scores 75.02, **Gemini-2.5 Pro** 88.03, **Qwen3-VL-235B** 89.15 — specialized OCR models like GLM-OCR (0.9B params) outperform them by a wide margin at a fraction of the cost and size.

### Pricing

Via [ZhipuAI special deals](https://bigmodel.cn/special_area), 50 million tokens (enough to OCR **~60 textbooks** at 300 pages each):

| Tier | Price | ~ USD | ~ EUR |
|------|-------|-------|-------|
| Flash sale (1× per account) | **¥2.9** | $0.40 | €0.37 |
| Developer / Education (3× per account) | **¥8** | $1.10 | €1.02 |
| Standard (no package) | ¥10 | $1.38 | €1.28 |

Standard per-token rate: ¥0.2/M tokens (~$0.03 / €0.03), roughly 1/100 the cost of GPT-4o Vision.

> Full pricing breakdown → [Appendix: API Pricing](#appendix-api-pricing-details)

### Comparison Summary

| Solution | OmniDocBench v1.5 | Best For | Weaknesses | Deployment |
|----------|--------------------|----------|------------|------------|
| **Unisound U1** (Unisound / 云知声) | **95.1** | Medical/clinical docs, field-level positioning & traceability, 50+ doc types (99%+ classification), extreme scenarios (blurred, multilingual) | Newer, less community testing, no public API pricing yet | Cloud API / On-premise |
| **GLM-OCR** (ZhipuAI / 智谱) | **94.62** | Structured documents, formulas, domain-specific text. 0.9B params, ~1.86 pages/sec, API ~0.2 CNY/M tokens (1/10 of traditional OCR) | Cannot extract images, no bounding box, hallucination on blurry text | Cloud API / VLLM local |
| **PaddleOCR VL 1.5** (Baidu / 百度) | **94.5** | Handwriting, tables, distorted images | CUDA dependency hell, weak at logical restructuring | Local GPU only |
| **MinerU 2.5** (OpenDataLab) | 90.67 | Clean PDFs with simple layout | Character errors on complex layouts | Local GPU only |
| **DeepSeek OCR** (DeepSeek / 深度求索) | 87.01 | Tables (zero info loss) | Formula errors, images discarded | Cloud API |
| **Gemini-2.5 Pro** (Google) | 88.03 | General-purpose VLM with decent OCR | Not OCR-specialized, $2.50/$15.00 per M tokens | Cloud API |
| **GPT-4o** (OpenAI) | 75.02 | General-purpose VLM | Poor OCR accuracy, $2.50/$10.00 per M tokens | Cloud API |

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
python ocr.py               # Standard OCR (printed text, formulas, etc.)
python ocr.py --handwrite   # Handwriting recognition mode
# Markdown output in output/
```

### 5. Verify Before Calling It Done

```bash
python verify_ocr.py
python audit_ocr_integrity.py
```

Only treat an OCR batch as complete when both checks are clean and the relevant `output/<file>/` directory has no `_failed_segments/*.failed.json`.

Detailed audit convention for non-GLM page supplementation: [OCR_AUDIT_POLICY.md](OCR_AUDIT_POLICY.md)

## Output Structure

```
output/
└── filename/
    ├── filename_0001-0020.md    # Pages 1-20
    ├── filename_0021-0040.md    # Pages 21-40
    ├── ...
    ├── _failed_segments/        # Present only when some pages still failed after all fallbacks
    │   └── filename_0021-0040.failed.json
    └── images/                  # Extracted bbox images
        ├── p0003_fig0001.png
        └── ...
```

Converted PPT/PPTX PDFs are cached separately under `_cache/ppt_pdf/<filename>/<filename>.pdf` so `output/` stays focused on OCR artifacts only.

## Verification and Failure Semantics

```bash
python verify_ocr.py
python audit_ocr_integrity.py
```

- `verify_ocr.py` is the acceptance gate. It checks output directories, Markdown presence, page-range continuity, failed placeholders, and `_failed_segments/*.failed.json`.
- `audit_ocr_integrity.py` is the deeper audit. It highlights high-risk states such as legacy mixed output, coverage gaps, partial failed md files, and explicit failed segment reports.
- `ocr.py` now treats "empty/failed markdown" as a real failure. If segment-level PDF upload is blocked or returns no meaningful content, it falls back to per-page images; if a page still fails, it tries native PDF text extraction; if that still fails, it writes a `.failed.json` report instead of pretending success.
- A visible failure report is intentional. It means the pipeline surfaced a real problem instead of silently producing incomplete OCR.

## Common Failure Modes and Recommended Handling

- **Provider content filter (`1301 contentFilter`)**:
  Some pages about security, attacks, or other sensitive topics may be blocked by ZhipuAI. Recommended handling:
  1. Split the failed segment so unaffected pages can still be saved.
  2. Retry the blocked page as a single-page segment.
  3. If it still fails, use a secondary path such as Mathpix, another vision model, or an explicitly documented AI visual transcription from the rendered page image.
  4. Mark the replacement clearly as non-GLM-OCR output.
- **Legacy mixed output (`segment_*.md`, old page image dumps)**:
  Older runs may leave mixed naming schemes or image-only remnants in `output/`. Recommended handling:
  1. Run `audit_ocr_integrity.py`.
  2. Do not delete old segments until the new ranged `.md` files are confirmed to cover the same pages.
  3. Prefer rerunning only the affected range instead of rerunning the whole book.
- **Garbled filenames from archive extraction / Windows encoding**:
  ZIP/RAR extraction may produce mojibake file names. Recommended handling:
  1. Rename the source files first.
  2. Keep `input/`, `output/`, and downstream library names synchronized.
  3. Save the rename mapping for later traceability.
- **PPT conversion artifacts**:
  PPT/PPTX must be converted to PDF before OCR. Recommended handling:
  1. Keep converted PDFs in `_cache/ppt_pdf/`.
  2. Do not treat cached PPT PDFs as OCR output.
  3. Do not import cache files into downstream knowledge libraries.
- **Editable-text fallback is not guaranteed**:
  Some scanned or image-only PDFs return no native text at all, so PDF text fallback may be empty. Recommended handling:
  1. Expect this on older scans and textbook page images.
  2. Switch to image OCR or another vision path rather than assuming native text extraction will save the page.

## Recommended Workflow for Personal Knowledge Pipelines

1. Keep a strict three-layer workflow:
   - source library
   - OCR intermediate library (`paged md + images`)
   - final knowledge base
2. Do not move OCR output into the final knowledge base before `verify_ocr.py` and `audit_ocr_integrity.py` are both clean.
3. For reference books, keep a directory page / page-offset note so future lookups can map book page numbers back to PDF page numbers.
4. When one blocked page would invalidate a whole segment, split the segment first so recoverable pages are not lost.
5. If you must replace one page through a non-GLM path, document it inside the target `.md` header so later auditing stays honest.

## Clean Junk Images

```bash
python clean_junk_images.py
```

Removes common OCR artifacts (background images ~3.2MB, icons <3KB) and cleans up Markdown references.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `PAGES_PER_MD_PDF` | 20 | Pages per segment for PDF |
| `PAGES_PER_MD_PPT` | 50 | Pages per segment for PPT |
| `MAX_WORKERS` | 2 | Max concurrent API calls (GLM-OCR API limit is 2) |
| `IMAGE_SEGMENT_HEIGHT` | 4000px | Max height per segment for long images |
| `IMAGE_OVERLAP` | 200px | Overlap between adjacent image segments |

## Requirements

- Python 3.8+
- [ZhipuAI API key](https://open.bigmodel.cn/)
- PowerPoint or WPS Office (only for PPT/PPTX conversion, via COM automation)

## Known Limitations

- **Hallucination**: GLM may guess plausible values for blurry text instead of returning errors — avoid for financial/medical documents requiring exact precision
- **Repetition bug**: Occasionally loops on dense Excel screenshots, repeating the same row
- **Provider content filters**: some pages (for example security-related textbook content) may trigger ZhipuAI safety filtering. These pages now stay visible as failed reports instead of being silently counted as finished OCR.
- **Handwriting**: Standard mode is weak on handwritten content — use `--handwrite` mode for handwritten text (or Claude/GPT for best quality). Handwriting mode outputs plain text only (no Markdown formatting), supports images only (PDFs are auto-converted to images), ¥0.01/page
- PPT/PPTX files are converted to PDF in a background thread (parallel with OCR), using a single reusable PowerPoint COM instance
- Source files in `input/` are preserved after processing

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
