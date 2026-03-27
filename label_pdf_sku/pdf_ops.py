from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import List, Sequence, Tuple

from .errors import DependencyError
from .layout import FooterLayout, LayoutConfig, choose_footer_layout
from .models import SkuQuantity
from .parsing import render_item_text

_TARGET_PAGE_HEIGHT_PER_WIDTH = 6.0 / 4.0
_PAGE_GEOMETRY_EPSILON = 0.01
_MAX_GEOMETRY_ITERATIONS = 12
_LANDSCAPE_HALF_DOMINANCE_RATIO = 0.85
_CONTENT_OCCUPANCY_CROP_THRESHOLD = 0.70
_SYMMETRIC_MARGIN_CROP_THRESHOLD = 0.12
_CONTENT_PADDING_RATIO = 0.02
_MIN_CONTENT_PADDING = 6.0
_MAX_CONTENT_PADDING = 18.0
_MIN_REGION_SIZE = 1.0
_IDENTITY_TRANSFORM = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_PAINTING_OPERATORS = {
    b"S",
    b"s",
    b"f",
    b"F",
    b"f*",
    b"B",
    b"B*",
    b"b",
    b"b*",
}
_STANDARD_PDF_FONT_NAMES = frozenset(
    {
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Oblique",
        "Helvetica-BoldOblique",
        "Times-Roman",
        "Times-Bold",
        "Times-Italic",
        "Times-BoldItalic",
        "Symbol",
        "ZapfDingbats",
    }
)
_SYSTEM_CJK_FONT_CANDIDATES = (
    ("LabelPdfSku-STHeiti-Light", Path("/System/Library/Fonts/STHeiti Light.ttc")),
    ("LabelPdfSku-STHeiti-Medium", Path("/System/Library/Fonts/STHeiti Medium.ttc")),
    ("LabelPdfSku-Songti", Path("/System/Library/Fonts/Supplemental/Songti.ttc")),
    (
        "LabelPdfSku-Arial-Unicode",
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ),
    ("LabelPdfSku-NotoSansCJK", Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")),
    (
        "LabelPdfSku-NotoSerifCJK",
        Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    ),
    (
        "LabelPdfSku-SourceHanSans",
        Path("/usr/share/fonts/opentype/source-han-sans/SourceHanSansSC-Regular.otf"),
    ),
    (
        "LabelPdfSku-SourceHanSerif",
        Path("/usr/share/fonts/opentype/source-han-serif/SourceHanSerifSC-Regular.otf"),
    ),
    ("LabelPdfSku-Microsoft-YaHei", Path("C:/Windows/Fonts/msyh.ttc")),
    ("LabelPdfSku-SimHei", Path("C:/Windows/Fonts/simhei.ttf")),
)
_CID_CJK_FONT_FALLBACKS = ("STSong-Light",)
_CJK_UNICODE_RANGES = (
    ("\u3000", "\u303f"),
    ("\u3400", "\u4dbf"),
    ("\u4e00", "\u9fff"),
    ("\uf900", "\ufaff"),
    ("\U00020000", "\U0002ebef"),
)


@dataclass(frozen=True)
class _OutputPageGeometry:
    page_width: float
    page_height: float
    source_offset_x: float
    source_offset_y: float
    footer_layout: FooterLayout


@dataclass(frozen=True)
class _Rectangle:
    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.top - self.bottom)

    @property
    def area(self) -> float:
        return self.width * self.height

    def intersection(self, other: _Rectangle) -> _Rectangle | None:
        left = max(self.left, other.left)
        bottom = max(self.bottom, other.bottom)
        right = min(self.right, other.right)
        top = min(self.top, other.top)
        if right <= left or top <= bottom:
            return None
        return _Rectangle(left=left, bottom=bottom, right=right, top=top)


@dataclass(frozen=True)
class _PreparedSourcePage:
    crop_region: _Rectangle
    placed_width: float
    placed_height: float
    rotate_clockwise: bool


