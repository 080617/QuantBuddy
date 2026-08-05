from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
import unittest

from backend.execution.runtime import build_readonly_futu_plan
from backend.futu.models import AccountSummary, FundsSummary, QuoteSnapshot, TradableQuantity

from backend.tests.execution_test_helpers import artifact, permissive_config, validation


class FakeClient:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None


class ExecutionRuntimeTests(unittest.TestCase):
    def test_runtime_uses_only_read_services_and_builds_dry_run(self) -> None:
        codes = [item.code for item in artifact().signals[:5]]
        account_service = SimpleNamespace(
            get_simulated_cn_account=lambda: AccountSummary(42, "SIMULATE", "CN", "ACTIVE"),
            get_funds=lambda: FundsSummary(100000, 0, 100000, 100000, 0),
            get_positions=lambda: [],
        )
        quote_service = SimpleNamespace(
            get_snapshot=lambda futu_codes: [QuoteSnapshot(code, code, 10.0, 100, False) for code in futu_codes]
        )
        order_service = SimpleNamespace(
            get_recent_orders=lambda: [],
            get_max_tradable_quantity=lambda code, price: TradableQuantity(code, price, 100000, 0, 100),
        )
        with (
            patch("backend.execution.runtime.AccountService", return_value=account_service),
            patch("backend.execution.runtime.QuoteService", return_value=quote_service),
            patch("backend.execution.runtime.OrderService", return_value=order_service),
        ):
            plan = build_readonly_futu_plan(
                artifact=artifact(),
                validation=validation(),
                planning_config=permissive_config(),
                client_factory=FakeClient,
                captured_at="2026-07-31T01:00:00+00:00",
            )
        self.assertTrue(plan.dry_run)
        self.assertEqual({item.code for item in plan.planned_buys}, set(codes))
        self.assertEqual(plan.account_id_masked, "****")
        self.assertFalse(hasattr(order_service, "place_simulated_limit_order"))
        self.assertFalse(hasattr(order_service, "cancel_simulated_order"))


if __name__ == "__main__":
    unittest.main()
