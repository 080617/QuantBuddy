from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
import inspect
import json
from pathlib import Path
import tempfile
import unittest

from backend.execution.exceptions import PlanningError
from backend.execution.models import CurrentPosition, ExecutionBlocker
from backend.execution.orchestrator import ShadowOrchestrator, collect_readonly_shadow_snapshot
from backend.execution.orchestrator_models import ExecutionOrderState, ExecutionSessionState, ShadowSnapshot
from backend.execution.orchestrator_precheck import (
    PricePolicyConfig,
    evaluate_order_update,
    next_state_for_order_update,
    run_precheck,
)
from backend.execution.orchestrator_store import load_session, save_session
from backend.execution.order_planner import build_execution_plan
from backend.futu.models import OrderRecord, QuoteSnapshot, TradableQuantity

from backend.tests.execution_test_helpers import account, artifact, permissive_config, validation


FIXED = datetime(2026, 7, 31, 1, 0, tzinfo=timezone.utc)


def quote(code: str, price: float = 10.0, *, suspended: bool = False, lot: int = 100):
    return QuoteSnapshot(code, code, price, lot, suspended, "2026-07-31 09:31:00")


def maximum(code: str, quantity: float = 100_000):
    return TradableQuantity(code, 10.0, quantity, None, 100)


def initial_plan():
    codes = [item.code for item in artifact().signals[:5]]
    return build_execution_plan(
        artifact=artifact(), artifact_validation=validation(), account=account(),
        current_positions=[], recent_orders=[], quotes={code: quote(code) for code in codes},
        maximum_quantities={code: maximum(code) for code in codes}, managed_codes=set(),
        config=permissive_config(),
    )


def rebalance_plan():
    held = [
        CurrentPosition("SH600000", 100, 100, 10, 1000, True),
        CurrentPosition("SH600009", 100, 100, 10, 1000, True),
        CurrentPosition("SH600010", 100, 100, 10, 1000, True),
        CurrentPosition("SH600011", 100, 100, 10, 1000, True),
        CurrentPosition("SH600018", 100, 100, 10, 1000, True),
    ]
    codes = [item.code for item in artifact().signals]
    return build_execution_plan(
        artifact=artifact(), artifact_validation=validation(), account=account(cash=95_000, market_value=5_000),
        current_positions=held, recent_orders=[], quotes={code: quote(code) for code in codes},
        maximum_quantities={"SH600015": maximum("SH600015")},
        managed_codes={item.code for item in held}, config=permissive_config(),
    )