def append_footer_to_label(
    input_pdf: str | Path,
    output_pdf: str | Path,
    items: Sequence[SkuQuantity],
    config: LayoutConfig | None = None,
) -> FooterLayout:
    PdfReader, PdfWriter, Transformation, RectangleObject = _load_pypdf()

    source_path = Path(input_pdf)
    destination_path = Path(output_pdf)
    config = config or LayoutConfig()
    config = _resolve_footer_font_config(items=items, config=config)

    with source_path.open("rb") as source_handle:
        reader = PdfReader(source_handle)
        if len(reader.pages) != 1:
            raise ValueError("输入的 PDF 必须且只能包含 1 页。")

        source_page = reader.pages[0]
        if source_page.rotation:
            source_page.transfer_rotation_to_content()
        prepared_source = _prepare_source_page(source_page)
        source_page.cropbox = RectangleObject(
            (
                prepared_source.crop_region.left,
                prepared_source.crop_region.bottom,
                prepared_source.crop_region.right,
                prepared_source.crop_region.top,
            )
        )
        output_geometry = _build_output_page_geometry(
            items=items,
            source_width=prepared_source.placed_width,
            source_height=prepared_source.placed_height,
            config=config,
        )

        footer_pdf = _build_footer_overlay(
            output_geometry.page_width,
            output_geometry.footer_layout,
        )
        footer_reader = PdfReader(footer_pdf)

        writer = PdfWriter()
        output_page = writer.add_blank_page(
            width=output_geometry.page_width,
            height=output_geometry.page_height,
        )
        output_page.merge_transformed_page(
            source_page,
            _build_source_transformation(
                transformation_cls=Transformation,
                crop_region=prepared_source.crop_region,
                rotate_clockwise=prepared_source.rotate_clockwise,
                offset_x=output_geometry.source_offset_x,
                offset_y=output_geometry.source_offset_y,
            ),
        )
        output_page.merge_page(footer_reader.pages[0])

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with destination_path.open("wb") as destination_handle:
            writer.write(destination_handle)

    return output_geometry.footer_layout


def pdf_dependencies_available() -> bool:
    try:
        _load_pypdf()
        _load_reportlab_canvas()
        from reportlab.pdfbase.pdfmetrics import stringWidth  # noqa: F401
    except (DependencyError, ImportError):
        return False
    return True


def _resolve_footer_font_config(
    items: Sequence[SkuQuantity],
    config: LayoutConfig,
) -> LayoutConfig:
    if config.font_name not in _STANDARD_PDF_FONT_NAMES:
        return config
    if not any(_text_contains_cjk(render_item_text(item)) for item in items):
        return config

    font_name = _resolve_cjk_font_name()
    if font_name == config.font_name:
        return config
    return replace(config, font_name=font_name)


def _text_contains_cjk(text: str) -> bool:
    return any(
        start <= character <= end
        for character in text
        for start, end in _CJK_UNICODE_RANGES
    )


def _resolve_cjk_font_name() -> str:
    for font_name, font_path in _SYSTEM_CJK_FONT_CANDIDATES:
        if _register_truetype_font(font_name=font_name, font_path=font_path):
            return font_name
    for font_name in _CID_CJK_FONT_FALLBACKS:
        if _register_cid_font(font_name):
            return font_name
    return LayoutConfig.font_name


def _register_truetype_font(font_name: str, font_path: Path) -> bool:
    if not font_path.exists():
        return False

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:
        raise DependencyError(
            "缺少 PDF 依赖，请先执行 "
            "'python3 -m pip install pypdf reportlab'。"
        ) from exc

    if font_name in pdfmetrics.getRegisteredFontNames():
        return True

    try:
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))
    except Exception:
        return False
    return True


