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
        raise ParseError("Manual SKU input cannot be blank.")

    chunks = [chunk.strip() for chunk in raw_items.split(",")]
    if any(not chunk for chunk in chunks):
        raise ParseError(
            "Each item must look like 'SKU x2' and items must be comma-separated."
        )

    parsed_items: List[SkuQuantity] = []
    for chunk in chunks:
        match = ITEM_PATTERN.fullmatch(chunk)
        if match is None:
            raise ParseError(
                f"Could not parse '{chunk}'. Expected format like 'SF601 x2'."
            )

        sku = match.group("sku").strip()
        quantity = int(match.group("qty"))
        if quantity < 1:
            raise ParseError(f"Quantity must be at least 1 for '{sku}'.")

        parsed_items.append(SkuQuantity(sku=sku, quantity=quantity))

    return parsed_items

