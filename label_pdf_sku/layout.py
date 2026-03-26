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
            "Missing PDF dependency. Install with "
            "'python3 -m pip install pypdf reportlab'."
        ) from exc

    return float(stringWidth(text, font_name, font_size))


def choose_footer_layout(
    items: Sequence[SkuQuantity],
    page_width: float,
    config: LayoutConfig | None = None,
    measure_text: TextMeasure | None = None,
) -> FooterLayout:
    if not items:
        raise LayoutError("At least one SKU item is required to build a footer.")

    config = config or LayoutConfig()
    _validate_config(config)

    usable_width = page_width - (2 * config.horizontal_padding)
    if usable_width <= 0:
        raise LayoutError("Configured horizontal padding leaves no room for footer text.")

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
            "Footer items do not fit within the configured width, font-size bounds, "
            "and line-count limit."
        )

    return max(candidates, key=lambda layout: (layout.font_size, -len(layout.lines)))


def _validate_config(config: LayoutConfig) -> None:
    if config.min_font_size <= 0 or config.max_font_size <= 0:
        raise ValueError("Font sizes must be positive.")
    if config.min_font_size > config.max_font_size:
        raise ValueError("min_font_size cannot be greater than max_font_size.")
    if config.max_lines < 1:
        raise ValueError("max_lines must be at least 1.")
    if config.horizontal_padding < 0 or config.vertical_padding < 0:
        raise ValueError("Padding cannot be negative.")
    if config.line_spacing < 1:
        raise ValueError("line_spacing must be at least 1.")
    if config.min_footer_height <= 0:
        raise ValueError("min_footer_height must be positive.")


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

