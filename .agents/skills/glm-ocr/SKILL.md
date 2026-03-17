---
name: glm-ocr
description: PDF/PPT/Image -> Markdown OCR with Zhipu GLM-OCR, strict verification, and failure-safe fallback.
---

# GLM-OCR Skill

## When to Use

Use this skill when the task involves:

- OCR for PDF / PPT / PPTX / images
- Converting textbooks, lecture slides, or screenshots into Markdown
- Verifying whether OCR output is actually complete
- Investigating legacy mixed output, failed placeholders, or silent OCR corruption

## Project Layout

- `input/` — source files waiting for OCR
- `output/` — Markdown output, extracted images, and any `_failed_segments/*.failed.json`
- `_cache/ppt_pdf/` — cached PDFs converted from PPT/PPTX
- `ocr.py` — main OCR pipeline
- `verify_ocr.py` — acceptance check
- `audit_ocr_integrity.py` — deep integrity audit
- `reference_book_metadata.py` — textbook directory page, page offset, and QR resource generation
- `backfill_reference_book_directory_pages.py` — batch refresh textbook metadata
- `rerun_pdf_segments.py` — rerun only failed or suspicious page ranges
- `duplicate_image_reviewer.py` — local UI for duplicate/similar image review
- `clean_junk_images.py` — duplicate audit, similarity search, purge, and legacy size-clean fallback
- `markdown_cleanup.py` / `repair_math_delimiters.py` — OCR-side Markdown and LaTeX delimiter cleanup
- `KNOWLEDGE_PIPELINE.md` — source-library -> OCR intermediate -> Obsidian note workflow

## Required Workflow

1. Put source files into `input/`.
2. Run `python ocr.py`.
3. Run both `python verify_ocr.py` and `python audit_ocr_integrity.py`.
4. For textbooks/reference books, generate `目录页.md`, page offsets, and QR metadata via `reference_book_metadata.py` or `backfill_reference_book_directory_pages.py`.
5. Only treat the batch as complete when both checks are clean and the corresponding output directory has no `_failed_segments/*.failed.json`.
6. Before downstream note generation, use the OCR intermediate output rather than importing raw OCR folders directly into the final knowledge vault.

## Failure Semantics

- The fallback chain is `segment PDF upload -> per-page image OCR -> native PDF text fallback`.
- If a segment still fails after all fallbacks, the pipeline writes `_failed_segments/*.failed.json`.
- Failed placeholders and failed segment reports mean the OCR result is incomplete. Do not silently pass or move such output downstream.

## Common Problems and Recommended Handling

- `1301 contentFilter`: split the segment first, rerun the blocked page separately, then use a secondary OCR / vision path only for the blocked page if needed.
- Legacy `segment_*.md`: do not delete until ranged `.md` coverage and content have been compared.
- Garbled file names from ZIP/RAR extraction: fix source names first, then keep `input/`, `output/`, and downstream library names in sync.
- Empty native PDF text fallback: common on scanned books; be ready to switch to image OCR or another vision path.
- Formula delimiters like `$ 2x+1 $`: clean them at OCR output time, not later in the note-writing stage.
- Header/footer strips, logos, watermarks, and glyph fragments: suppress them before they become `images/`.
- Ordinary orphan images should be audited first; do not blindly delete every unreferenced image.
- If a page is filled through a non-GLM route, mark it as `AI visual supplementation (non-GLM-OCR output)` or equivalent instead of pretending it came from the main OCR pipeline.
- For the exact marker format and audit rules, follow `OCR_AUDIT_POLICY.md`.

## Notes

- PPT/PPTX temporary PDFs belong in `_cache/ppt_pdf/`, not in `output/`.
- `verify_ocr.py` is the minimum acceptance gate.
- `audit_ocr_integrity.py` should be used whenever you need confidence that there is no legacy mixed output or silent corruption.
- For the full downstream note workflow, also read `KNOWLEDGE_PIPELINE.md`.
