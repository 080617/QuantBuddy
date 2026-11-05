"""Stable public response schemas for the read-only Futu API."""

from __future__ import annotations

from pydantic import BaseModel


class FutuConnectionResponse(BaseModel):
    connected: bool
    openD: bool
    market: str
    environment: str
    accountStatus: str | None = None
    reason: str | None = None


class FutuAccountResponse(BaseModel):
    accountIdMasked: str
    market: str
    environment: str
    accountType: str | None = None
    status: str
    totalAssets: float | None = None
    cash: float | None = None
    marketValue: float | None = None


class FutuPositionResponse(BaseModel):
    code: str
    name: str
    quantity: float
    canSellQuantity: float
    price: float | None = None
    costPrice: float | None = None
    marketValue: float | None = None
    profitLoss: float | None = None
    profitLossPercent: float | None = None


class FutuPositionsResponse(BaseModel):
    positions: list[FutuPositionResponse]
    count: int


class FutuOrderResponse(BaseModel):
    orderIdMasked: str
    code: str
    name: str | None = None
    side: str
    status: str
    quantity: float
    price: float
    dealtQuantity: float
    dealtAveragePrice: float | None = None
    createdAt: str | None = None


class FutuOrdersResponse(BaseModel):
    orders: list[FutuOrderResponse]
    count: int


class FutuPortfolioResponse(BaseModel):
    connection: FutuConnectionResponse
    account: FutuAccountResponse
    positions: list[FutuPositionResponse]
    orders: list[FutuOrderResponse]

