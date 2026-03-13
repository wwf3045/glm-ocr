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

## Required Workflow

1. Put source files into `input/`.
2. Run `python ocr.py`.
3. Run both `python verify_ocr.py` and `python audit_ocr_integrity.py`.
4. Only treat the batch as complete when both checks are clean and the corresponding output directory has no `_failed_segments/*.failed.json`.

## Failure Semantics

- The fallback chain is `segment PDF upload -> per-page image OCR -> native PDF text fallback`.
- If a segment still fails after all fallbacks, the pipeline writes `_failed_segments/*.failed.json`.
- Failed placeholders and failed segment reports mean the OCR result is incomplete. Do not silently pass or move such output downstream.

## Notes

- PPT/PPTX temporary PDFs belong in `_cache/ppt_pdf/`, not in `output/`.
- `verify_ocr.py` is the minimum acceptance gate.
- `audit_ocr_integrity.py` should be used whenever you need confidence that there is no legacy mixed output or silent corruption.
