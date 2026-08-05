from __future__ import annotations

from dataclasses import replace
import json
import unittest

from backend.execution.models import CurrentPosition, ExecutionBlocker
from backend.execution.order_planner import build_execution_plan
from backend.futu.models import OrderRecord, QuoteSnapshot, TradableQuantity

from backend.tests.execution_test_helpers import account, artifact, permissive_config, validation


def quote(code: str, *, price: float = 10.0, lot: int = 100, suspended: bool = False):
    return QuoteSnapshot(code, code, price, lot, suspended)


def maximum(code: str, quantity: float = 100_000):
    return TradableQuantity(code, 10.0, quantity, None, 100)


class OrderPlannerTests(unittest.TestCase):
    def build(self, **changes):
        codes = [item.code for item in artifact().signals[:5]]
        values = dict(
            artifact=artifact(),
            artifact_validation=validation(),
            account=account(),
            current_positions=[],
            recent_orders=[],
            quotes={code: quote(code) for code in codes},
            maximum_quantities={code: maximum(code) for code in codes},
            managed_codes=set(),
            config=permissive_config(),
        )
        values.update(changes)
        return build_execution_plan(**values)

    def test_empty_portfolio_buys_top_five_in_board_lots(self) -> None:
        plan = self.build()
        self.assertEqual(len(plan.planned_buys), 5)
        self.assertTrue(all(order.quantity > 0 and order.quantity % order.lot_size == 0 for order in plan.planned_buys))
        self.assertTrue(all(order.phase == "BUY_AFTER_SELL_CONFIRMATION" for order in plan.planned_buys))

    def test_below_one_lot_and_maximum_quantity_are_blocked(self) -> None:
        low_cash = self.build(account=account(cash=100.0, total_assets=100.0))
        self.assertIn("INSUFFICIENT_CASH_FOR_ONE_LOT", {item.code for item in low_cash.blockers})
        codes = [item.code for item in artifact().signals[:5]]
        limited = self.build(maximum_quantities={code: maximum(code, 0) for code in codes})
        self.assertIn("MAX_BUY_BELOW_ONE_LOT", {item.code for item in limited.blockers})

    def test_sell_never_exceeds_sellable_quantity(self) -> None:
        held = [
            CurrentPosition("SH600000", 100, 100, 10, 1000, True),
            CurrentPosition("SH600009", 100, 100, 10, 1000, True),
            CurrentPosition("SH600010", 100, 100, 10, 1000, True),
            CurrentPosition("SH600011", 100, 100, 10, 1000, True),
            CurrentPosition("SH600018", 200, 100, 10, 2000, True),
        ]
        quotes = {item.code: quote(item.code) for item in artifact().signals}
        plan = self.build(
            current_positions=held,
            managed_codes={item.code for item in held},
            quotes=quotes,
            maximum_quantities={"SH600015": maximum("SH600015")},
        )
        self.assertIn("INSUFFICIENT_SELLABLE_QUANTITY", {item.code for item in plan.blockers})
        self.assertEqual(plan.planned_sells[0].quantity, 100)

    def test_suspended_missing_price_and_unfinished_order_block(self) -> None:
        codes = [item.code for item in artifact().signals[:5]]
        quotes = {code: quote(code) for code in codes}
        quotes[codes[0]] = quote(codes[0], suspended=True)
        quotes.pop(codes[1])
        pending = OrderRecord("masked", codes[2], None, "BUY", "NORMAL", "SUBMITTED", 100, 10, 0, None, None, None, None)
        plan = self.build(quotes=quotes, recent_orders=[pending])
        blocker_codes = {item.code for item in plan.blockers}
        self.assertIn("SUSPENDED_SECURITY", blocker_codes)
        self.assertIn("MISSING_PRICE", blocker_codes)
        self.assertIn("UNFINISHED_ORDER_CONFLICT", blocker_codes)

    def test_same_inputs_have_same_plan_id_and_stable_json(self) -> None:
        first = self.build()
        second = self.build()
        self.assertEqual(first.plan_id, second.plan_id)
        self.assertEqual(
            json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")),
            json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")),
        )

    def test_validation_blocker_keeps_plan_non_executable(self) -> None:
        blocked = validation(blockers=[ExecutionBlocker("STALE_SIGNAL", "Signal is stale.")])
        plan = self.build(artifact_validation=blocked)
        self.assertFalse(plan.executable)
        self.assertIn("STALE_SIGNAL", {item.code for item in plan.blockers})


if __name__ == "__main__":
    unittest.main()
