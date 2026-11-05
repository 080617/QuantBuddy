"""Read-only Futu HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .futu_service import FutuReadService, get_futu_read_service
from .schemas import (
    FutuAccountResponse,
    FutuConnectionResponse,
    FutuOrdersResponse,
    FutuPortfolioResponse,
    FutuPositionsResponse,
)


router = APIRouter(prefix="/api/futu", tags=["futu-read-only"])


@router.get("/status", response_model=FutuConnectionResponse)
def get_status(
    service: FutuReadService = Depends(get_futu_read_service),
) -> FutuConnectionResponse:
    return service.status()


@router.get("/account", response_model=FutuAccountResponse)
def get_account(
    service: FutuReadService = Depends(get_futu_read_service),
) -> FutuAccountResponse:
    return service.account()


@router.get("/positions", response_model=FutuPositionsResponse)
def get_positions(
    service: FutuReadService = Depends(get_futu_read_service),
) -> FutuPositionsResponse:
    return service.positions()


@router.get("/orders", response_model=FutuOrdersResponse)
def get_orders(
    service: FutuReadService = Depends(get_futu_read_service),
) -> FutuOrdersResponse:
    return service.orders()


@router.get("/portfolio", response_model=FutuPortfolioResponse)
def get_portfolio(
    service: FutuReadService = Depends(get_futu_read_service),
) -> FutuPortfolioResponse:
    return service.portfolio()

