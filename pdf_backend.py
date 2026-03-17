from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pypdfium2 as pdfium
from PIL import Image
from pypdf import PdfReader, PdfWriter


def _normalize_pdf_path(pdf_path: str | Path) -> Path:
    return Path(pdf_path).resolve()


def get_pdf_page_count(pdf_path: str | Path) -> int:
    reader = PdfReader(str(_normalize_pdf_path(pdf_path)))
    return len(reader.pages)


def extract_pdf_segment(
    pdf_path: str | Path,
    start: int,
    end: int,
    out_path: str | Path,
) -> None:
    reader = PdfReader(str(_normalize_pdf_path(pdf_path)))
    writer = PdfWriter()
    for index in range(start, min(end, len(reader.pages))):
        writer.add_page(reader.pages[index])
    out_file = _normalize_pdf_path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with out_file.open("wb") as handle:
        writer.write(handle)


def extract_pdf_page_text(pdf_path: str | Path, page_index: int) -> str:
    reader = PdfReader(str(_normalize_pdf_path(pdf_path)))
    if page_index < 0 or page_index >= len(reader.pages):
        return ""
    return (reader.pages[page_index].extract_text() or "").strip()


@dataclass(frozen=True)
class PdfPageSize:
    width: float
    height: float


class PdfRenderDocument:
    def __init__(self, pdf_path: str | Path) -> None:
        self.path = _normalize_pdf_path(pdf_path)
        self._doc = pdfium.PdfDocument(str(self.path))

    def __enter__(self) -> "PdfRenderDocument":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    def __len__(self) -> int:
        return len(self._doc)

    def page_size(self, page_index: int) -> PdfPageSize:
        width, height = self._doc.get_page_size(page_index)
        return PdfPageSize(float(width), float(height))

    def render_page(
        self,
        page_index: int,
        dpi: float = 72.0,
        grayscale: bool = False,
    ) -> Image.Image:
        page = self._doc.get_page(page_index)
        bitmap = None
        try:
            bitmap = page.render(
                scale=dpi / 72.0,
                grayscale=grayscale,
                rev_byteorder=True,
            )
            image = bitmap.to_pil()
            return image.copy()
        finally:
            if bitmap is not None:
                bitmap.close()
            page.close()

    def render_bbox_crop(
        self,
        page_index: int,
        coords: tuple[float, float, float, float],
        api_size: tuple[float, float],
        dpi: float = 216.0,
        rendered_page: Image.Image | None = None,
    ) -> Image.Image:
        api_w, api_h = api_size
        if api_w <= 0 or api_h <= 0:
            raise ValueError("api_size must be positive")

        page_image = rendered_page if rendered_page is not None else self.render_page(page_index, dpi=dpi)
        x0, y0, x1, y1 = coords
        sx = page_image.width / api_w
        sy = page_image.height / api_h

        left = max(0, int(round(x0 * sx)))
        top = max(0, int(round(y0 * sy)))
        right = min(page_image.width, int(round(x1 * sx)))
        bottom = min(page_image.height, int(round(y1 * sy)))
        if right <= left or bottom <= top:
            raise ValueError("bbox crop is empty")
        return page_image.crop((left, top, right, bottom))

    def iter_text_rects(self, page_index: int) -> Iterator[tuple[float, float, float, float]]:
        page = self._doc.get_page(page_index)
        text_page = None
        try:
            page_height = float(page.get_height())
            text_page = page.get_textpage()
            rect_count = text_page.count_rects()
            for index in range(rect_count):
                left, bottom, right, top = text_page.get_rect(index)
                yield (
                    float(left),
                    page_height - float(top),
                    float(right),
                    page_height - float(bottom),
                )
        finally:
            if text_page is not None:
                text_page.close()
            page.close()

