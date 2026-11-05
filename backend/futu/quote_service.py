"""Read-only market quote service."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Callable
from zoneinfo import ZoneInfo

from .client import FutuClient
from .code_mapper import validate_futu_code
from .exceptions import FutuApiError
from .models import (
    OrderBookAcquisition,
    OrderBookDiagnostics,
    OrderBookTop,
    QuoteSnapshot,
    number,
    rows,
    value,
)


def _parse_futu_server_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return parsed.astimezone(timezone.utc)


class QuoteService:
    def __init__(self, client: FutuClient) -> None:
        self.client = client

    def get_snapshot(self, codes: list[str]) -> list[QuoteSnapshot]:
        normalized = [validate_futu_code(code) for code in codes]
        if not normalized:
            return []
        frame = self.client.ensure_ok(
            self.client.quote_context.get_market_snapshot(normalized), "get_snapshot"
        )
        snapshots: list[QuoteSnapshot] = []
        for row in rows(frame):
            price = number(row, "last_price")
            lot_size = number(row, "lot_size")
            if price is None or lot_size is None:
                raise FutuApiError("Snapshot is missing last_price or lot_size.")
            snapshots.append(
                QuoteSnapshot(
                    code=validate_futu_code(str(value(row, "code"))),
                    name=str(value(row, "name", "")),
                    last_price=price,
                    lot_size=int(lot_size),
                    suspended=bool(value(row, "suspension", False)),
                    update_time=str(value(row, "update_time")) if value(row, "update_time") else None,
                    price_spread=number(row, "price_spread"),
                )
            )
        return snapshots

    def get_lot_size(self, code: str) -> int:
        snapshots = self.get_snapshot([code])
        if len(snapshots) != 1:
            raise FutuApiError(f"Expected one snapshot for {code!r}.")
        return snapshots[0].lot_size

    def get_order_book_top(self, code: str) -> OrderBookTop:
        acquisition = self.acquire_fresh_order_book_top(code)
        if acquisition.order_book is None:
            raise FutuApiError(f"Order book has no valid ask for {code}.")
        return acquisition.order_book

    def acquire_fresh_order_book_top(
        self,
        code: str,
        *,
        freshness_threshold_seconds: int = 15,
        acquisition_timeout_seconds: int = 10,
        poll_interval_seconds: float = 1.0,
        maximum_attempts: int = 10,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        sleeper: Callable[[float], None] = time.sleep,
    ) -> OrderBookAcquisition:
        """Subscribe once and wait, boundedly, for a timestamped fresh best ask."""
        if freshness_threshold_seconds <= 0 or acquisition_timeout_seconds <= 0:
            raise ValueError("Freshness threshold and acquisition timeout must be positive.")
        if poll_interval_seconds <= 0 or maximum_attempts <= 0:
            raise ValueError("Polling interval and maximum attempts must be positive.")
        code = validate_futu_code(code)
        sdk = self.client.sdk
        self.client.ensure_ok(
            self.client.quote_context.subscribe([code], [sdk.SubType.ORDER_BOOK], is_first_push=False),
            "subscribe_order_book",
        )
        first_ask_time: str | None = None
        final_ask_time: str | None = None
        final_age: float | None = None
        final_best_ask: float | None = None
        fresh_top: OrderBookTop | None = None
        started_at = clock()
        attempt_count = 0

        for attempt in range(1, maximum_attempts + 1):
            attempt_count = attempt
            payload = self.client.ensure_ok(
                self.client.quote_context.get_order_book(code, num=1), "get_order_book_top"
            )
            asks = payload.get("Ask", []) if isinstance(payload, dict) else []
            raw_time = payload.get("svr_recv_time_ask") if isinstance(payload, dict) else None
            ask_time = str(raw_time) if raw_time else None
            if attempt == 1:
                first_ask_time = ask_time
            final_ask_time = ask_time
            parsed_time = _parse_futu_server_time(ask_time)
            now = clock().astimezone(timezone.utc)
            final_age = abs((now - parsed_time).total_seconds()) if parsed_time else None

            best_ask: float | None = None
            ask_volume = 0.0
            if asks:
                first = asks[0]
                if isinstance(first, (tuple, list)) and len(first) >= 2:
                    try:
                        best_ask = float(first[0])
                        ask_volume = float(first[1])
                    except (TypeError, ValueError):
                        best_ask = None
            final_best_ask = best_ask
            if best_ask is not None and best_ask > 0:
                current_top = OrderBookTop(
                    code=code,
                    best_ask=best_ask,
                    ask_volume=ask_volume,
                    server_time=ask_time,
                )
                if parsed_time is not None and final_age is not None and final_age <= freshness_threshold_seconds:
                    fresh_top = current_top
                    break

            elapsed = (clock() - started_at).total_seconds()
            if attempt >= maximum_attempts or elapsed + poll_interval_seconds > acquisition_timeout_seconds:
                break
            sleeper(poll_interval_seconds)

        diagnostics = OrderBookDiagnostics(
            subscription_succeeded=True,
            order_book_attempt_count=attempt_count,
            first_order_book_ask_time=first_ask_time,
            final_order_book_ask_time=final_ask_time,
            final_order_book_age_seconds=final_age,
            best_ask=final_best_ask,
            freshness_threshold_seconds=freshness_threshold_seconds,
            acquisition_timeout_seconds=acquisition_timeout_seconds,
        )
        return OrderBookAcquisition(order_book=fresh_top, diagnostics=diagnostics)
