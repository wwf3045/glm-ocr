English | [简体中文](README_CN.md)

# GLM-OCR

Batch convert PDF / PPT / images to Markdown using [ZhipuAI GLM-4v-flash](https://open.bigmodel.cn/) API. Outputs clean Markdown with LaTeX math formulas.

## Features

- **PDF / PPT / PPTX -> Markdown**: segment-based OCR with automatic fallback (file upload -> per-page image)
- **Long screenshot support**: auto-splits tall images (e.g. chat screenshots) into overlapping segments
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

## Requirements

- Python 3.8+
- [ZhipuAI API key](https://open.bigmodel.cn/) (GLM-4v-flash is free-tier)
- LibreOffice (only for PPT/PPTX conversion)

## Notes

- GLM-4v-flash is weak on handwritten content. Use Claude or GPT for handwriting OCR.
- PPT/PPTX files are first converted to PDF via LibreOffice before OCR.
- Source files are automatically deleted from `input/` after successful processing.

## License

MIT
