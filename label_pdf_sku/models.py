from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkuQuantity:
    sku: str
    quantity: int

    def __post_init__(self) -> None:
        cleaned = self.sku.strip()
        if not cleaned:
            raise ValueError("SKU cannot be blank.")
        if self.quantity < 1:
            raise ValueError("Quantity must be at least 1.")
        object.__setattr__(self, "sku", cleaned)

    @property
    def display_text(self) -> str:
        return f"{self.sku} x{self.quantity}"

