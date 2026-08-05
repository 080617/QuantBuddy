"""Explicit lifecycle management for Futu quote and trade contexts."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any, Callable

from .config import FutuConfig
from .exceptions import FutuApiError, FutuConnectionError


class FutuClient:
    """Owns Futu contexts; importing this module never connects to OpenD."""

    def __init__(
        self,
        config: FutuConfig | None = None,
        *,
        sdk: ModuleType | Any | None = None,
        quote_context_factory: Callable[..., Any] | None = None,
        trade_context_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config or FutuConfig.from_env()
        self._sdk = sdk
        self._quote_factory = quote_context_factory
        self._trade_factory = trade_context_factory
        self._quote_context: Any | None = None
        self._trade_context: Any | None = None

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            try:
                self._sdk = import_module("futu")
            except ImportError as exc:
                raise FutuConnectionError(
                    "futu-api is not installed. Install backend requirements first."
                ) from exc
        return self._sdk

    @property
    def quote_context(self) -> Any:
        if self._quote_context is None:
            factory = self._quote_factory or self.sdk.OpenQuoteContext
            try:
                self._quote_context = factory(host=self.config.host, port=self.config.port)
            except Exception as exc:
                raise FutuConnectionError(
                    f"Could not open quote context at {self.config.host}:{self.config.port}."
                ) from exc
        return self._quote_context

    @property
    def trade_context(self) -> Any:
        if self._trade_context is None:
            factory = self._trade_factory or self.sdk.OpenSecTradeContext
            try:
                self._trade_context = factory(
                    filter_trdmarket=self.sdk.TrdMarket.CN,
                    host=self.config.host,
                    port=self.config.port,
                )
            except Exception as exc:
                raise FutuConnectionError(
                    f"Could not open CN trade context at {self.config.host}:{self.config.port}."
                ) from exc
        return self._trade_context

    def ensure_ok(self, result: tuple[Any, Any], operation: str) -> Any:
        result_code, data = result
        if result_code != self.sdk.RET_OK:
            raise FutuApiError(f"Futu SDK operation {operation!r} failed: {data}")
        return data

    def health_check(self) -> bool:
        data = self.ensure_ok(self.quote_context.get_global_state(), "health_check")
        return data is not None

    def close(self) -> None:
        errors: list[Exception] = []
        for attribute in ("_quote_context", "_trade_context"):
            context = getattr(self, attribute)
            if context is not None:
                try:
                    context.close()
                except Exception as exc:  # close both contexts before surfacing an error
                    errors.append(exc)
                finally:
                    setattr(self, attribute, None)
        if errors:
            raise FutuConnectionError("One or more Futu contexts could not be closed.") from errors[0]

    def __enter__(self) -> "FutuClient":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
