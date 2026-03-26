from __future__ import annotations

import re
from typing import List

from .errors import ParseError
from .models import SkuQuantity

ITEM_PATTERN = re.compile(r"^(?P<sku>.+?)\s*[xX]\s*(?P<qty>\d+)\s*$")


def render_item_text(item: SkuQuantity) -> str:
    return item.display_text


def parse_items(raw_items: str) -> List[SkuQuantity]:
    if not raw_items or not raw_items.strip():
        raise ParseError("SKU 输入不能为空。")

    chunks = [chunk.strip() for chunk in raw_items.split(",")]
    if any(not chunk for chunk in chunks):
        raise ParseError(
            "每一项都必须是类似“SKU x2”的格式，并使用英文逗号分隔。"
        )

    parsed_items: List[SkuQuantity] = []
    for chunk in chunks:
        match = ITEM_PATTERN.fullmatch(chunk)
        if match is None:
            raise ParseError(
                f"无法解析“{chunk}”，正确格式应类似“SF601 x2”。"
            )

        sku = match.group("sku").strip()
        quantity = int(match.group("qty"))
        if quantity < 1:
            raise ParseError(f"“{sku}”的数量至少要为 1。")

        parsed_items.append(SkuQuantity(sku=sku, quantity=quantity))

    return parsed_items
