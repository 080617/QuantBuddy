"""Order reads and explicitly named, safety-gated simulated writes."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .account_service import AccountService
from .client import FutuClient
from .code_mapper import validate_futu_code
from .exceptions import FutuApiError, FutuSafetyError
from .models import (
    OrderRecord,
    OrderSide,
    PlaceOrderRequest,
    PlaceOrderResult,
    TradableQuantity,
    number,
    rows,
    value,
)
from .quote_service import QuoteService
from .safety import require_cn_simulate, validate_maximum_quantity, validate_order_input


class OrderService:
    def __init__(self, client: FutuClient) -> None:
        self.client = client
        self.accounts = AccountService(client)
        self.quotes = QuoteService(client)

    def _orders(self, frame: Any) -> list[OrderRecord]:
        return [
            OrderRecord(
                order_id=str(value(row, "order_id", "")),
                code=str(value(row, "code", "")),
                name=str(value(row, "stock_name")) if value(row, "stock_name") is not None else None,
                side=str(value(row, "trd_side", "")),
                order_type=str(value(row, "order_type", "")),
                status=str(value(row, "order_status", "")),
                quantity=number(row, "qty") or 0.0,
                price=number(row, "price") or 0.0,
                dealt_quantity=number(row, "dealt_qty") or 0.0,
                dealt_average_price=number(row, "dealt_avg_price"),
                created_at=str(value(row, "create_time")) if value(row, "create_time") else None,
                updated_at=str(value(row, "updated_time")) if value(row, "updated_time") else None,
                error_message=str(value(row, "last_err_msg")) if value(row, "last_err_msg") else None,
            )
            for row in rows(frame)
        ]

    def get_recent_orders(self) -> list[OrderRecord]:
        account = self.accounts.get_simulated_cn_account()
        frame = self.client.ensure_ok(
            self.client.trade_context.order_list_query(
                order_market=self.client.sdk.TrdMarket.CN,
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
                refresh_cache=False,
            ),
            "get_recent_orders",
        )
        return self._orders(frame)

    def get_historical_orders(self, *, days: int = 30) -> list[OrderRecord]:
        if days <= 0:
            raise ValueError("days must be positive")
        account = self.accounts.get_simulated_cn_account()
        end = datetime.now()
        start = end - timedelta(days=days)
        frame = self.client.ensure_ok(
            self.client.trade_context.history_order_list_query(
                order_market=self.client.sdk.TrdMarket.CN,
                start=start.strftime("%Y-%m-%d %H:%M:%S"),
                end=end.strftime("%Y-%m-%d %H:%M:%S"),
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
            ),
            "get_historical_orders",
        )
        return self._orders(frame)

    def get_max_tradable_quantity(self, code: str, price: float) -> TradableQuantity:
        code = validate_futu_code(code)
        if price <= 0:
            raise FutuSafetyError("Price must be greater than zero.")
        account = self.accounts.get_simulated_cn_account()
        frame = self.client.ensure_ok(
            self.client.trade_context.acctradinginfo_query(
                order_type=self.client.sdk.OrderType.NORMAL,
                code=code,
                price=price,
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
            ),
            "get_max_tradable_quantity",
        )
        returned_rows = rows(frame)
        if not returned_rows:
            raise FutuApiError("No tradable quantity was returned.")
        row = returned_rows[0]
        maximum = number(row, "max_cash_buy")
        if maximum is None:
            raise FutuApiError("max_cash_buy is missing from the SDK response.")
        return TradableQuantity(
            code=code,
            price=price,
            maximum_cash_buy=maximum,
            maximum_position_sell=number(row, "max_position_sell"),
            lot_size=self.quotes.get_lot_size(code),
        )

    def place_simulated_limit_order(self, request: PlaceOrderRequest) -> PlaceOrderResult:
        snapshots = self.quotes.get_snapshot([request.code])
        if len(snapshots) != 1:
            raise FutuApiError("Could not refresh the market snapshot before order placement.")
        snapshot = snapshots[0]
        if snapshot.suspended:
            raise FutuSafetyError("The requested security is suspended.")
        code = validate_order_input(
            config=self.client.config,
            code=request.code,
            quantity=request.quantity,
            price=request.price,
            lot_size=snapshot.lot_size,
        )
        tradable = self.get_max_tradable_quantity(code, request.price)
        if request.side == OrderSide.BUY:
            validate_maximum_quantity(request.quantity, tradable.maximum_cash_buy)
        account = self.accounts.get_simulated_cn_account()
        side = self.client.sdk.TrdSide.BUY if request.side == OrderSide.BUY else self.client.sdk.TrdSide.SELL
        frame = self.client.ensure_ok(
            self.client.trade_context.place_order(
                price=request.price,
                qty=request.quantity,
                code=code,
                trd_side=side,
                order_type=self.client.sdk.OrderType.NORMAL,
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
            ),
            "place_simulated_limit_order",
        )
        returned_rows = rows(frame)
        if not returned_rows:
            raise FutuApiError("Order placement returned no order record.")
        row = returned_rows[0]
        return PlaceOrderResult(
            order_id=str(value(row, "order_id", "")),
            code=str(value(row, "code", code)),
            side=str(value(row, "trd_side", request.side.value)),
            quantity=number(row, "qty") or float(request.quantity),
            price=number(row, "price") or request.price,
            status=str(value(row, "order_status", "SUBMITTED")),
        )

    def get_order(self, order_id: str) -> OrderRecord | None:
        if not order_id:
            raise ValueError("order_id is required")
        matches = [order for order in self.get_recent_orders() if order.order_id == str(order_id)]
        return matches[0] if matches else None

    def cancel_simulated_order(self, order_id: str) -> bool:
        require_cn_simulate(self.client.config.market, self.client.config.trading_environment)
        if not self.client.config.enable_simulated_orders:
            raise FutuSafetyError("Simulated order writes are disabled.")
        if not order_id:
            raise ValueError("order_id is required")
        account = self.accounts.get_simulated_cn_account()
        self.client.ensure_ok(
            self.client.trade_context.modify_order(
                modify_order_op=self.client.sdk.ModifyOrderOp.CANCEL,
                order_id=order_id,
                qty=0,
                price=0,
                trd_env=self.client.sdk.TrdEnv.SIMULATE,
                acc_id=account.account_id,
            ),
            "cancel_simulated_order",
        )
        return True
