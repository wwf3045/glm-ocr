# OCR Audit Policy

This document defines how GLM-OCR results should be audited when some pages cannot be produced by the main GLM pipeline.

## Scope

Use this policy for:

- failed segments reported by `_failed_segments/*.failed.json`
- pages replaced through non-GLM routes
- mixed legacy output that must be reviewed before cleanup

## Three Result Classes

1. **GLM-native output**
   - Produced by the standard pipeline in `ocr.py`
   - May include PDF upload, per-page image fallback, and native PDF text fallback
   - No extra annotation is required
2. **Documented non-GLM supplementation**
   - The page could not be completed by the GLM pipeline
   - A secondary route was used, such as Mathpix, another vision model, or AI visual transcription from a rendered page image
   - The target `.md` must include the `OCR_AUDIT` marker
3. **Undocumented replacement**
   - A page was replaced manually or by another route but the source is not recorded
   - This is not acceptable for long-term auditability

## Required Marker

For every non-GLM replacement page, add a one-line comment near the file header:

```md
<!-- OCR_AUDIT: supplement=non_glm mode=ai_visual_supplement reason=provider_content_filter source=rendered_page_image operator=codex_session_vision -->
```

Recommended fields:

- `supplement=non_glm`
- `mode=ai_visual_supplement` or another precise mode
- `reason=provider_content_filter` or another concrete cause
- `source=rendered_page_image` or another source description
- `operator=...` to record which workflow produced the replacement

## Recommended Handling Order

1. Split the failed segment first so unaffected pages can still be saved.
2. Retry the blocked page as a single-page segment.
3. Try the built-in fallback chain before leaving the GLM pipeline.
4. If the page still fails, use a secondary route.
5. Record the replacement with the `OCR_AUDIT` marker.

## Audit Interpretation

- `_failed_segments/*.failed.json` means the batch is not complete.
- A page with the `OCR_AUDIT` marker is not considered hidden corruption.
- Documented non-GLM supplementation should remain visible in audit reports.
- Legacy `segment_*.md` must not be deleted until ranged `.md` coverage and text continuity have been confirmed.

## Current Script Behavior

- `verify_ocr.py` remains the acceptance gate for completion.
- `audit_ocr_integrity.py` now reports documented non-GLM supplementation in a separate section so it stays visible without being mixed into true high-risk failures.
