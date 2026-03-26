from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkuQuantity:
    sku: str
    quantity: int | None = None

    def __post_init__(self) -> None:
        cleaned = self.sku.strip()
        if not cleaned:
            raise ValueError("SKU 不能为空。")
        if self.quantity is not None and self.quantity < 1:
            raise ValueError("数量至少要为 1。")
        object.__setattr__(self, "sku", cleaned)

    @property
    def display_text(self) -> str:
        if self.quantity is None:
            return self.sku
        return f"{self.sku} x{self.quantity}"