def _register_cid_font(font_name: str) -> bool:
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except ImportError as exc:
        raise DependencyError(
            "缺少 PDF 依赖，请先执行 "
            "'python3 -m pip install pypdf reportlab'。"
        ) from exc

    if font_name in pdfmetrics.getRegisteredFontNames():
        return True

    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
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
    grid_width = sum(layout.column_widths) + (
        max(0, len(layout.column_widths) - 1) * layout.column_gap
    )
    grid_origin_x = max(
        layout.horizontal_padding,
        (page_width - grid_width) / 2.0,
    )
    for index, line in enumerate(layout.lines):
        y_position = first_baseline - (index * layout.font_size * layout.line_spacing)
        if line.cells and layout.column_widths:
            for cell in line.cells:
                x_position = grid_origin_x + sum(
                    layout.column_widths[:cell.column_index]
                ) + (cell.column_index * layout.column_gap)
                canvas.drawString(x_position, y_position, cell.text)
        else:
            x_position = max(layout.horizontal_padding, (page_width - line.width) / 2.0)
            canvas.drawString(x_position, y_position, line.text)

    canvas.showPage()
    canvas.save()
    buffer.seek(0)
    return buffer


def _build_output_page_geometry(
    items: Sequence[SkuQuantity],
    source_width: float,
    source_height: float,
    config: LayoutConfig,
) -> _OutputPageGeometry:
    target_width = max(
        source_width,
        (source_height + config.min_footer_height) / _TARGET_PAGE_HEIGHT_PER_WIDTH,
    )

    for _ in range(_MAX_GEOMETRY_ITERATIONS):
        footer_layout = choose_footer_layout(
            items=items,
            page_width=target_width,
            config=config,
        )
        required_target_width = max(
            source_width,
            (source_height + footer_layout.footer_height)
            / _TARGET_PAGE_HEIGHT_PER_WIDTH,
        )
        if required_target_width <= target_width + _PAGE_GEOMETRY_EPSILON:
            target_height = target_width * _TARGET_PAGE_HEIGHT_PER_WIDTH
            return _OutputPageGeometry(
                page_width=target_width,
                page_height=target_height,
                source_offset_x=(target_width - source_width) / 2.0,
                source_offset_y=target_height - source_height,
                footer_layout=footer_layout,
            )
        target_width = required_target_width

    footer_layout = choose_footer_layout(
        items=items,
        page_width=target_width,
        config=config,
    )
    target_height = target_width * _TARGET_PAGE_HEIGHT_PER_WIDTH
    return _OutputPageGeometry(
        page_width=target_width,
        page_height=target_height,
        source_offset_x=(target_width - source_width) / 2.0,
        source_offset_y=target_height - source_height,
        footer_layout=footer_layout,
    )


def _prepare_source_page(source_page) -> _PreparedSourcePage:
    page_region = _rectangle_from_box(source_page.cropbox)
    content_regions = _detect_content_regions(source_page)
    crop_region = page_region
    half_region = _select_landscape_half_region(page_region, content_regions)
    if half_region is not None:
        crop_region = half_region
    crop_region = _trim_crop_region_to_content(crop_region, content_regions)
    crop_changed = not _rectangles_close(crop_region, page_region)
    rotate_clockwise = half_region is not None or (
        crop_changed and crop_region.width > crop_region.height
    )
    return _PreparedSourcePage(
        crop_region=crop_region,
        placed_width=crop_region.height if rotate_clockwise else crop_region.width,
        placed_height=crop_region.width if rotate_clockwise else crop_region.height,
        rotate_clockwise=rotate_clockwise,
    )


def _build_source_transformation(
    transformation_cls,
    crop_region: _Rectangle,
    rotate_clockwise: bool,
    offset_x: float,
    offset_y: float,
):
    transformation = transformation_cls().translate(
        tx=-crop_region.left,
        ty=-crop_region.bottom,
    )
    if rotate_clockwise:
        transformation = transformation.rotate(-90).translate(tx=0, ty=crop_region.width)
    return transformation.translate(tx=offset_x, ty=offset_y)


def _rectangle_from_box(box) -> _Rectangle:
    return _Rectangle(
        left=float(box.left),
        bottom=float(box.bottom),
        right=float(box.right),
        top=float(box.top),
    )


def _detect_content_regions(source_page) -> List[_Rectangle]:
    regions = _collect_graphic_regions(source_page)
    regions.extend(_collect_text_regions(source_page))
    return regions


