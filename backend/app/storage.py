from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from redis import Redis


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class CartState:
    cart_id: str
    owner_id: str
    currency: str
    items_map: dict[str, int]
    version: int
    updated_at: datetime


class CartStore:
    def get(self, owner_id: str) -> CartState:
        raise NotImplementedError

    def upsert_item(
        self,
        owner_id: str,
        product_id: str,
        new_quantity: int,
        *,
        mode: str,
        idempotency_key: str | None,
        expected_version: int | None,
    ) -> CartState:
        raise NotImplementedError

    def remove_item(
        self,
        owner_id: str,
        product_id: str,
        *,
        idempotency_key: str | None,
        expected_version: int | None,
    ) -> CartState:
        raise NotImplementedError


class InMemoryCartStore(CartStore):
    def __init__(self, default_currency: str = "USD", ttl_seconds: int = 60 * 60 * 24):
        self.default_currency = default_currency
        self.ttl_seconds = ttl_seconds
        self.carts: dict[str, dict[str, Any]] = {}
        self.idem: dict[tuple[str, str], CartState] = {}

    def _purge(self, owner_id: str) -> None:
        row = self.carts.get(owner_id)
        if row and (time.time() - float(row["updated_ts"]) > self.ttl_seconds):
            self.carts.pop(owner_id, None)

    def get(self, owner_id: str) -> CartState:
        self._purge(owner_id)
        row = self.carts.get(owner_id)
        if not row:
            state = CartState(f"cart_{owner_id}", owner_id, self.default_currency, {}, 0, utcnow())
            self._save(owner_id, state)
            return state
        return CartState(
            row["cart_id"],
            owner_id,
            row["currency"],
            dict(row["items_map"]),
            int(row["version"]),
            datetime.fromisoformat(row["updated_at"]),
        )

    def _save(self, owner_id: str, state: CartState) -> None:
        self.carts[owner_id] = {
            "cart_id": state.cart_id,
            "currency": state.currency,
            "items_map": dict(state.items_map),
            "version": state.version,
            "updated_at": state.updated_at.isoformat(),
            "updated_ts": time.time(),
        }

    def upsert_item(
        self,
        owner_id: str,
        product_id: str,
        new_quantity: int,
        *,
        mode: str,
        idempotency_key: str | None,
        expected_version: int | None,
    ) -> CartState:
        if idempotency_key and (owner_id, idempotency_key) in self.idem:
            return self.idem[(owner_id, idempotency_key)]
        state = self.get(owner_id)
        if expected_version is not None and expected_version != state.version:
            raise ValueError("CART_VERSION_MISMATCH")
        items = dict(state.items_map)
        if mode == "increment":
            items[product_id] = int(items.get(product_id, 0)) + int(new_quantity)
        elif mode == "set":
            items[product_id] = int(new_quantity)
        else:
            raise ValueError("INVALID_MODE")
        new_state = CartState(state.cart_id, owner_id, state.currency, items, state.version + 1, utcnow())
        self._save(owner_id, new_state)
        if idempotency_key:
            self.idem[(owner_id, idempotency_key)] = new_state
        return new_state

    def remove_item(
        self,
        owner_id: str,
        product_id: str,
        *,
        idempotency_key: str | None,
        expected_version: int | None,
    ) -> CartState:
        if idempotency_key and (owner_id, idempotency_key) in self.idem:
            return self.idem[(owner_id, idempotency_key)]
        state = self.get(owner_id)
        if expected_version is not None and expected_version != state.version:
            raise ValueError("CART_VERSION_MISMATCH")
        items = dict(state.items_map)
        items.pop(product_id, None)
        new_state = CartState(state.cart_id, owner_id, state.currency, items, state.version + 1, utcnow())
        self._save(owner_id, new_state)
        if idempotency_key:
            self.idem[(owner_id, idempotency_key)] = new_state
        return new_state


class RedisCartStore(CartStore):
    def __init__(self, redis: Redis, default_currency: str = "USD", ttl_seconds: int = 60 * 60 * 24):
        self.redis = redis
        self.default_currency = default_currency
        self.ttl_seconds = ttl_seconds

    def _key(self, owner_id: str) -> str:
        return f"cart:{owner_id}"

    def _idem_key(self, owner_id: str, idem: str) -> str:
        return f"cart:idem:{owner_id}:{idem}"

    def get(self, owner_id: str) -> CartState:
        raw = self.redis.get(self._key(owner_id))
        if not raw:
            state = CartState(f"cart_{owner_id}", owner_id, self.default_currency, {}, 0, utcnow())
            self.redis.setex(self._key(owner_id), self.ttl_seconds, json.dumps(self._encode(state)))
            return state
        return self._decode(owner_id, json.loads(raw))

    def upsert_item(self, owner_id: str, product_id: str, new_quantity: int, *, mode: str, idempotency_key: str | None, expected_version: int | None) -> CartState:
        if idempotency_key:
            cached = self.redis.get(self._idem_key(owner_id, idempotency_key))
            if cached:
                return self._decode(owner_id, json.loads(cached))
        state = self.get(owner_id)
        if expected_version is not None and expected_version != state.version:
            raise ValueError("CART_VERSION_MISMATCH")
        items = dict(state.items_map)
        if mode == "increment":
            items[product_id] = int(items.get(product_id, 0)) + int(new_quantity)
        elif mode == "set":
            items[product_id] = int(new_quantity)
        else:
            raise ValueError("INVALID_MODE")
        updated = CartState(state.cart_id, owner_id, state.currency, items, state.version + 1, utcnow())
        self.redis.setex(self._key(owner_id), self.ttl_seconds, json.dumps(self._encode(updated)))
        if idempotency_key:
            self.redis.setex(self._idem_key(owner_id, idempotency_key), 600, json.dumps(self._encode(updated)))
        return updated

    def remove_item(self, owner_id: str, product_id: str, *, idempotency_key: str | None, expected_version: int | None) -> CartState:
        if idempotency_key:
            cached = self.redis.get(self._idem_key(owner_id, idempotency_key))
            if cached:
                return self._decode(owner_id, json.loads(cached))
        state = self.get(owner_id)
        if expected_version is not None and expected_version != state.version:
            raise ValueError("CART_VERSION_MISMATCH")
        items = dict(state.items_map)
        items.pop(product_id, None)
        updated = CartState(state.cart_id, owner_id, state.currency, items, state.version + 1, utcnow())
        self.redis.setex(self._key(owner_id), self.ttl_seconds, json.dumps(self._encode(updated)))
        if idempotency_key:
            self.redis.setex(self._idem_key(owner_id, idempotency_key), 600, json.dumps(self._encode(updated)))
        return updated

    def _encode(self, state: CartState) -> dict[str, Any]:
        return {"cart_id": state.cart_id, "currency": state.currency, "items_map": state.items_map, "version": state.version, "updated_at": state.updated_at.isoformat()}

    def _decode(self, owner_id: str, data: dict[str, Any]) -> CartState:
        return CartState(data["cart_id"], owner_id, data.get("currency", self.default_currency), {str(k): int(v) for k, v in data.get("items_map", {}).items()}, int(data.get("version", 0)), datetime.fromisoformat(data["updated_at"]))


def build_cart_store() -> CartStore:
    import os

    url = os.getenv("REDIS_URL")
    if not url:
        return InMemoryCartStore()
    try:
        redis = Redis.from_url(url, decode_responses=True)
        redis.ping()
        return RedisCartStore(redis)
    except Exception:
        return InMemoryCartStore()

