"""Stable Python models returned by the Futu service boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class AccountSummary:
    account_id: int
    environment: str
    market: str
    status: str
    account_type: str | None = None


@dataclass(frozen=True, slots=True)
class FundsSummary:
    total_assets: float | None
    market_value: float | None
    cash: float | None
    buying_power: float | None
    frozen_cash: float | None
    currency: str | None = "CNY"


@dataclass(frozen=True, slots=True)
class Position:
    code: str
    name: str
    quantity: float
    sellable_quantity: float
    current_price: float | None
    cost_price: float | None
    market_value: float | None
    profit_loss: float | None
    profit_loss_ratio: float | None
    currency: str | None


@dataclass(frozen=True, slots=True)
class QuoteSnapshot:
    code: str
    name: str
    last_price: float
    lot_size: int
    suspended: bool
    update_time: str | None = None


@dataclass(frozen=True, slots=True)
class OrderRecord:
    order_id: str
    code: str
    name: str | None
    side: str
    order_type: str
    status: str
    quantity: float
    price: float
    dealt_quantity: float
    dealt_average_price: float | None
    created_at: str | None
    updated_at: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class TradableQuantity:
    code: str
    price: float
    maximum_cash_buy: float
    maximum_position_sell: float | None
    lot_size: int


@dataclass(frozen=True, slots=True)
class PlaceOrderRequest:
    code: str
    side: OrderSide
    quantity: int
    price: float


@dataclass(frozen=True, slots=True)
class PlaceOrderResult:
    order_id: str
    code: str
    side: str
    quantity: float
    price: float
    status: str


def value(row: Any, key: str, default: Any = None) -> Any:
    """Read a DataFrame row or mapping without leaking pandas past this module."""
    try:
        candidate = row.get(key, default)
    except AttributeError:
        candidate = default
    try:
        if candidate != candidate:  # NaN
            return default
    except (TypeError, ValueError):
        pass
    return candidate


def number(row: Any, key: str) -> float | None:
    candidate = value(row, key)
    if candidate is None:
        return None
    try:
        return float(candidate)
    except (TypeError, ValueError):
        return None


def rows(frame: Any) -> list[Any]:
    if frame is None:
        return []
    if hasattr(frame, "empty") and frame.empty:
        return []
    if hasattr(frame, "iterrows"):
        return [row for _, row in frame.iterrows()]
    if isinstance(frame, list):
        return frame
    return [frame]