def _collect_graphic_regions(source_page) -> List[_Rectangle]:
    content = source_page.get_contents()
    if content is None:
        return []

    resources = _get_inherited_page_resources(source_page)
    xobjects = resources.get("/XObject") if resources else None
    regions: List[_Rectangle] = []
    current_transform = _IDENTITY_TRANSFORM
    transform_stack: List[Tuple[float, float, float, float, float, float]] = []
    current_path_points: List[Tuple[float, float]] = []

    for operands, operator in content.operations:
        if operator == b"q":
            transform_stack.append(current_transform)
            continue
        if operator == b"Q":
            current_transform = (
                transform_stack.pop() if transform_stack else _IDENTITY_TRANSFORM
            )
            continue
        if operator == b"cm":
            current_transform = _multiply_transforms(
                tuple(float(operand) for operand in operands[:6]),
                current_transform,
            )
            continue
        if operator == b"re":
            x, y, width, height = (float(operand) for operand in operands[:4])
            current_path_points.extend(
                [
                    _apply_transform(current_transform, x, y),
                    _apply_transform(current_transform, x + width, y),
                    _apply_transform(current_transform, x, y + height),
                    _apply_transform(current_transform, x + width, y + height),
                ]
            )
            continue
        if operator in {b"m", b"l"}:
            x, y = (float(operand) for operand in operands[:2])
            current_path_points.append(_apply_transform(current_transform, x, y))
            continue
        if operator == b"c":
            for index in (0, 2, 4):
                x = float(operands[index])
                y = float(operands[index + 1])
                current_path_points.append(_apply_transform(current_transform, x, y))
            continue
        if operator in {b"v", b"y"}:
            for index in (0, 2):
                x = float(operands[index])
                y = float(operands[index + 1])
                current_path_points.append(_apply_transform(current_transform, x, y))
            continue
        if operator in _PAINTING_OPERATORS:
            region = _rectangle_from_points(current_path_points)
            if region is not None:
                regions.append(region)
            current_path_points = []
            continue
        if operator == b"n":
            current_path_points = []
            continue
        if operator == b"Do" and xobjects is not None:
            xobject = xobjects.get(operands[0])
            if xobject is None:
                continue
            region = _region_from_xobject(
                xobject.get_object(),
                current_transform,
            )
            if region is not None:
                regions.append(region)

    return regions


def _collect_text_regions(source_page) -> List[_Rectangle]:
    regions: List[_Rectangle] = []

    def visitor_text(text, cm_matrix, tm_matrix, _font_dict, font_size):
        stripped_text = str(text).strip()
        if not stripped_text:
            return
        combined_transform = _multiply_transforms(
            tuple(float(value) for value in tm_matrix[:6]),
            tuple(float(value) for value in cm_matrix[:6]),
        )
        width = max(font_size, font_size * 0.6 * len(stripped_text))
        height = max(font_size, _MIN_REGION_SIZE)
        region = _rectangle_from_transformed_box(
            combined_transform,
            width=width,
            height=height,
        )
        if region is not None:
            regions.append(region)

    source_page.extract_text(visitor_text=visitor_text)
    return regions


def _get_inherited_page_resources(source_page):
    page_object = source_page
    while page_object is not None:
        resources = page_object.get("/Resources")
        if resources is not None:
            return resources.get_object()
        parent = page_object.get("/Parent")
        page_object = parent.get_object() if parent is not None else None
    return None


def _region_from_xobject(xobject, current_transform) -> _Rectangle | None:
    subtype = xobject.get("/Subtype")
    if subtype == "/Image":
        return _rectangle_from_transformed_box(current_transform, width=1.0, height=1.0)

    if subtype != "/Form":
        return None

    bbox = xobject.get("/BBox")
    if bbox is None:
        return None

    form_transform = current_transform
    matrix = xobject.get("/Matrix")
    if matrix is not None:
        form_transform = _multiply_transforms(
            tuple(float(value) for value in matrix[:6]),
            current_transform,
        )

    return _rectangle_from_points(
        [
            _apply_transform(form_transform, float(bbox[0]), float(bbox[1])),
            _apply_transform(form_transform, float(bbox[2]), float(bbox[1])),
            _apply_transform(form_transform, float(bbox[0]), float(bbox[3])),
            _apply_transform(form_transform, float(bbox[2]), float(bbox[3])),
        ]
    )


