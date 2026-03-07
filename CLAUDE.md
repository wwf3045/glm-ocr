# GLM-OCR — AI Coding Assistant Instructions

> This file is for AI coding assistants (Claude Code, Codex, Cursor, etc.). It is optional and can be safely deleted.

## Project Overview

PDF/PPT/Image to Markdown OCR converter using ZhipuAI GLM API. Processes files in `input/` and outputs Markdown to `output/`.

## Key Commands

```bash
python ocr.py                  # OCR all files in input/
python clean_junk_images.py    # Remove junk images from output
```

## Architecture

- `ocr.py` — Main OCR script. Segments PDFs (20 pages/segment), PPTs (50 pages/segment), and long images (4000px/segment). Uses GLM-4v-flash API with automatic fallback (file upload → per-page image).
- `clean_junk_images.py` — Removes background images (~3.2MB) and tiny icons (<3KB) from OCR output, cleans Markdown references.
- `.env` — Must contain `GLM_API_KEY=xxx` (ZhipuAI API key). Never commit this file.

## Important Notes

- Do not modify `.env` or commit API keys
- `input/` and `output/` are gitignored — do not track data files
- Source files in `input/` are auto-deleted after successful OCR
- Resume support: already-completed segments are skipped on re-run
- PPT/PPTX requires LibreOffice installed for PDF conversion
