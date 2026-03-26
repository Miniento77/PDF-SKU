from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .errors import DependencyError, LayoutError, ParseError
from .layout import LayoutConfig
from .parsing import parse_items
from .pdf_ops import append_footer_to_label


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "为单页快递面单 PDF 增加底部区域，并为 4x6 面单打印排入 "
            "SKU 与数量信息。"
        )
    )
    parser.add_argument("input_pdf", type=Path, help="输入的单页 PDF 面单路径。")
    parser.add_argument("output_pdf", type=Path, help="输出 PDF 的保存路径。")
    parser.add_argument(
        "items",
        help="SKU 与数量文本，使用英文逗号分隔，例如 'SF601 x2, BJ601DRY x1'。",
    )
    parser.add_argument("--min-font-size", type=float, default=LayoutConfig.min_font_size)
    parser.add_argument("--max-font-size", type=float, default=LayoutConfig.max_font_size)
    parser.add_argument("--max-lines", type=int, default=LayoutConfig.max_lines)
    parser.add_argument(
        "--horizontal-padding",
        type=float,
        default=LayoutConfig.horizontal_padding,
    )
    parser.add_argument(
        "--vertical-padding",
        type=float,
        default=LayoutConfig.vertical_padding,
    )
    parser.add_argument(
        "--footer-min-height",
        type=float,
        default=LayoutConfig.min_footer_height,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        items = parse_items(args.items)
        layout = append_footer_to_label(
            input_pdf=args.input_pdf,
            output_pdf=args.output_pdf,
            items=items,
            config=LayoutConfig(
                min_font_size=args.min_font_size,
                max_font_size=args.max_font_size,
                max_lines=args.max_lines,
                horizontal_padding=args.horizontal_padding,
                vertical_padding=args.vertical_padding,
                min_footer_height=args.footer_min_height,
            ),
        )
    except (DependencyError, LayoutError, ParseError, OSError, ValueError) as exc:
        parser.exit(1, f"错误：{exc}\n")

    print(
        "已生成 "
        f"{args.output_pdf} "
        f"，共 {len(layout.lines)} 行底部内容，字号为 {layout.font_size:.1f}pt。"
    )
    return 0