def snapshot(plan, **changes):
    all_orders = plan.planned_sells + plan.planned_buys
    values = dict(
        captured_at=FIXED.isoformat(), execution_date="2026-07-31",
        account=account(cash=plan.cash_before, market_value=plan.market_value_before, total_assets=plan.total_assets_before),
        positions=list(plan.current_positions), recent_orders=[],
        quotes={item.code: quote(item.code, item.limit_reference_price) for item in all_orders},
        maximum_quantities={item.code: maximum(item.code) for item in plan.planned_buys},
    )
    values.update(changes)
    return ShadowSnapshot(**values)


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def orchestrator(self, snap):
        return ShadowOrchestrator(snapshot_provider=lambda plan, day: snap, session_dir=self.output, clock=lambda: FIXED)

    def run_initial(self, snap=None):
        plan = initial_plan()
        return plan, self.orchestrator(snap or snapshot(plan)).run(plan, expected_source_hash=plan.source_hash)

    def test_01_initial_deployment_skips_sell(self):
        _, session = self.run_initial()
        self.assertEqual(session.steps[0].status, "SKIPPED")

    def test_02_rebalance_sells_before_buys(self):
        plan = rebalance_plan()
        session = self.orchestrator(snapshot(plan)).run(plan, expected_source_hash=plan.source_hash)
        events = [item.event_type for item in session.events]
        self.assertLess(events.index("SHADOW_SELL_FILLED"), events.index("SHADOW_SUBMITTING"))

    def test_03_same_plan_has_one_session(self):
        plan = initial_plan()
        paused = snapshot(plan, account=replace(account(), status="DISABLED"))
        first = self.orchestrator(paused).run(plan, expected_source_hash=plan.source_hash)
        second = self.orchestrator(paused).run(plan, expected_source_hash=plan.source_hash)
        self.assertEqual(first.session_id, second.session_id)

    def test_04_completed_session_cannot_run_again(self):
        plan, _ = self.run_initial()
        with self.assertRaises(PlanningError):
            self.orchestrator(snapshot(plan)).run(plan, expected_source_hash=plan.source_hash)

    def test_05_expired_plan_is_rejected(self):
        plan = initial_plan()
        result = run_precheck(plan, snapshot(plan), expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 8, 1))
        self.assertIn("PLAN_EXPIRED", {item.code for item in result.blockers})

    def test_06_future_execution_date_mismatch_is_rejected(self):
        plan = initial_plan()
        result = run_precheck(plan, snapshot(plan), expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 30))
        self.assertIn("EXECUTION_DATE_MISMATCH", {item.code for item in result.blockers})

    def test_07_source_hash_change_is_rejected(self):
        plan = initial_plan()
        result = run_precheck(plan, snapshot(plan), expected_source_hash="b" * 64,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("SOURCE_HASH_CHANGED", {item.code for item in result.blockers})

    def test_08_account_state_change_is_rejected(self):
        plan = initial_plan()
        result = run_precheck(plan, snapshot(plan, account=replace(account(), status="DISABLED")),
                              expected_source_hash=plan.source_hash, price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("ACCOUNT_NOT_ACTIVE", {item.code for item in result.blockers})

    def test_09_cash_shortage_is_rejected(self):
        plan = initial_plan()
        result = run_precheck(plan, snapshot(plan, account=account(cash=1)), expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("INSUFFICIENT_CASH", {item.code for item in result.blockers})

    def test_10_unfinished_order_conflict_is_rejected(self):
        plan = initial_plan(); code = plan.planned_buys[0].code
        pending = OrderRecord("masked", code, None, "BUY", "NORMAL", "SUBMITTED", 100, 10, 0, None, None, None, None)
        result = run_precheck(plan, snapshot(plan, recent_orders=[pending]), expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("UNFINISHED_ORDER_CONFLICT", {item.code for item in result.blockers})

    def test_11_suspended_security_is_rejected(self):
        plan = initial_plan(); snap = snapshot(plan); code = plan.planned_buys[0].code
        snap.quotes[code] = quote(code, suspended=True)
        result = run_precheck(plan, snap, expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("SUSPENDED_SECURITY", {item.code for item in result.blockers})

    def test_12_price_deviation_is_rejected(self):
        plan = initial_plan(); snap = snapshot(plan); code = plan.planned_buys[0].code
        snap.quotes[code] = quote(code, 11.1)
        result = run_precheck(plan, snap, expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("PRICE_DEVIATION_EXCEEDED", {item.code for item in result.blockers})

    def test_13_maximum_buy_is_rejected(self):
        plan = initial_plan(); snap = snapshot(plan); code = plan.planned_buys[0].code
        snap.maximum_quantities[code] = maximum(code, 0)
        result = run_precheck(plan, snap, expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("MAX_BUY_INSUFFICIENT", {item.code for item in result.blockers})

    def test_14_non_lot_quantity_is_rejected(self):
        plan = initial_plan(); plan.planned_buys[0] = replace(plan.planned_buys[0], quantity=plan.planned_buys[0].quantity + 1)
        result = run_precheck(plan, snapshot(plan), expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertIn("INVALID_LOT_QUANTITY", {item.code for item in result.blockers})

    def test_15_unfinished_sell_waits(self):
        self.assertEqual(next_state_for_order_update("SELL", "SUBMITTED"), "WAITING_FOR_SELLS")

    def test_16_partial_buy_waits(self):
        decision = evaluate_order_update("BUY", "PARTIALLY_FILLED", 1000, 400)
        self.assertEqual(decision.next_session_state, "WAITING_FOR_BUYS")
        self.assertEqual(decision.remaining_quantity, 600)
        self.assertFalse(decision.allow_resubmit)

    def test_17_unknown_state_pauses(self):
        self.assertEqual(next_state_for_order_update("BUY", "UNKNOWN"), "PAUSED")

    def test_18_interrupted_session_resumes_same_id(self):
        plan = initial_plan(); paused = snapshot(plan, account=replace(account(), status="DISABLED"))
        first = self.orchestrator(paused).run(plan, expected_source_hash=plan.source_hash)
        resumed = self.orchestrator(snapshot(plan)).run(plan, expected_source_hash=plan.source_hash)
        self.assertEqual(first.session_id, resumed.session_id)
        self.assertEqual(resumed.state, ExecutionSessionState.SHADOW_COMPLETED)

    def test_19_shadow_collector_has_no_place_call(self):
        self.assertNotIn("place_simulated", inspect.getsource(collect_readonly_shadow_snapshot))

    def test_20_shadow_collector_has_no_modify_call(self):
        self.assertNotIn("modify_order", inspect.getsource(collect_readonly_shadow_snapshot))

    def test_21_shadow_collector_has_no_cancel_call(self):
        self.assertNotIn("cancel_simulated", inspect.getsource(collect_readonly_shadow_snapshot))

    def test_22_session_serialization_is_stable(self):
        _, session = self.run_initial()
        loaded = load_session(session.session_id, self.output)
        self.assertEqual(json.dumps(session.to_dict(), sort_keys=True), json.dumps(loaded.to_dict(), sort_keys=True))

    def test_23_event_log_sequences_are_stable(self):
        _, session = self.run_initial()
        lines = (self.output / f"{session.session_id}.events.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["sequence"] for line in lines], list(range(1, len(lines) + 1)))

    def test_24_same_input_has_same_intents(self):
        plan = initial_plan(); snap = snapshot(plan)
        first = self.orchestrator(snap)._create_intents(plan, snap)
        second = self.orchestrator(snap)._create_intents(plan, snap)
        self.assertEqual([item.intent_id for item in first], [item.intent_id for item in second])

    def test_25_cn_simulate_is_enforced(self):
        plan = initial_plan(); snap = snapshot(plan, account=replace(account(), market="US", trading_environment="REAL"))
        result = run_precheck(plan, snap, expected_source_hash=plan.source_hash,
                              price_config=PricePolicyConfig(), effective_date=date(2026, 7, 31))
        self.assertTrue({"NON_CN_MARKET", "REAL_ENVIRONMENT_REJECTED"}.issubset({item.code for item in result.blockers}))

    def test_26_changed_plan_cannot_resume(self):
        plan = initial_plan(); paused = snapshot(plan, account=replace(account(), status="DISABLED"))
        self.orchestrator(paused).run(plan, expected_source_hash=plan.source_hash)
        with self.assertRaises(PlanningError):
            self.orchestrator(paused).run(replace(plan, estimated_cash_after=1), expected_source_hash=plan.source_hash)

    def test_27_shadow_override_is_marked(self):
        plan = initial_plan()
        clock = lambda: datetime(2026, 8, 1, tzinfo=timezone.utc)
        runner = ShadowOrchestrator(snapshot_provider=lambda p, d: snapshot(p), session_dir=self.output, clock=clock)
        session = runner.run(plan, expected_source_hash=plan.source_hash, shadow_date=date(2026, 7, 31))
        self.assertEqual(session.shadow_date_override, "2026-07-31")
        self.assertIn("SHADOW_DATE_OVERRIDE", {item.code for item in session.warnings})


if __name__ == "__main__":
    unittest.main()
