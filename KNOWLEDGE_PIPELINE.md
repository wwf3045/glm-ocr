English | [简体中文](KNOWLEDGE_PIPELINE_CN.md)

# Knowledge Note Generation Pipeline

This document records the full workflow from raw course files to final Obsidian notes.

## 1. Three-layer storage model

1. Source library: keep original `pdf / ppt / pptx / scans / course attachments`.
2. OCR intermediate library: keep `paged md + images + textbook metadata pages`.
3. Knowledge vault: keep cleaned course outlines, chapter notes, and final attachments for Obsidian.

Do not skip the intermediate layer. OCR output is source material, not the final note itself.

## 2. OCR the source files

1. Put files into `input/`.
2. Run `python ocr.py`.
3. For handwritten material, run `python ocr.py --handwrite`.
4. Keep PPT-converted PDFs in `_cache/ppt_pdf/`, not in `output/`.

### PDF backend contract

- The active `GLM-OCR` PDF backend has already moved away from `PyMuPDF(fitz)` to `pypdf + pypdfium2`.
- Split of responsibility:
  - `pypdf`: page count, segment extraction, and native PDF text fallback
  - `pypdfium2`: page rendering, bbox crops, and QR-page raster sampling
- In practice this means:
  - do not reintroduce `fitz` by default into `ocr.py`, `verify_ocr.py`, or textbook-metadata scripts
  - if a task only needs PDF structure/text, avoid adding rendering-heavy dependencies
  - if a task really needs pixels, route it through `pdf_backend.py`

## 3. Accept the OCR batch before downstream use

Run both:

```bash
python verify_ocr.py
python audit_ocr_integrity.py
```

Only treat the batch as complete when:

- page coverage is continuous
- there is no silent empty Markdown
- the relevant folder has no `_failed_segments/*.failed.json`

If a range fails, prefer `rerun_pdf_segments.py` over rerunning the whole book.

## 4. Clean formulas and OCR-side formatting

The OCR pipeline should normalize math delimiters before downstream note generation:

- `$ 2x+1 $` -> `$2x+1$`
- keep block math as `$$...$$`

Related scripts:

- `markdown_cleanup.py`
- `repair_math_delimiters.py`

## 5. Control extracted images before they reach notes

The OCR pipeline should suppress or audit:

- headers / footers / page-number strips
- school logos, watermarks, banners
- isolated glyph fragments such as brackets, integrals, single letters
- orphan whole-page screenshots

Related scripts:

- `clean_junk_images.py`
- `duplicate_image_reviewer.py`
- `middle_library_image_maintenance.py`
- `purge_sjtu_watermarks.py`

Use the reviewer UI for manual image approval when needed. The final note should only keep images that serve a concrete concept, theorem, example, or algorithm step.

## 6. Generate textbook metadata

For textbooks and reference books, generate:

- `目录页.md`
- page offset information
- QR resource aggregation

Rules:

- every textbook OCR folder should have `目录页.md`
- page offsets should map original printed page numbers back to PDF pages
- if QR resources are few, keep them inside `目录页.md`
- if QR resources are many, aggregate them into `周边资源-全部.md`

Related scripts:

- `reference_book_metadata.py`
- `backfill_reference_book_directory_pages.py`

## 7. Build the course outline in the knowledge vault

Before generating chapter notes, create a resource-oriented `大纲.md` that lists:

- source-library entry
- lecture slides / PPTs
- textbooks and references
- assignments / review material
- online resources

Do not pretend the outline is already a full lecture note if the structure is not stable yet.

## 8. Build chapter-source mapping

For each course:

1. use the teacher's sequence as the main skeleton
2. align textbook chapters to that skeleton
3. mark what is:
   - course-required / exam-priority
   - textbook supplement (`*`)

If multiple teachers exist, keep one as the main progression and use the other to fill gaps.

## 9. Generate formal notes

Formal notes should be rewritten integrated notes, not raw OCR dumps.

Each chapter should normally contain:

- what problem the chapter answers
- transition from the previous chapter
- intuition or geometry
- formal definitions
- theorems and conclusions
- derivation or proof idea
- examples
- common mistakes
- assignment mapping
- textbook supplement (`*`)

## 10. Integrate homework and worked solutions

Recommended format for homework-heavy courses:

- Chinese prompt summary
- key tested concept
- Chinese solution path
- `English Problem`
- `English Solution`

This keeps revision readable while preserving exam familiarity with the original wording.

## 11. Final Obsidian placement

When moving to the knowledge vault:

- place attachments under the mirrored attachment structure
- insert images near the exact concept they explain
- do not pile images at the end of a note
- do not import raw OCR intermediate folders as final course notes

## 12. Recommended script map

- OCR main pipeline: `ocr.py`
- PDF backend bridge: `pdf_backend.py`
- verification: `verify_ocr.py`, `audit_ocr_integrity.py`
- range rerun: `rerun_pdf_segments.py`
- formula cleanup: `markdown_cleanup.py`, `repair_math_delimiters.py`
- image audit / purge: `clean_junk_images.py`, `duplicate_image_reviewer.py`, `middle_library_image_maintenance.py`
- textbook metadata: `reference_book_metadata.py`, `backfill_reference_book_directory_pages.py`
