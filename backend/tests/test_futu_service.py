from __future__ import annotations

from types import SimpleNamespace
import unittest

import pandas as pd

from backend.futu.account_service import AccountService
from backend.futu.client import FutuClient
from backend.futu.config import FutuConfig
from backend.futu.exceptions import FutuSafetyError
from backend.futu.models import PlaceOrderRequest, OrderSide
from backend.futu.order_service import OrderService
from backend.futu.quote_service import QuoteService


SDK = SimpleNamespace(
    RET_OK=0,
    TrdMarket=SimpleNamespace(CN="CN"),
    TrdEnv=SimpleNamespace(SIMULATE="SIMULATE", REAL="REAL"),
    OrderType=SimpleNamespace(NORMAL="NORMAL"),
    TrdSide=SimpleNamespace(BUY="BUY", SELL="SELL"),
    ModifyOrderOp=SimpleNamespace(CANCEL="CANCEL"),
)


class FakeQuoteContext:
    def __init__(self) -> None:
        self.closed = False

    def get_global_state(self):
        return 0, {"server_ver": "test"}

    def get_market_snapshot(self, codes):
        return 0, pd.DataFrame(
            [
                {
                    "code": code,
                    "name": "Mock security",
                    "last_price": 10.5,
                    "lot_size": 100,
                    "suspension": False,
                    "update_time": "2026-08-05 10:00:00",
                }
                for code in codes
            ]
        )

    def close(self) -> None:
        self.closed = True


class FakeTradeContext:
    def __init__(self) -> None:
        self.closed = False
        self.modified = None

    def get_acc_list(self):
        return 0, pd.DataFrame(
            [{"acc_id": 1001, "trd_env": "SIMULATE", "acc_status": "ACTIVE", "trdmarket_auth": ["CN"], "acc_type": "CASH"}]
        )

    def accinfo_query(self, **kwargs):
        return 0, pd.DataFrame(
            [{"total_assets": 100000, "market_val": 20000, "cash": 80000, "power": 80000, "frozen_cash": 0, "currency": "CNY"}]
        )

    def position_list_query(self, **kwargs):
        return 0, pd.DataFrame(
            [{"code": "SH.600104", "stock_name": "SAIC", "qty": 100, "can_sell_qty": 100, "nominal_price": 15, "cost_price": 14, "market_val": 1500, "pl_val": 100, "pl_ratio": 7.14, "currency": "CNY"}]
        )

    def order_list_query(self, **kwargs):
        return 0, pd.DataFrame(
            [{"order_id": "test-order-1", "code": "SH.600104", "stock_name": "SAIC", "trd_side": "BUY", "order_type": "NORMAL", "order_status": "CANCELLED_ALL", "qty": 100, "price": 15, "dealt_qty": 0, "dealt_avg_price": 0, "create_time": "2026-08-05 09:30:00", "updated_time": "2026-08-05 09:31:00", "last_err_msg": ""}]
        )

    def history_order_list_query(self, **kwargs):
        return self.order_list_query(**kwargs)

    def acctradinginfo_query(self, **kwargs):
        return 0, pd.DataFrame([{"max_cash_buy": 1000, "max_position_sell": 100}])

    def place_order(self, **kwargs):
        return 0, pd.DataFrame([{"order_id": "test-order-1", "code": kwargs["code"], "trd_side": kwargs["trd_side"], "qty": kwargs["qty"], "price": kwargs["price"], "order_status": "SUBMITTED"}])

    def modify_order(self, **kwargs):
        self.modified = kwargs
        return 0, pd.DataFrame([{"order_id": kwargs["order_id"]}])

    def close(self) -> None:
        self.closed = True


class ServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.quote = FakeQuoteContext()
        self.trade = FakeTradeContext()
        self.client = FutuClient(
            FutuConfig(), sdk=SDK,
            quote_context_factory=lambda **_: self.quote,
            trade_context_factory=lambda **_: self.trade,
        )

    def test_dataframes_are_converted_to_stable_models(self) -> None:
        account_service = AccountService(self.client)
        account = account_service.get_simulated_cn_account()
        funds = account_service.get_funds()
        positions = account_service.get_positions()
        snapshot = QuoteService(self.client).get_snapshot(["SH.600104"])[0]
        order = OrderService(self.client).get_recent_orders()[0]
        self.assertEqual(account.market, "CN")
        self.assertEqual(funds.cash, 80000)
        self.assertEqual(positions[0].code, "SH.600104")
        self.assertEqual(snapshot.lot_size, 100)
        self.assertEqual(order.order_id, "test-order-1")
        self.assertNotIsInstance(positions, pd.DataFrame)

    def test_context_manager_closes_both_contexts(self) -> None:
        with self.client as client:
            self.assertTrue(client.health_check())
            _ = client.trade_context
        self.assertTrue(self.quote.closed)
        self.assertTrue(self.trade.closed)

    def test_simulated_order_is_disabled_by_default(self) -> None:
        service = OrderService(self.client)
        with self.assertRaises(FutuSafetyError):
            service.place_simulated_limit_order(
                PlaceOrderRequest("SH.600104", OrderSide.BUY, 100, 10)
            )

    def test_enabled_order_refreshes_quote_and_maximum_quantity(self) -> None:
        client = FutuClient(
            FutuConfig(enable_simulated_orders=True), sdk=SDK,
            quote_context_factory=lambda **_: self.quote,
            trade_context_factory=lambda **_: self.trade,
        )
        result = OrderService(client).place_simulated_limit_order(
            PlaceOrderRequest("SH.600104", OrderSide.BUY, 100, 10)
        )
        self.assertEqual(result.status, "SUBMITTED")

    def test_quantity_over_sdk_maximum_is_rejected(self) -> None:
        client = FutuClient(
            FutuConfig(enable_simulated_orders=True, max_simulated_order_amount=100000), sdk=SDK,
            quote_context_factory=lambda **_: self.quote,
            trade_context_factory=lambda **_: self.trade,
        )
        with self.assertRaisesRegex(FutuSafetyError, "exceeds"):
            OrderService(client).place_simulated_limit_order(
                PlaceOrderRequest("SH.600104", OrderSide.BUY, 1100, 10)
            )

    def test_cancel_uses_simulate_only(self) -> None:
        client = FutuClient(
            FutuConfig(enable_simulated_orders=True), sdk=SDK,
            quote_context_factory=lambda **_: self.quote,
            trade_context_factory=lambda **_: self.trade,
        )
        self.assertTrue(OrderService(client).cancel_simulated_order("test-order-1"))
        self.assertEqual(self.trade.modified["trd_env"], "SIMULATE")


if __name__ == "__main__":
    unittest.main()
