from __future__ import annotations

import re
from typing import List

from .errors import ParseError
from .models import SkuQuantity

ITEM_SEPARATOR_PATTERN = re.compile(r"[，,]")


def render_item_text(item: SkuQuantity) -> str:
    return item.display_text


def parse_items(raw_items: str) -> List[SkuQuantity]:
    if not raw_items or not raw_items.strip():
        raise ParseError("SKU 输入不能为空。")

    chunks = [chunk.strip() for chunk in ITEM_SEPARATOR_PATTERN.split(raw_items)]
    if any(not chunk for chunk in chunks):
        raise ParseError(
            "请使用中文或英文逗号分隔每个 SKU，且不要出现空白项。"
        )

    return [SkuQuantity(sku=chunk) for chunk in chunks]
