"""Environment-only configuration for the Futu service."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .exceptions import FutuConfigurationError


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise FutuConfigurationError(f"Invalid boolean configuration value: {value!r}")


@dataclass(frozen=True, slots=True)
class FutuConfig:
    host: str = "127.0.0.1"
    port: int = 11111
    market: str = "CN"
    trading_environment: str = "SIMULATE"
    account_id: int | None = None
    enable_simulated_orders: bool = False
    max_simulated_order_amount: float = 100_000.0

    def __post_init__(self) -> None:
        if self.market.upper() != "CN":
            raise FutuConfigurationError("Only FUTU_MARKET=CN is supported.")
        if self.trading_environment.upper() != "SIMULATE":
            raise FutuConfigurationError("Only FUTU_TRD_ENV=SIMULATE is supported.")
        if not 1 <= self.port <= 65535:
            raise FutuConfigurationError("FUTU_PORT must be between 1 and 65535.")
        if self.max_simulated_order_amount <= 0:
            raise FutuConfigurationError("FUTU_MAX_SIMULATED_ORDER_AMOUNT must be positive.")

    @classmethod
    def from_env(cls) -> "FutuConfig":
        account_text = os.getenv("FUTU_ACCOUNT_ID", "").strip()
        try:
            account_id = int(account_text) if account_text else None
            port = int(os.getenv("FUTU_PORT", "11111"))
            max_amount = float(os.getenv("FUTU_MAX_SIMULATED_ORDER_AMOUNT", "100000"))
        except ValueError as exc:
            raise FutuConfigurationError("Numeric Futu configuration is invalid.") from exc
        return cls(
            host=os.getenv("FUTU_HOST", "127.0.0.1"),
            port=port,
            market=os.getenv("FUTU_MARKET", "CN"),
            trading_environment=os.getenv("FUTU_TRD_ENV", "SIMULATE"),
            account_id=account_id,
            enable_simulated_orders=_as_bool(os.getenv("FUTU_ENABLE_SIMULATED_ORDERS")),
            max_simulated_order_amount=max_amount,
        )
