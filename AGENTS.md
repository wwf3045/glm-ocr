# GLM-OCR — AI Coding Assistant Instructions

> This file is for AI coding assistants (Claude Code, Codex, Cursor, OpenCode, etc.). It is optional and can be safely deleted.

## Project Overview

PDF/PPT/Image to Markdown OCR converter using ZhipuAI GLM API. Processes files in `input/` and outputs Markdown to `output/`.

## Key Commands

```bash
python ocr.py                     # OCR all files in input/
python verify_ocr.py              # Acceptance check: coverage, failed placeholders, failed segment reports
python audit_ocr_integrity.py     # Deep audit for coverage gaps / legacy mixed output / failed md states
python clean_junk_images.py       # Remove junk images from output
```

## Architecture

- `ocr.py` — Main OCR script. Segments PDFs (20 pages/segment), PPTs (50 pages/segment), and long images (4000px/segment). Fallback chain is `segment PDF upload -> per-page image OCR -> native PDF text fallback`. If pages still fail, the script writes `output/<file>/_failed_segments/*.failed.json` instead of silently emitting a fake-success `.md`.
- `verify_ocr.py` — Acceptance gate. Flags missing dirs, missing Markdown, coverage gaps, failed placeholders, and `_failed_segments` reports.
- `audit_ocr_integrity.py` — Deeper integrity audit for legacy mixed output, failed markdown artifacts, coverage gaps, and other high-risk states.
- `clean_junk_images.py` — Removes background images (~3.2MB) and tiny icons (<3KB) from OCR output, cleans Markdown references.
- `_cache/ppt_pdf/` — PPT/PPTX conversion cache. Converted PDFs should live here, not inside `output/`.
- `.env` — Must contain `GLM_API_KEY=xxx` (ZhipuAI API key). Never commit this file.

## Important Notes

- Do not modify `.env` or commit API keys
- `input/`, `output/`, `_cache/`, `audit_reports/`, and `output_backups/` are local data / diagnostics — do not publish them
- Source files in `input/` are preserved after processing (not auto-deleted)
- Resume support: already-completed segments are skipped on re-run
- PPT/PPTX requires PowerPoint or WPS Office (COM automation) for PDF conversion
- Treat any `_failed_segments/*.failed.json`, `[FAILED_SEGMENT]`, or `"OCR 页失败"` marker as an incomplete OCR result
- If a provider content filter blocks one page, first split the segment so unaffected pages can still be saved; only then escalate to another OCR or vision path for the blocked page
- If a page is replaced through a non-GLM route, label it clearly as AI visual supplementation / non-GLM-OCR output rather than pretending it came from the main OCR pipeline
- Use the `OCR_AUDIT` marker and follow `OCR_AUDIT_POLICY.md` whenever a page is supplemented outside the main GLM pipeline
