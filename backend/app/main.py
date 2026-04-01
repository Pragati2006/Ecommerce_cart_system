from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.ai import price_sensitivity, recommend_from_cart, upsell_suggestions
from app.catalog import get_product, list_products
from app.pricing import compute_pricing
from app.schemas import (
    CartItemInput,
    CartItemUpdateInput,
    CartMutationResult,
    CartView,
    CheckoutRequest,
    CheckoutResponse,
    PriceSensitivityResponse,
    RecommendationsResponse,
    UpsellResponse,
)
from app.storage import build_cart_store

APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = APP_ROOT / "frontend"

app = FastAPI(title="E-commerce Cart System")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")
store = build_cart_store()

METRICS = {"cart_add_success": 0, "checkout_fail_stock": 0, "checkout_ok": 0}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _owner(owner_id: str | None) -> str:
    return owner_id or "guest_default"


def _read_expected_version(header_value: str | None) -> int | None:
    if header_value is None:
        return None
    try:
        return int(header_value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Cart-Version header") from exc


def _cart_view(owner_id: str, *, discount_codes: list[str] | None = None, estimated: bool = True) -> CartView:
    state = store.get(owner_id)
    enriched = []
    priced_items = []
    for pid, qty in state.items_map.items():
        product = get_product(pid)
        if not product:
            continue
        priced_items.append((product, qty))
        enriched.append(
            {
                "productId": product.product_id,
                "quantity": qty,
                "name": product.name,
                "imageUrl": product.image_url,
                "unitPrice": {"currency": "USD", "amount": product.price_usd},
                "lineTotal": {"currency": "USD", "amount": round(product.price_usd * qty, 2)},
                "inStock": product.in_stock,
                "availableQuantity": product.available_quantity,
            }
        )
    pricing = compute_pricing(priced_items, discount_codes=discount_codes or [])
    rec = recommend_from_cart(state.items_map)
    ups = upsell_suggestions(state.items_map)
    sens = price_sensitivity(state.items_map, pricing.subtotal, (pricing.discount / pricing.subtotal) if pricing.subtotal else 0.0)
    return CartView(
        cartId=state.cart_id,
        ownerId=owner_id,
        currency=state.currency,
        items=enriched,
        itemsMap=state.items_map,
        cartVersion=state.version,
        updatedAt=state.updated_at,
        pricing={
            "subtotal": {"currency": "USD", "amount": pricing.subtotal},
            "discount": {"currency": "USD", "amount": pricing.discount},
            "tax": {"currency": "USD", "amount": pricing.tax},
            "shipping": {"currency": "USD", "amount": pricing.shipping},
            "grandTotal": {"currency": "USD", "amount": pricing.grand_total},
            "isEstimated": estimated,
            "appliedDiscountCodes": pricing.applied_discount_codes,
        },
        ai={
            "recommendations": rec["recommendations"],
            "upsell": ups["suggestions"],
            "priceSensitivity": {"buyProbability": sens["buyProbability"], "segment": sens["segment"]},
            "isCached": rec.get("isCached", False),
        },
    )


@app.get("/", response_class=HTMLResponse)
def product_list_page(request: Request):
    return templates.TemplateResponse("product_list.html", {"request": request, "products": list_products()})


@app.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request):
    return templates.TemplateResponse("cart.html", {"request": request})


@app.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request):
    return templates.TemplateResponse("checkout.html", {"request": request})


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    return METRICS


