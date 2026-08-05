from __future__ import annotations

from dataclasses import replace
import tempfile
from pathlib import Path
import unittest

from backend.execution.exceptions import PlanningError
from backend.execution.models import PlannedOrder
from backend.execution.order_planner import build_execution_plan
from backend.execution.persistence import save_execution_plan
from backend.execution.safety import collect_execution_safety_blockers

from backend.futu.models import QuoteSnapshot, TradableQuantity

from backend.tests.execution_test_helpers import account, artifact, permissive_config, validation


def order(**changes):
    values = dict(
        sequence=1,
        phase="BUY_AFTER_SELL_CONFIRMATION",
        side="BUY",
        code="SH600000",
        quantity=100,
        limit_reference_price=10.0,
        lot_size=100,
        estimated_value=1000.0,
        estimated_fee=5.0,
        reason="test",
    )
    values.update(changes)
    return PlannedOrder(**values)


class ExecutionSafetyTests(unittest.TestCase):
    def blocker_codes(self, **changes):
        values = dict(
            account=account(),
            strategy_id="strategy-hs300-lightgbm-top5",
            orders=[order()],
            config=permissive_config(),
            dry_run=True,
        )
        values.update(changes)
        return {item.code for item in collect_execution_safety_blockers(**values)}

    def test_real_non_cn_inactive_and_non_dry_run_are_rejected(self) -> None:
        codes = self.blocker_codes(
            account=account(market="US", trading_environment="REAL", status="DISABLED"), dry_run=False
        )
        expected = {"NON_CN_MARKET", "REAL_ENVIRONMENT_REJECTED", "ACCOUNT_NOT_ACTIVE", "DRY_RUN_REQUIRED"}
        self.assertTrue(expected.issubset(codes))

    def test_invalid_lot_price_and_order_caps_are_rejected(self) -> None:
        bad = order(quantity=150, limit_reference_price=0, estimated_value=2000)
        config = permissive_config(max_single_order_amount=1000, max_daily_planned_amount=1000)
        codes = self.blocker_codes(orders=[bad], config=config)
        expected = {"INVALID_LOT_QUANTITY", "INVALID_PRICE", "SINGLE_ORDER_LIMIT_EXCEEDED", "DAILY_PLAN_LIMIT_EXCEEDED"}
        self.assertTrue(expected.issubset(codes))

    def test_persistence_is_non_overwriting_and_summary_declares_no_writes(self) -> None:
        item = artifact()
        codes = [signal.code for signal in item.signals[:5]]
        plan = build_execution_plan(
            artifact=item,
            artifact_validation=validation(),
            account=account(),
            current_positions=[],
            recent_orders=[],
            quotes={code: QuoteSnapshot(code, code, 10, 100, False) for code in codes},
            maximum_quantities={code: TradableQuantity(code, 10, 100000, None, 100) for code in codes},
            managed_codes=set(),
            config=permissive_config(),
        )
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            output = Path(directory)
            json_path, summary_path = save_execution_plan(plan, output)
            self.assertEqual(save_execution_plan(plan, output), (json_path, summary_path))
            summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("NO ORDER SUBMITTED", summary)
            self.assertIn("NO ORDER MODIFIED", summary)
            self.assertIn("NO ORDER CANCELLED", summary)
            with self.assertRaises(PlanningError):
                save_execution_plan(replace(plan, executable=not plan.executable), output)


if __name__ == "__main__":
    unittest.main()
