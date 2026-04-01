from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    product_id: str
    name: str
    price_usd: float
    category: str
    brand_tier: int
    image_url: str | None = None
    in_stock: bool = True
    available_quantity: int = 100


PRODUCTS: dict[str, Product] = {
    "p100": Product("p100", "Basic T-Shirt", 12.99, "apparel", 1, None, True, 50),
    "p101": Product("p101", "Premium T-Shirt", 24.99, "apparel", 3, None, True, 25),
    "p102": Product("p102", "Jeans", 39.99, "apparel", 2, None, True, 20),
    "p200": Product("p200", "Wireless Mouse", 19.99, "electronics", 1, None, True, 40),
    "p201": Product("p201", "Ergonomic Mouse", 34.99, "electronics", 2, None, True, 30),
    "p202": Product("p202", "Gaming Mouse", 59.99, "electronics", 3, None, True, 15),
    "p300": Product("p300", "Coffee Beans 250g", 9.99, "grocery", 1, None, True, 80),
    "p301": Product("p301", "Coffee Beans 1kg", 29.99, "grocery", 2, None, True, 60),
    "p302": Product("p302", "Specialty Coffee 250g", 16.99, "grocery", 3, None, True, 10),
    "p999": Product("p999", "Limited Edition Item", 199.99, "special", 3, None, False, 0),
}


def get_product(product_id: str) -> Product | None:
    return PRODUCTS.get(product_id)


def list_products() -> list[Product]:
    return list(PRODUCTS.values())