@app.post("/cart/items", response_model=CartMutationResult)
def add_item(
    payload: CartItemInput,
    ownerId: str | None = Query(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    cart_version: str | None = Header(default=None, alias="X-Cart-Version"),
):
    owner_id = _owner(ownerId)
    product = get_product(payload.productId)
    if not product:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
    if not product.in_stock:
        raise HTTPException(status_code=409, detail="OUT_OF_STOCK")
    if payload.quantity > product.available_quantity:
        raise HTTPException(status_code=409, detail="Requested quantity exceeds available stock")
    state = store.upsert_item(
        owner_id,
        payload.productId,
        payload.quantity,
        mode="increment",
        idempotency_key=idempotency_key,
        expected_version=_read_expected_version(cart_version),
    )
    METRICS["cart_add_success"] += 1
    return CartMutationResult(cartId=state.cart_id, cartVersion=state.version, updatedAt=state.updated_at)


@app.patch("/cart/items/{product_id}", response_model=CartMutationResult)
def update_quantity(
    product_id: str,
    payload: CartItemUpdateInput,
    ownerId: str | None = Query(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    cart_version: str | None = Header(default=None, alias="X-Cart-Version"),
):
    owner_id = _owner(ownerId)
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="PRODUCT_NOT_FOUND")
    if payload.quantity < 0:
        raise HTTPException(status_code=400, detail="INVALID_QUANTITY")
    if payload.quantity == 0:
        state = store.remove_item(owner_id, product_id, idempotency_key=idempotency_key, expected_version=_read_expected_version(cart_version))
        return CartMutationResult(cartId=state.cart_id, cartVersion=state.version, updatedAt=state.updated_at)
    if payload.quantity > product.available_quantity:
        raise HTTPException(status_code=409, detail="Requested quantity exceeds available stock")
    state = store.upsert_item(
        owner_id,
        product_id,
        payload.quantity,
        mode="set",
        idempotency_key=idempotency_key,
        expected_version=_read_expected_version(cart_version),
    )
    return CartMutationResult(cartId=state.cart_id, cartVersion=state.version, updatedAt=state.updated_at)


@app.delete("/cart/items/{product_id}", response_model=CartMutationResult)
def remove_item(
    product_id: str,
    ownerId: str | None = Query(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    cart_version: str | None = Header(default=None, alias="X-Cart-Version"),
):
    state = store.remove_item(
        _owner(ownerId),
        product_id,
        idempotency_key=idempotency_key,
        expected_version=_read_expected_version(cart_version),
    )
    return CartMutationResult(cartId=state.cart_id, cartVersion=state.version, updatedAt=state.updated_at)


@app.get("/api/cart", response_model=CartView)
def get_cart(ownerId: str | None = Query(default=None)):
    return _cart_view(_owner(ownerId), estimated=True)


@app.post("/api/cart/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutRequest, ownerId: str | None = Query(default=None)):
    owner_id = _owner(ownerId)
    state = store.get(owner_id)
    item_errors = []
    priced_items = []
    for pid, qty in state.items_map.items():
        product = get_product(pid)
        if not product:
            item_errors.append({"productId": pid, "reason": "PRODUCT_NOT_FOUND", "message": "Product no longer exists", "availableQuantity": None})
            continue
        if qty <= 0:
            item_errors.append({"productId": pid, "reason": "INVALID_QUANTITY", "message": "Quantity must be > 0", "availableQuantity": product.available_quantity})
            continue
        if (not product.in_stock) or qty > product.available_quantity:
            item_errors.append({"productId": pid, "reason": "OUT_OF_STOCK", "message": "Insufficient stock at checkout", "availableQuantity": product.available_quantity})
            continue
        priced_items.append((product, qty))

    pricing = compute_pricing(priced_items, discount_codes=payload.discountCodes)
    if item_errors:
        METRICS["checkout_fail_stock"] += 1
    else:
        METRICS["checkout_ok"] += 1
    return CheckoutResponse(
        cartId=state.cart_id,
        cartVersion=state.version,
        pricing={
            "subtotal": {"currency": "USD", "amount": pricing.subtotal},
            "discount": {"currency": "USD", "amount": pricing.discount},
            "tax": {"currency": "USD", "amount": pricing.tax},
            "shipping": {"currency": "USD", "amount": pricing.shipping},
            "grandTotal": {"currency": "USD", "amount": pricing.grand_total},
            "isEstimated": False,
            "appliedDiscountCodes": pricing.applied_discount_codes,
        },
        itemErrors=item_errors,
        canProceedToPayment=len(item_errors) == 0,
        pricedAt=_now(),
    )


@app.get("/ai/recommendations", response_model=RecommendationsResponse)
def ai_recommendations(cartId: str | None = Query(default=None), ownerId: str | None = Query(default=None)):
    state = store.get(_owner(ownerId))
    rec = recommend_from_cart(state.items_map)
    return RecommendationsResponse(cartId=cartId or state.cart_id, recommendations=rec["recommendations"], explanations=rec["explanations"], generatedAt=rec["generatedAt"])


@app.get("/ai/upsell", response_model=UpsellResponse)
def ai_upsell(cartId: str | None = Query(default=None), ownerId: str | None = Query(default=None)):
    state = store.get(_owner(ownerId))
    result = upsell_suggestions(state.items_map)
    return UpsellResponse(cartId=cartId or state.cart_id, suggestions=result["suggestions"], generatedAt=result["generatedAt"])


@app.get("/ai/price-sensitivity", response_model=PriceSensitivityResponse)
def ai_price_sensitivity(cartId: str | None = Query(default=None), ownerId: str | None = Query(default=None)):
    view = _cart_view(_owner(ownerId), estimated=True)
    result = price_sensitivity(view.itemsMap, view.pricing.subtotal.amount, (view.pricing.discount.amount / view.pricing.subtotal.amount) if view.pricing.subtotal.amount else 0.0)
    return PriceSensitivityResponse(
        cartId=cartId or view.cartId,
        buyProbability=result["buyProbability"],
        segment=result["segment"],
        generatedAt=result["generatedAt"],
    )

