from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.catalog import Product


@dataclass
class PricingResult:
    subtotal: float
    discount: float
    tax: float
    shipping: float
    grand_total: float
    applied_discount_codes: list[str]


def compute_pricing(
    items: Iterable[tuple[Product, int]],
    *,
    discount_codes: list[str] | None = None,
) -> PricingResult:
    discount_codes = discount_codes or []
    subtotal = 0.0
    for product, qty in items:
        subtotal += product.price_usd * qty

    discount = 0.0
    applied: list[str] = []
    if "SAVE10" in discount_codes:
        discount += subtotal * 0.10
        applied.append("SAVE10")
    if "FLAT5" in discount_codes:
        discount += 5.0
        applied.append("FLAT5")
    discount = min(discount, subtotal)

    taxable_amount = max(subtotal - discount, 0.0)
    tax = taxable_amount * 0.08
    shipping = 0.0 if taxable_amount >= 50 else 4.99
    grand_total = taxable_amount + tax + shipping

    return PricingResult(
        subtotal=round(subtotal, 2),
        discount=round(discount, 2),
        tax=round(tax, 2),
        shipping=round(shipping, 2),
        grand_total=round(grand_total, 2),
        applied_discount_codes=applied,
    )

