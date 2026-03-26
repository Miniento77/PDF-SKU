from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Sequence, Tuple

from .errors import DependencyError
from .layout import FooterLayout, LayoutConfig, choose_footer_layout
from .models import SkuQuantity


def append_footer_to_label(
    input_pdf: str | Path,
    output_pdf: str | Path,
    items: Sequence[SkuQuantity],
    config: LayoutConfig | None = None,
) -> FooterLayout:
    PdfReader, PdfWriter, Transformation = _load_pypdf()

    source_path = Path(input_pdf)
    destination_path = Path(output_pdf)
    config = config or LayoutConfig()

    with source_path.open("rb") as source_handle:
        reader = PdfReader(source_handle)
        if len(reader.pages) != 1:
            raise ValueError("Input PDF must contain exactly one page.")

        source_page = reader.pages[0]
        page_width = float(source_page.mediabox.width)
        page_height = float(source_page.mediabox.height)
        layout = choose_footer_layout(items=items, page_width=page_width, config=config)

        footer_pdf = _build_footer_overlay(page_width, layout)
        footer_reader = PdfReader(footer_pdf)

        writer = PdfWriter()
        output_page = writer.add_blank_page(
            width=page_width, height=page_height + layout.footer_height
        )
        output_page.merge_transformed_page(
            source_page, Transformation().translate(tx=0, ty=layout.footer_height)
        )
        output_page.merge_page(footer_reader.pages[0])

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with destination_path.open("wb") as destination_handle:
            writer.write(destination_handle)

    return layout


def pdf_dependencies_available() -> bool:
    try:
        _load_pypdf()
        _load_reportlab_canvas()
        from reportlab.pdfbase.pdfmetrics import stringWidth  # noqa: F401
    except (DependencyError, ImportError):
        return False
    return True


def _build_footer_overlay(page_width: float, layout: FooterLayout) -> BytesIO:
    canvas_cls = _load_reportlab_canvas()
    buffer = BytesIO()
    canvas = canvas_cls(buffer, pagesize=(page_width, layout.footer_height), pageCompression=1)

    canvas.setStrokeColorRGB(0.75, 0.75, 0.75)
    canvas.setLineWidth(0.5)
    canvas.line(0, layout.footer_height - 0.5, page_width, layout.footer_height - 0.5)

    total_text_height = layout.font_size + (
        (len(layout.lines) - 1) * layout.font_size * layout.line_spacing
    )
    extra_vertical_space = max(
        0.0,
        layout.footer_height - total_text_height - (2 * layout.vertical_padding),
    )
    first_baseline = (
        layout.footer_height
        - layout.vertical_padding
        - (extra_vertical_space / 2.0)
        - layout.font_size
    )

    canvas.setFillColorRGB(0, 0, 0)
    canvas.setFont(layout.font_name, layout.font_size)
    for index, line in enumerate(layout.lines):
        x_position = max(layout.horizontal_padding, (page_width - line.width) / 2.0)
        y_position = first_baseline - (index * layout.font_size * layout.line_spacing)
        canvas.drawString(x_position, y_position, line.text)

    canvas.showPage()
    canvas.save()
    buffer.seek(0)
    return buffer


def _load_pypdf() -> Tuple[type, type, type]:
    try:
        from pypdf import PdfReader, PdfWriter, Transformation
    except ImportError as exc:
        raise DependencyError(
            "Missing PDF dependency. Install with "
            "'python3 -m pip install pypdf reportlab'."
        ) from exc

    return PdfReader, PdfWriter, Transformation


def _load_reportlab_canvas():
    try:
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise DependencyError(
            "Missing PDF dependency. Install with "
            "'python3 -m pip install pypdf reportlab'."
        ) from exc

    return Canvas
