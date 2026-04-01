from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, PositiveInt


CurrencyCode = Literal["USD", "INR", "EUR"]


class Money(BaseModel):
    currency: CurrencyCode = "USD"
    amount: float = Field(ge=0)


class CartItemInput(BaseModel):
    productId: str = Field(min_length=1)
    quantity: PositiveInt


class CartItemUpdateInput(BaseModel):
    quantity: int = Field(ge=0)


class CartItemView(BaseModel):
    productId: str
    quantity: int = Field(ge=0)
    name: str
    imageUrl: str | None = None
    unitPrice: Money
    lineTotal: Money
    inStock: bool
    availableQuantity: int | None = Field(default=None, ge=0)


class PricingSummary(BaseModel):
    subtotal: Money
    discount: Money
    tax: Money
    shipping: Money
    grandTotal: Money
    isEstimated: bool = True
    appliedDiscountCodes: list[str] = Field(default_factory=list)


class CartAIBlock(BaseModel):
    recommendations: list[str] = Field(default_factory=list)
    upsell: list[dict[str, Any]] = Field(default_factory=list)
    priceSensitivity: dict[str, Any] | None = None
    isCached: bool = True


class CartView(BaseModel):
    cartId: str
    ownerId: str
    currency: CurrencyCode = "USD"
    items: list[CartItemView]
    itemsMap: dict[str, int]
    cartVersion: int = Field(ge=0)
    updatedAt: datetime
    pricing: PricingSummary
    ai: CartAIBlock | None = None


class CartMutationResult(BaseModel):
    cartId: str
    cartVersion: int = Field(ge=0)
    updatedAt: datetime


class CheckoutRequest(BaseModel):
    discountCodes: list[str] = Field(default_factory=list, max_length=10)


class CheckoutItemError(BaseModel):
    productId: str
    reason: Literal["OUT_OF_STOCK", "INVALID_QUANTITY", "PRODUCT_NOT_FOUND"]
    message: str
    availableQuantity: int | None = None


class CheckoutResponse(BaseModel):
    cartId: str
    cartVersion: int
    pricing: PricingSummary
    itemErrors: list[CheckoutItemError] = Field(default_factory=list)
    canProceedToPayment: bool
    pricedAt: datetime


class AssociationRuleExplanation(BaseModel):
    antecedent: list[str]
    consequent: list[str]
    support: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    lift: float = Field(ge=0)


class RecommendationsResponse(BaseModel):
    cartId: str
    recommendations: list[str]
    explanations: list[AssociationRuleExplanation] = Field(default_factory=list)
    generatedAt: datetime


class UpsellSuggestion(BaseModel):
    baseProductId: str
    suggestedProductId: str
    reason: str
    priceDelta: Money


class UpsellResponse(BaseModel):
    cartId: str
    suggestions: list[UpsellSuggestion]
    generatedAt: datetime


class PriceSensitivityResponse(BaseModel):
    cartId: str
    buyProbability: float = Field(ge=0, le=1)
    segment: Literal["highSensitivity", "neutral", "lowSensitivity"]
    generatedAt: datetime