def _multiply_transforms(
    left: Tuple[float, float, float, float, float, float],
    right: Tuple[float, float, float, float, float, float],
) -> Tuple[float, float, float, float, float, float]:
    return (
        (left[0] * right[0]) + (left[1] * right[2]),
        (left[0] * right[1]) + (left[1] * right[3]),
        (left[2] * right[0]) + (left[3] * right[2]),
        (left[2] * right[1]) + (left[3] * right[3]),
        (left[4] * right[0]) + (left[5] * right[2]) + right[4],
        (left[4] * right[1]) + (left[5] * right[3]) + right[5],
    )


def _apply_transform(
    transform: Tuple[float, float, float, float, float, float],
    x: float,
    y: float,
) -> Tuple[float, float]:
    return (
        (x * transform[0]) + (y * transform[2]) + transform[4],
        (x * transform[1]) + (y * transform[3]) + transform[5],
    )


def _rectangle_from_transformed_box(
    transform: Tuple[float, float, float, float, float, float],
    width: float,
    height: float,
) -> _Rectangle | None:
    return _rectangle_from_points(
        [
            _apply_transform(transform, 0.0, 0.0),
            _apply_transform(transform, width, 0.0),
            _apply_transform(transform, 0.0, height),
            _apply_transform(transform, width, height),
        ]
    )


def _rectangle_from_points(points: Sequence[Tuple[float, float]]) -> _Rectangle | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    left = min(xs)
    right = max(xs)
    bottom = min(ys)
    top = max(ys)
    if right - left < _MIN_REGION_SIZE:
        center_x = (left + right) / 2.0
        left = center_x - (_MIN_REGION_SIZE / 2.0)
        right = center_x + (_MIN_REGION_SIZE / 2.0)
    if top - bottom < _MIN_REGION_SIZE:
        center_y = (bottom + top) / 2.0
        bottom = center_y - (_MIN_REGION_SIZE / 2.0)
        top = center_y + (_MIN_REGION_SIZE / 2.0)
    return _Rectangle(left=left, bottom=bottom, right=right, top=top)


def _select_landscape_half_region(
    page_region: _Rectangle,
    content_regions: Sequence[_Rectangle],
) -> _Rectangle | None:
    if page_region.width <= page_region.height or not content_regions:
        return None

    middle_x = page_region.left + (page_region.width / 2.0)
    left_half = _Rectangle(
        left=page_region.left,
        bottom=page_region.bottom,
        right=middle_x,
        top=page_region.top,
    )
    right_half = _Rectangle(
        left=middle_x,
        bottom=page_region.bottom,
        right=page_region.right,
        top=page_region.top,
    )

    left_score = _region_score_within_area(content_regions, left_half)
    right_score = _region_score_within_area(content_regions, right_half)
    total_score = left_score + right_score
    if total_score <= 0:
        return None

    dominant_ratio = max(left_score, right_score) / total_score
    if dominant_ratio < _LANDSCAPE_HALF_DOMINANCE_RATIO:
        return None

    return left_half if left_score >= right_score else right_half


def _region_score_within_area(
    content_regions: Sequence[_Rectangle],
    area: _Rectangle,
) -> float:
    score = 0.0
    for region in content_regions:
        intersection = region.intersection(area)
        if intersection is None:
            continue
        score += max(intersection.area, intersection.width, intersection.height)
    return score


