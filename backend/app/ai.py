from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone

from app.catalog import PRODUCTS, Product, get_product


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


TRANSACTIONS: list[set[str]] = [
    {"p100", "p102"},
    {"p100", "p101", "p102"},
    {"p200", "p201"},
    {"p200", "p202"},
    {"p300", "p301"},
    {"p300", "p302"},
    {"p100", "p200"},
    {"p100", "p300"},
    {"p102", "p300"},
    {"p201", "p202"},
]


@dataclass
class Rule:
    antecedent: tuple[str, ...]
    consequent: tuple[str, ...]
    support: float
    confidence: float
    lift: float


def _support(itemset: set[str], txns: list[set[str]]) -> float:
    if not txns:
        return 0.0
    return sum(1 for txn in txns if itemset.issubset(txn)) / len(txns)


def generate_rules(min_support: float = 0.1, min_confidence: float = 0.2) -> list[Rule]:
    rules: list[Rule] = []
    ids = list(PRODUCTS.keys())
    for a in ids:
        for b in ids:
            if a == b:
                continue
            sup_a = _support({a}, TRANSACTIONS)
            sup_b = _support({b}, TRANSACTIONS)
            sup_ab = _support({a, b}, TRANSACTIONS)
            if sup_ab < min_support or sup_a == 0 or sup_b == 0:
                continue
            confidence = sup_ab / sup_a
            if confidence < min_confidence:
                continue
            rules.append(
                Rule(
                    antecedent=(a,),
                    consequent=(b,),
                    support=round(sup_ab, 4),
                    confidence=round(confidence, 4),
                    lift=round(confidence / sup_b, 4),
                )
            )
    return sorted(rules, key=lambda r: (r.lift, r.confidence, r.support), reverse=True)


RULE_CACHE = generate_rules()
AI_CACHE: dict[str, dict] = {}


def _hash_items(items_map: dict[str, int]) -> str:
    payload = "|".join(f"{k}:{v}" for k, v in sorted(items_map.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def recommend_from_cart(items_map: dict[str, int], top_k: int = 5) -> dict:
    key = f"rec:{_hash_items(items_map)}"
    if key in AI_CACHE:
        return {**AI_CACHE[key], "isCached": True}

    cart_ids = {k for k, v in items_map.items() if v > 0}
    candidates: dict[str, Rule] = {}
    for rule in RULE_CACHE:
        target = rule.consequent[0]
        if set(rule.antecedent).issubset(cart_ids) and target not in cart_ids:
            prev = candidates.get(target)
            if not prev or (rule.lift, rule.confidence) > (prev.lift, prev.confidence):
                candidates[target] = rule

    ranked = sorted(candidates.items(), key=lambda x: (x[1].lift, x[1].confidence), reverse=True)[:top_k]
    recommendations = [pid for pid, _ in ranked if get_product(pid) and get_product(pid).in_stock]
    explanations = [
        {
            "antecedent": list(rule.antecedent),
            "consequent": list(rule.consequent),
            "support": rule.support,
            "confidence": rule.confidence,
            "lift": rule.lift,
        }
        for _, rule in ranked
    ]
    payload = {"recommendations": recommendations, "explanations": explanations, "generatedAt": utcnow(), "isCached": False}
    AI_CACHE[key] = payload
    return payload


def upsell_suggestions(items_map: dict[str, int], price_cap_ratio: float = 2.0) -> dict:
    suggestions = []
    for pid, qty in items_map.items():
        if qty <= 0:
            continue
        base = get_product(pid)
        if not base:
            continue
        candidates: list[Product] = []
        cap = base.price_usd * (1 + price_cap_ratio)
        for p in PRODUCTS.values():
            if p.product_id == base.product_id or not p.in_stock:
                continue
            if p.category != base.category or p.brand_tier < base.brand_tier:
                continue
            if p.price_usd <= base.price_usd or p.price_usd > cap:
                continue
            candidates.append(p)
        candidates.sort(key=lambda x: (x.brand_tier, x.price_usd), reverse=True)
        if candidates:
            top = candidates[0]
            suggestions.append(
                {
                    "baseProductId": base.product_id,
                    "suggestedProductId": top.product_id,
                    "reason": "Higher tier option in same category within price guardrail",
                    "priceDelta": {"currency": "USD", "amount": round(top.price_usd - base.price_usd, 2)},
                }
            )
    return {"suggestions": suggestions, "generatedAt": utcnow()}


def price_sensitivity(items_map: dict[str, int], subtotal: float, discount_ratio: float) -> dict:
    item_count = sum(max(v, 0) for v in items_map.values())
    x = -0.8 + 0.03 * min(subtotal, 400) + 0.25 * min(item_count, 10) - 2.0 * discount_ratio
    prob = round(float(1 / (1 + math.exp(-x))), 4)
    segment = "highSensitivity" if prob < 0.35 else "neutral" if prob < 0.70 else "lowSensitivity"
    return {"buyProbability": prob, "segment": segment, "generatedAt": utcnow()}

