"""Mandatory CN/SIMULATE safety checks for every write operation."""

from __future__ import annotations

from typing import Any, Iterable

from .code_mapper import validate_futu_code
from .config import FutuConfig
from .exceptions import AccountSelectionError, FutuSafetyError
from .models import value


def enum_text(candidate: Any) -> str:
    text = str(candidate).upper()
    return text.rsplit(".", 1)[-1]


def require_cn_simulate(market: Any, environment: Any) -> None:
    if enum_text(market) != "CN":
        raise FutuSafetyError("Safety stop: only the CN market is allowed.")
    if enum_text(environment) != "SIMULATE":
        raise FutuSafetyError("Safety stop: REAL trading is never allowed.")


def has_cn_authorization(candidate: Any) -> bool:
    values = candidate if isinstance(candidate, (list, tuple, set)) else [candidate]
    return any(enum_text(item) == "CN" for item in values)


def select_unique_active_cn_simulated_account(
    accounts: Iterable[Any], requested_account_id: int | None = None
) -> Any:
    eligible = [
        row
        for row in accounts
        if enum_text(value(row, "trd_env")) == "SIMULATE"
        and enum_text(value(row, "acc_status")) == "ACTIVE"
        and has_cn_authorization(value(row, "trdmarket_auth"))
    ]
    if requested_account_id is not None:
        eligible = [row for row in eligible if int(value(row, "acc_id", -1)) == requested_account_id]
    if len(eligible) != 1:
        raise AccountSelectionError(
            "Safety stop: expected exactly one active CN simulated account, "
            f"found {len(eligible)}."
        )
    require_cn_simulate("CN", value(eligible[0], "trd_env"))
    return eligible[0]


def validate_order_input(
    *, config: FutuConfig, code: str, quantity: int, price: float, lot_size: int
) -> str:
    require_cn_simulate(config.market, config.trading_environment)
    if not config.enable_simulated_orders:
        raise FutuSafetyError(
            "Simulated order writes are disabled. Set FUTU_ENABLE_SIMULATED_ORDERS=true explicitly."
        )
    normalized = validate_futu_code(code)
    if quantity <= 0:
        raise FutuSafetyError("Order quantity must be greater than zero.")
    if lot_size <= 0 or quantity % lot_size != 0:
        raise FutuSafetyError(f"Order quantity must be a multiple of lot_size={lot_size}.")
    if price <= 0:
        raise FutuSafetyError("Order price must be greater than zero.")
    if quantity * price > config.max_simulated_order_amount:
        raise FutuSafetyError("Simulated order exceeds the configured single-order amount limit.")
    return normalized


def validate_maximum_quantity(quantity: int, maximum: float) -> None:
    if quantity > maximum:
        raise FutuSafetyError(
            f"Order quantity {quantity} exceeds maximum tradable quantity {maximum:g}."
        )


def mask_identifier(value_to_mask: Any, visible: int = 4) -> str:
    text = str(value_to_mask)
    if not text:
        return "****"
    if len(text) <= visible:
        return "*" * max(visible, len(text))
    return f"{'*' * (len(text) - visible)}{text[-visible:]}"