def _trim_crop_region_to_content(
    crop_region: _Rectangle,
    content_regions: Sequence[_Rectangle],
) -> _Rectangle:
    content_bounds = _union_rectangles(
        [
            intersection
            for region in content_regions
            for intersection in [region.intersection(crop_region)]
            if intersection is not None
        ]
    )
    if content_bounds is None:
        return crop_region

    left_margin_ratio = (content_bounds.left - crop_region.left) / crop_region.width
    right_margin_ratio = (crop_region.right - content_bounds.right) / crop_region.width
    bottom_margin_ratio = (content_bounds.bottom - crop_region.bottom) / crop_region.height
    top_margin_ratio = (crop_region.top - content_bounds.top) / crop_region.height
    content_width_ratio = content_bounds.width / crop_region.width
    content_height_ratio = content_bounds.height / crop_region.height

    shrink_x = (
        content_width_ratio < _CONTENT_OCCUPANCY_CROP_THRESHOLD
        or (
            left_margin_ratio >= _SYMMETRIC_MARGIN_CROP_THRESHOLD
            and right_margin_ratio >= _SYMMETRIC_MARGIN_CROP_THRESHOLD
        )
    )
    shrink_y = (
        content_height_ratio < _CONTENT_OCCUPANCY_CROP_THRESHOLD
        or (
            bottom_margin_ratio >= _SYMMETRIC_MARGIN_CROP_THRESHOLD
            and top_margin_ratio >= _SYMMETRIC_MARGIN_CROP_THRESHOLD
        )
    )
    if not shrink_x and not shrink_y:
        return crop_region

    padding = _content_padding_for(crop_region)
    padded_bounds = _expand_rectangle_within(content_bounds, padding, crop_region)
    return _Rectangle(
        left=padded_bounds.left if shrink_x else crop_region.left,
        bottom=padded_bounds.bottom if shrink_y else crop_region.bottom,
        right=padded_bounds.right if shrink_x else crop_region.right,
        top=padded_bounds.top if shrink_y else crop_region.top,
    )


def _content_padding_for(region: _Rectangle) -> float:
    return min(
        _MAX_CONTENT_PADDING,
        max(_MIN_CONTENT_PADDING, max(region.width, region.height) * _CONTENT_PADDING_RATIO),
    )


def _expand_rectangle_within(
    rectangle: _Rectangle,
    padding: float,
    bounds: _Rectangle,
) -> _Rectangle:
    return _Rectangle(
        left=max(bounds.left, rectangle.left - padding),
        bottom=max(bounds.bottom, rectangle.bottom - padding),
        right=min(bounds.right, rectangle.right + padding),
        top=min(bounds.top, rectangle.top + padding),
    )


def _union_rectangles(rectangles: Sequence[_Rectangle]) -> _Rectangle | None:
    if not rectangles:
        return None
    return _Rectangle(
        left=min(rect.left for rect in rectangles),
        bottom=min(rect.bottom for rect in rectangles),
        right=max(rect.right for rect in rectangles),
        top=max(rect.top for rect in rectangles),
    )


def _rectangles_close(left: _Rectangle, right: _Rectangle) -> bool:
    return (
        abs(left.left - right.left) <= _PAGE_GEOMETRY_EPSILON
        and abs(left.bottom - right.bottom) <= _PAGE_GEOMETRY_EPSILON
        and abs(left.right - right.right) <= _PAGE_GEOMETRY_EPSILON
        and abs(left.top - right.top) <= _PAGE_GEOMETRY_EPSILON
    )


def _load_pypdf() -> Tuple[type, type, type, type]:
    try:
        from pypdf import PdfReader, PdfWriter, Transformation
        from pypdf.generic import RectangleObject
    except ImportError as exc:
        raise DependencyError(
            "缺少 PDF 依赖，请先执行 "
            "'python3 -m pip install pypdf reportlab'。"
        ) from exc

    return PdfReader, PdfWriter, Transformation, RectangleObject


def _load_reportlab_canvas():
    try:
        from reportlab.pdfgen.canvas import Canvas
    except ImportError as exc:
        raise DependencyError(
            "缺少 PDF 依赖，请先执行 "
            "'python3 -m pip install pypdf reportlab'。"
        ) from exc

    return Canvas
