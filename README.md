English | [简体中文](README_CN.md)

# GLM OCR

> PDF/PPT/Image to Markdown OCR Converter

Batch convert documents to clean Markdown using [ZhipuAI GLM-OCR](https://open.bigmodel.cn/) API — the [#1 OCR model on OmniDocBench v1.5](https://opendatalab.com/omnidocbench) as of early 2026. Zero GPU required, LaTeX math support, concurrent processing, resume from breakpoint.

## Contents

- [Features](#features)
- [Use Cases](#use-cases)
- [Why GLM?](#why-glm)
  - [Pricing](#pricing)
  - [Comparison Summary](#comparison-summary)
  - [Why Cloud API?](#why-cloud-api)
- [Quick Start](#quick-start)
- [Studio Prototype](#studio-prototype)
- [Output Structure](#output-structure)
- [Verification and Failure Semantics](#verification-and-failure-semantics)
- [Common Failure Modes and Recommended Handling](#common-failure-modes-and-recommended-handling)
- [Recommended Workflow for Personal Knowledge Pipelines](#recommended-workflow-for-personal-knowledge-pipelines)
- [Reference-book Metadata and Downstream Note Workflow](#reference-book-metadata-and-downstream-note-workflow)
- [Clean Junk Images](#clean-junk-images)
- [Configuration](#configuration)
- [Requirements](#requirements)
- [Known Limitations](#known-limitations)
- [License](#license)
- [Appendix: Detailed Benchmark Test Results](#appendix-detailed-benchmark-test-results)
- [Appendix: API Pricing Details](#appendix-api-pricing-details)

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
- **Markdown cleanup at the OCR boundary**: normalizes OCR math delimiters so `$ 2x+1 $` becomes `$2x+1$` before downstream note generation
- **Suspicious math-command audit**: can emit a report of suspicious commands still left after cleanup, so the remaining OCR edge cases are explicit
- **Visual-block suppression**: filters header/footer strips, page-number corners, logos, watermarks, and glyph-fragment crops before they enter `images/`
- **Reference-book metadata**: generates `目录页.md`, page-offset notes, QR resource aggregation, and textbook lookup helpers
- **Manual image review UI**: local reviewer for duplicate / similar OCR images, blacklist learning, and group-by-group deletion
- **Junk image audit tools**: exact-duplicate audit, grayscale similarity search, orphan-image maintenance, and targeted watermark purging
- **No more fitz in the active PDF backend**: the main pipeline now uses `pypdf + pypdfium2`, with `pypdf` for page structure/text and `pypdfium2` for rendering and bbox crops
- **Math formula support**: LaTeX output (`$...$` inline, `$$...$$` block)
- **AI coding assistant support**: includes `CLAUDE.md` and `AGENTS.md` for Claude Code, Codex, OpenCode, and OpenClaw

## Use Cases

- Convert lecture slides / textbooks to Markdown for note-taking and RAG knowledge bases
- **WeChat chat export via screenshots**: taking long screenshots is a safer alternative to third-party export tools (no API abuse, no risk of ToS violations). OCR the screenshots into text, then feed to AI for personal assistant training
- Batch digitize scanned documents
- Extract text from web page screenshots

## Why GLM?

The [OmniDocBench v1.5](https://opendatalab.com/omnidocbench) benchmark ([GitHub](https://github.com/opendatalab/OmniDocBench)) is still one of the best document-parsing references, but there is an important 2026 caveat: **not every “high score” is reported on the same scale**.

- `GLM-OCR 94.62`: an **official raw OmniDocBench v1.5 score**
- `Qianfan-OCR 93.12`: an **official model-card self-reported OmniDocBench v1.5 score**
- `PaddleOCR-VL-1.5 94.5`: a **paper-reported OmniDocBench v1.5 score**
- `dots.mocr 1124.7`: an **Elo aggregate score across multiple benchmarks** from the project README
- `dots.mocr-svg 0.931 / 0.905`: **SVG-specific task scores** on UniSVG / ChartMimic

That means `94.62` and `1124.7` are not directly comparable. The first is a raw benchmark score; the second is an author-built Elo aggregate.

This is also why this software does not chase a single “one model does everything” answer:

- **GLM-OCR** remains the default daily document OCR path
- **Qianfan-OCR** is a strong cloud structured-OCR backend
- **dots.mocr-svg** is the most relevant path for turning charts, UI, and logos into editable SVG assets

Also, many people remember the older `PaddleOCR` toolkit line. The models compared here, `PaddleOCR-VL` and `PaddleOCR-VL-1.5`, belong to the **newer VL document parsing branch that formed between 2025-10 and 2026-01**, and should not be confused with the older product line.

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

| Solution | Key Score / Metric | Score Type | Best For | Weaknesses | Deployment |
|----------|--------------------|------------|----------|------------|------------|
| **GLM-OCR** (ZhipuAI / 智谱) | `94.62` | Raw OmniDocBench v1.5 score (official) | Textbooks, lecture notes, formula-heavy documents, and the default path of this software | Does not directly produce SVG; weak editable-asset story | Cloud API / VLLM local |
| **Qianfan-OCR** (Baidu Qianfan / 百度千帆) | `93.12` | OmniDocBench v1.5 self-reported score (official model card) | Markdown plus JSON structured output and cloud parsing of complex layouts | More focused on structured text than SVG assets | Cloud API |
| **PaddleOCR-VL-1.5** (Baidu / 百度) | `94.5` | OmniDocBench v1.5 self-reported score (paper) | Offline deployment, privacy-sensitive docs, strong structured parsing | Higher deployment cost; not ideal as your lightweight daily default | Local GPU / service deployment |
| **dots.ocr** (rednote-hilab) | `88.41` | Raw OmniDocBench v1.5 score | Markdown plus JSON plus bbox structure | Complex tables and math are not its strongest area | Local / vLLM |
| **dots.mocr** (rednote-hilab) | `1124.7` | Multi-benchmark Elo aggregate (official README) | Charts, UI, visual understanding, multimodal structured assets | Elo scores should not be mixed directly with raw OmniDocBench scores | Local / vLLM |
| **dots.mocr-svg** (rednote-hilab) | `UniSVG 0.931` / `ChartMimic 0.905` | SVG-specific task scores | Charts, UI, logos, and editable visual assets | Not a primary whole-document OCR model; better as a visual-asset pipeline stage | Local / vLLM / API wrapper |

For this product, the current best division of labor is:

1. **GLM-OCR** as the default document OCR pipeline
2. **Qianfan-OCR** as the cloud structured parsing backend
3. **dots.mocr-svg** as the editable SVG asset pipeline

### Why Cloud API?

This project is designed for **individual users** (students, researchers) who don't need to process thousands of documents. Cloud API means zero GPU requirements, no CUDA setup, no model downloads — just `pip install` and go. Local deployment only makes sense for enterprises with dedicated GPU servers.

The script architecture is model-agnostic — swapping to a different API (DeepSeek, Unisound U1, etc.) only requires changing the API client and model name in `ocr.py`.

> References:
> - [5-model OCR benchmark with detailed test cases (2026.02)](https://www.bilibili.com/video/BV1UjFjz1EdD/) by [@AI创客空间](https://space.bilibili.com/396997624)
> - [OCR model selection guide (2026.02)](https://www.bilibili.com/video/BV1GYF7z9E7n/) by [@从零开始学AI](https://space.bilibili.com/91394217)
> - [OmniDocBench v1.5 benchmark](https://github.com/opendatalab/OmniDocBench)
> - [GLM-OCR official documentation](https://docs.bigmodel.cn/cn/guide/models/vlm/glm-ocr)
> - [Qianfan-OCR official model card](https://huggingface.co/baidu/Qianfan-OCR)
> - [PaddleOCR-VL-1.5 paper](https://arxiv.org/abs/2601.21957)
> - [dots.mocr official README](https://github.com/rednote-hilab/dots.mocr)

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

## Studio Prototype

The repository now includes an early desktop-shell prototype named `GLM OCR Studio`.
It is meant to address two practical problems first:

- OCR provider differences are hard to remember
- advanced manual tools are scattered across scripts

The current prototype already provides:

- bilingual UI switching
- a provider capability board for GLM-OCR, Qianfan-OCR, Qianfan-OCR-Fast, GLM handwriting, dots.ocr, dots.mocr, dots.mocr-svg, PaddleOCR-VL 1.5, and PP-StructureV3
- a visual memory board for the existing manual workflow and script entry points
- a staged refactor plan

Run it with:

```bash
python ocr_studio.py
```

Refactor plan documents:

- English: [docs/STUDIO_REFACTOR_PLAN.md](docs/STUDIO_REFACTOR_PLAN.md)
- 简体中文: [docs/STUDIO_REFACTOR_PLAN_CN.md](docs/STUDIO_REFACTOR_PLAN_CN.md)

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

For textbooks and reference books, the OCR folder may additionally contain:

```text
目录页.md
周边资源-全部.md         # only when QR resources are numerous
_front_assets/qrcodes/    # extracted QR code snapshots
```

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

Full source-library -> OCR intermediate library -> Obsidian note workflow:

[KNOWLEDGE_PIPELINE.md](KNOWLEDGE_PIPELINE.md)

## Reference-book Metadata and Downstream Note Workflow

- `reference_book_metadata.py`: generate `目录页.md`, printed-page offsets, and QR resource aggregation from the original PDF
- `backfill_reference_book_directory_pages.py`: batch refresh textbook metadata across the intermediate library
- `rerun_pdf_segments.py`: rerun only failed or suspicious page ranges
- `markdown_cleanup.py` / `repair_math_delimiters.py`: fix OCR math delimiters and generate suspicious-command audit reports before the notes consume the output
- `duplicate_image_reviewer.py`: local UI for duplicate/similar image review, blacklist learning, and manual deletion
- `middle_library_image_maintenance.py`: audit orphan images and keep the OCR intermediate library tidy

This repo now supports not only OCR itself, but also the textbook metadata and handoff steps needed before writing structured course notes.

## Clean Junk Images

```bash
python clean_junk_images.py audit --root output --min-count 4 --copy-samples
python clean_junk_images.py similar --root output --reference path/to/sample.png --threshold 8
python clean_junk_images.py purge --root output --manifest confirmed_junk_manifest.txt
```

Use `python duplicate_image_reviewer.py --root output` for a local browser UI similar to phone gallery duplicate-photo cleanup.

The old size-based cleaner still exists as an explicit compatibility mode:

```bash
python clean_junk_images.py legacy-size-clean --root output
```

Recommended order is:

1. audit duplicate families
2. review them manually in the UI
3. learn or purge confirmed junk families
4. keep ordinary unreferenced images under audit instead of blindly deleting them

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
