from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Sequence

from .errors import DependencyError, LayoutError
from .models import SkuQuantity
from .parsing import render_item_text

TextMeasure = Callable[[str, str, float], float]


@dataclass(frozen=True)
class LayoutConfig:
    font_name: str = "Helvetica"
    min_font_size: float = 12.0
    max_font_size: float = 28.0
    max_lines: int = 4
    horizontal_padding: float = 18.0
    vertical_padding: float = 12.0
    line_spacing: float = 1.15
    min_footer_height: float = 60.0


@dataclass(frozen=True)
class FooterLine:
    text: str
    width: float
    cells: Sequence["FooterCell"] = field(default_factory=tuple)


@dataclass(frozen=True)
class FooterCell:
    text: str
    width: float
    column_index: int


@dataclass(frozen=True)
class FooterLayout:
    font_name: str
    font_size: float
    lines: Sequence[FooterLine]
    footer_height: float
    line_spacing: float
    horizontal_padding: float
    vertical_padding: float
    column_widths: Sequence[float] = field(default_factory=tuple)
    column_gap: float = 0.0


_MAX_ITEMS_PER_ROW = 4
_COLUMN_GAP_EM = 1.6


def measure_text_reportlab(text: str, font_name: str, font_size: float) -> float:
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth
    except ImportError as exc:
        raise DependencyError(
            "缺少 PDF 依赖，请先执行 "
            "'python3 -m pip install pypdf reportlab'。"
        ) from exc

    return float(stringWidth(text, font_name, font_size))


def choose_footer_layout(
    items: Sequence[SkuQuantity],
    page_width: float,
    config: LayoutConfig | None = None,
    measure_text: TextMeasure | None = None,
) -> FooterLayout:
    if not items:
        raise LayoutError("至少需要一条 SKU 项目才能生成底部内容。")

    config = config or LayoutConfig()
    validate_layout_config(config)

    usable_width = page_width - (2 * config.horizontal_padding)
    if usable_width <= 0:
        raise LayoutError("当前左右边距过大，底部文字已没有可用空间。")

    measure = measure_text or measure_text_reportlab
    rendered_items = [render_item_text(item) for item in items]
    unit_widths = [
        float(measure(text, config.font_name, 1.0))
        for text in rendered_items
    ]

    candidates: List[FooterLayout] = []
    max_columns = min(_MAX_ITEMS_PER_ROW, len(rendered_items))
    min_columns = max(1, math.ceil(len(rendered_items) / config.max_lines))

    for column_count in range(min_columns, max_columns + 1):
        rows = [
            (
                rendered_items[index:index + column_count],
                unit_widths[index:index + column_count],
            )
            for index in range(0, len(rendered_items), column_count)
        ]
        if len(rows) > config.max_lines:
            continue

        column_unit_widths = [0.0] * column_count
        for row_texts, row_unit_widths in rows:
            for column_index, _ in enumerate(row_texts):
                column_unit_widths[column_index] = max(
                    column_unit_widths[column_index],
                    row_unit_widths[column_index],
                )

        total_unit_width = sum(column_unit_widths) + (
            max(0, column_count - 1) * _COLUMN_GAP_EM
        )
        if total_unit_width <= 0:
            font_size = config.max_font_size
        else:
            font_size = min(config.max_font_size, usable_width / total_unit_width)

        font_size = _round_down_tenth(font_size)
        if font_size < config.min_font_size:
            continue

        column_widths = [width * font_size for width in column_unit_widths]
        column_gap = _COLUMN_GAP_EM * font_size
        lines: List[FooterLine] = []
        for row_texts, row_unit_widths in rows:
            cells = [
                FooterCell(
                    text=text,
                    width=unit_widths_at_index * font_size,
                    column_index=column_index,
                )
                for column_index, (text, unit_widths_at_index) in enumerate(
                    zip(row_texts, row_unit_widths)
                )
            ]
            lines.append(
                FooterLine(
                    text=" | ".join(row_texts),
                    width=sum(column_widths[:len(row_texts)])
                    + (max(0, len(row_texts) - 1) * column_gap),
                    cells=cells,
                )
            )

        footer_height = max(
            config.min_footer_height,
            (2 * config.vertical_padding)
            + font_size
            + ((len(lines) - 1) * font_size * config.line_spacing),
        )
        candidates.append(
            FooterLayout(
                font_name=config.font_name,
                font_size=font_size,
                lines=lines,
                footer_height=footer_height,
                line_spacing=config.line_spacing,
                horizontal_padding=config.horizontal_padding,
                vertical_padding=config.vertical_padding,
                column_widths=column_widths,
                column_gap=column_gap,
            )
        )

    if not candidates:
        raise LayoutError(
            "当前配置下，SKU 内容无法在允许的宽度、字号范围、最大行数和每行最多 4 项的限制内完成排版。"
        )

    return max(
        candidates,
        key=lambda layout: (
            layout.font_size,
            len(layout.column_widths),
            -len(layout.lines),
        ),
    )


def validate_layout_config(config: LayoutConfig) -> None:
    if config.min_font_size <= 0 or config.max_font_size <= 0:
        raise ValueError("字号必须大于 0。")
    if config.min_font_size > config.max_font_size:
        raise ValueError("最小字号不能大于最大字号。")
    if config.max_lines < 1:
        raise ValueError("最大行数至少要为 1。")
    if config.horizontal_padding < 0 or config.vertical_padding < 0:
        raise ValueError("边距不能为负数。")
    if config.line_spacing < 1:
        raise ValueError("行距至少要为 1。")
    if config.min_footer_height <= 0:
        raise ValueError("底部最小高度必须大于 0。")


def _round_down_tenth(value: float) -> float:
    return math.floor(value * 10.0) / 10.0
