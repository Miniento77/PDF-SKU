from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

from .errors import DependencyError, LayoutError
from .models import SkuQuantity
from .parsing import render_item_text

TextMeasure = Callable[[str, str, float], float]


@dataclass(frozen=True)
class LayoutConfig:
    font_name: str = "Helvetica-Bold"
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


@dataclass(frozen=True)
class FooterLayout:
    font_name: str
    font_size: float
    lines: Sequence[FooterLine]
    footer_height: float
    line_spacing: float
    horizontal_padding: float
    vertical_padding: float


@dataclass(frozen=True)
class _Partition:
    line_ranges: Sequence[Tuple[int, int]]
    max_unit_width: float


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
    unit_widths = _build_unit_widths(rendered_items, config, measure)

    candidates: List[FooterLayout] = []
    line_limit = min(config.max_lines, len(rendered_items))
    for line_count in range(1, line_limit + 1):
        partition = _find_best_partition(unit_widths, len(rendered_items), line_count)
        if partition is None:
            continue

        if partition.max_unit_width <= 0:
            font_size = config.max_font_size
        else:
            font_size = min(config.max_font_size, usable_width / partition.max_unit_width)

        font_size = _round_down_tenth(font_size)
        if font_size < config.min_font_size:
            continue

        lines = [
            FooterLine(
                text=", ".join(rendered_items[start:end]),
                width=unit_widths[(start, end)] * font_size,
            )
            for start, end in partition.line_ranges
        ]
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
            )
        )

    if not candidates:
        raise LayoutError(
            "当前配置下，SKU 内容无法在允许的宽度、字号范围和最大行数内完成排版。"
        )

    return max(candidates, key=lambda layout: (layout.font_size, -len(layout.lines)))


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


def _build_unit_widths(
    rendered_items: Sequence[str],
    config: LayoutConfig,
    measure_text: TextMeasure,
) -> Dict[Tuple[int, int], float]:
    widths: Dict[Tuple[int, int], float] = {}
    item_count = len(rendered_items)
    for start in range(item_count):
        for end in range(start + 1, item_count + 1):
            line_text = ", ".join(rendered_items[start:end])
            widths[(start, end)] = float(measure_text(line_text, config.font_name, 1.0))
    return widths


def _find_best_partition(
    unit_widths: Dict[Tuple[int, int], float],
    item_count: int,
    line_count: int,
) -> _Partition | None:
    infinity = math.inf
    dp = [[infinity] * (item_count + 1) for _ in range(line_count + 1)]
    previous = [[-1] * (item_count + 1) for _ in range(line_count + 1)]
    dp[0][0] = 0.0

    for used_lines in range(1, line_count + 1):
        for end in range(1, item_count + 1):
            for start in range(used_lines - 1, end):
                prior = dp[used_lines - 1][start]
                if math.isinf(prior):
                    continue
                line_width = unit_widths[(start, end)]
                cost = max(prior, line_width)
                if cost < dp[used_lines][end]:
                    dp[used_lines][end] = cost
                    previous[used_lines][end] = start

    if math.isinf(dp[line_count][item_count]):
        return None

    ranges: List[Tuple[int, int]] = []
    end = item_count
    used_lines = line_count
    while used_lines > 0:
        start = previous[used_lines][end]
        if start < 0:
            return None
        ranges.append((start, end))
        end = start
        used_lines -= 1

    ranges.reverse()
    return _Partition(line_ranges=ranges, max_unit_width=dp[line_count][item_count])


def _round_down_tenth(value: float) -> float:
    return math.floor(value * 10.0) / 10.0
