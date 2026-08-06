"""Phase 2D-A shadow-only execution orchestrator.

This module intentionally exposes no real or simulated order-write command and
never calls place, modify, or cancel APIs.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable

from backend.futu import AccountService, FutuClient, OrderService, QuoteService
from backend.futu.code_mapper import futu_to_qlib, qlib_to_futu
from backend.futu.models import QuoteSnapshot, TradableQuantity
from backend.futu.safety import mask_identifier

from .artifact_loader import find_latest_artifact, load_execution_artifact
from .exceptions import PlanningError
from .models import AccountState, CurrentPosition, ExecutionPlan
from .orchestrator_models import (
    ExecutionEvent,
    ExecutionOrderIntent,
    ExecutionOrderState,
    ExecutionPricePolicy,
    ExecutionSession,
    ExecutionSessionState,
    ExecutionStep,
    ReconciliationResult,
    ShadowSnapshot,
)
from .orchestrator_precheck import PricePolicyConfig, plan_digest, run_precheck
from .orchestrator_store import DEFAULT_SESSION_DIR, find_session_for_plan, save_session
from .persistence import load_execution_plan


Clock = Callable[[], datetime]
SnapshotProvider = Callable[[ExecutionPlan, date], ShadowSnapshot]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stable_id(prefix: str, payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def collect_readonly_shadow_snapshot(plan: ExecutionPlan, execution_date: date) -> ShadowSnapshot:
    """Read account, orders, quotes, and limits. There is no write-service call."""
    with FutuClient() as client:
        accounts = AccountService(client)
        quotes_service = QuoteService(client)
        orders = OrderService(client)
        account_summary = accounts.get_simulated_cn_account()
        funds = accounts.get_funds()
        positions = [
            CurrentPosition(
                code=futu_to_qlib(item.code),
                quantity=int(item.quantity),
                sellable_quantity=int(item.sellable_quantity),
                reference_price=item.current_price,
                market_value=item.market_value,
                managed=True,
            )
            for item in accounts.get_positions()
        ]
        recent_orders = [replace(item, code=futu_to_qlib(item.code)) for item in orders.get_recent_orders()]
        planned = plan.planned_sells + plan.planned_buys
        codes = sorted({item.code for item in planned})
        raw_quotes = quotes_service.get_snapshot([qlib_to_futu(code) for code in codes]) if codes else []
        quotes = {
            futu_to_qlib(item.code): QuoteSnapshot(
                code=futu_to_qlib(item.code),
                name=item.name,
                last_price=item.last_price,
                lot_size=item.lot_size,
                suspended=item.suspended,
                update_time=item.update_time,
                price_spread=item.price_spread,
            )
            for item in raw_quotes
        }
        maximum_quantities: dict[str, TradableQuantity] = {}
        for order in plan.planned_buys:
            quote = quotes.get(order.code)
            if quote is None or quote.last_price <= 0 or quote.suspended:
                continue
            item = orders.get_max_tradable_quantity(qlib_to_futu(order.code), quote.last_price)
            maximum_quantities[order.code] = TradableQuantity(
                code=order.code,
                price=item.price,
                maximum_cash_buy=item.maximum_cash_buy,
                maximum_position_sell=item.maximum_position_sell,
                lot_size=item.lot_size,
            )
        return ShadowSnapshot(
            captured_at=_utc_now().isoformat(),
            execution_date=execution_date.isoformat(),
            account=AccountState(
                account_id_masked=mask_identifier(account_summary.account_id),
                market=account_summary.market,
                trading_environment=account_summary.environment,
                status=account_summary.status,
                captured_at=_utc_now().isoformat(),
                cash=float(funds.cash or 0.0),
                market_value=float(funds.market_value or 0.0),
                total_assets=float(funds.total_assets or 0.0),
            ),
            positions=positions,
            recent_orders=recent_orders,
            quotes=quotes,
            maximum_quantities=maximum_quantities,
        )


class ShadowOrchestrator:
    def __init__(
        self,
        *,
        snapshot_provider: SnapshotProvider = collect_readonly_shadow_snapshot,
        session_dir: Path = DEFAULT_SESSION_DIR,
        clock: Clock = _utc_now,
        price_config: PricePolicyConfig = PricePolicyConfig(),
    ) -> None:
        self.snapshot_provider = snapshot_provider
        self.session_dir = session_dir
        self.clock = clock
        self.price_config = price_config

    def _event(self, session: ExecutionSession, event_type: str, message: str, intent_id: str | None = None) -> ExecutionEvent:
        event = ExecutionEvent(
            sequence=len(session.events) + 1,
            occurred_at=self.clock().isoformat(),
            event_type=event_type,
            state=session.state.value,
            message=message,
            intent_id=intent_id,
        )
        session.events.append(event)
        return event

    def _transition(self, session: ExecutionSession, state: ExecutionSessionState, message: str) -> ExecutionEvent:
        session.state = state
        return self._event(session, "STATE_TRANSITION", message)

    def _create_intents(self, plan: ExecutionPlan, snapshot: ShadowSnapshot) -> list[ExecutionOrderIntent]:
        intents: list[ExecutionOrderIntent] = []
        for order in plan.planned_sells + plan.planned_buys:
            quote = snapshot.quotes[order.code]
            minimum, maximum = self.price_config.bounds(order.limit_reference_price)
            intents.append(
                ExecutionOrderIntent(
                    intent_id=_stable_id("intent", {
                        "plan_id": plan.plan_id,
                        "source_hash": plan.source_hash,
                        "sequence": order.sequence,
                        "code": order.code,
                        "side": order.side,
                        "quantity": order.quantity,
                    }),
                    plan_id=plan.plan_id,
                    code=order.code,
                    side=order.side,
                    planned_qty=order.quantity,
                    reference_price=order.limit_reference_price,
                    current_price=quote.last_price,
                    relative_deviation=(quote.last_price / order.limit_reference_price - 1.0),
                    maximum_allowed_price=maximum,
                    minimum_allowed_price=minimum,
                    lot_size=order.lot_size,
                    estimated_amount=order.estimated_value,
                    sequence=order.sequence,
                    status=ExecutionOrderState.PLANNED,
                    reason=order.reason,
                    source_hash=plan.source_hash,
                )
            )
        return intents

    def run(
        self,
        plan: ExecutionPlan,
        *,
        expected_source_hash: str,
        shadow_date: date | None = None,
    ) -> ExecutionSession:
        current_date = self.clock().date()
        effective_date = shadow_date or current_date
        existing = find_session_for_plan(plan.plan_id, self.session_dir)
        digest = plan_digest(plan)
        if existing:
            if existing.plan_digest != digest or existing.plan_source_hash != plan.source_hash:
                raise PlanningError("Refusing to resume because the input plan changed.")
            if existing.state in {ExecutionSessionState.COMPLETED, ExecutionSessionState.SHADOW_COMPLETED}:
                raise PlanningError("A completed session cannot be executed again.")
            session = existing
            if any(item.status == ExecutionOrderState.UNKNOWN for item in session.order_intents):
                session.state = ExecutionSessionState.PAUSED
                session.failure_reason = "Unknown intent state requires operator reconciliation."
                event = self._event(session, "RESUME_PAUSED", session.failure_reason)
                save_session(session, output_dir=self.session_dir, append_events=[event])
                return session
        else:
            now = self.clock().isoformat()
            session = ExecutionSession(
                schema_version="quantbuddy.execution-session.v1",
                session_id=_stable_id("session", {"plan_id": plan.plan_id, "source_hash": plan.source_hash}),
                plan_id=plan.plan_id,
                strategy_id=plan.strategy_id,
                mode=plan.plan_mode,
                signal_date=plan.signal_date,
                planned_execution_date=plan.planned_execution_date or "",
                created_at=now,
                started_at=None,
                completed_at=None,
                market=plan.market,
                trading_environment=plan.trading_environment,
                account_id_masked=plan.account_id_masked,
                state=ExecutionSessionState.CREATED,
                shadow_mode=True,
                shadow_date_override=(effective_date.isoformat() if shadow_date and shadow_date != current_date else None),
                plan_source_hash=plan.source_hash,
                plan_digest=digest,
                account_snapshot_hash="",
                price_policy=self.price_config.policy,
            )
            created = self._event(session, "SESSION_CREATED", "Shadow execution session created.")
            save_session(session, output_dir=self.session_dir, append_events=[created])

        appended: list[ExecutionEvent] = []
        session.started_at = session.started_at or self.clock().isoformat()
        appended.append(self._transition(session, ExecutionSessionState.PRECHECKING, "Refreshing all read-only precheck inputs."))
        snapshot = self.snapshot_provider(plan, effective_date)
        result = run_precheck(
            plan,
            snapshot,
            expected_source_hash=expected_source_hash,
            price_config=self.price_config,
            effective_date=effective_date,
            shadow_override=session.shadow_date_override is not None,
        )
        session.account_snapshot_hash = result.account_snapshot_hash
        session.blockers = result.blockers
        session.warnings = list(plan.warnings) + result.warnings
        if result.blockers:
            immutable = {"PLAN_NOT_DRY_RUN", "PLAN_NOT_EXECUTABLE", "SOURCE_HASH_CHANGED", "REAL_ENVIRONMENT_REJECTED"}
            state = ExecutionSessionState.FAILED if any(item.code in immutable for item in result.blockers) else ExecutionSessionState.PAUSED
            session.failure_reason = "; ".join(f"{item.code}: {item.message}" for item in result.blockers)
            appended.append(self._transition(session, state, "Precheck blocked shadow execution."))
            save_session(session, output_dir=self.session_dir, append_events=appended)
            return session

        session.order_intents = self._create_intents(plan, snapshot)
        appended.append(self._transition(session, ExecutionSessionState.READY, "Precheck passed; deterministic intents created."))
        now = self.clock().isoformat()
        if not plan.planned_sells:
            session.steps.append(ExecutionStep("SELL", "SKIPPED", now, now, "INITIAL_DEPLOYMENT has no sells."))
            appended.append(self._event(session, "SELL_PHASE_SKIPPED", "SELL phase skipped: no planned sells."))
        else:
            appended.append(self._transition(session, ExecutionSessionState.SELLING, "Shadow-simulating sell intents."))
            for intent in [item for item in session.order_intents if item.side == "SELL"]:
                intent.status = ExecutionOrderState.FILLED
                intent.filled_qty = intent.planned_qty
                appended.append(self._event(session, "SHADOW_SELL_FILLED", "Shadow sell simulated as filled.", intent.intent_id))
            session.steps.append(ExecutionStep("SELL", "SHADOW_FILLED", now, self.clock().isoformat()))

        appended.append(self._transition(session, ExecutionSessionState.BUYING, "Shadow-simulating buy intents."))
        for intent in [item for item in session.order_intents if item.side == "BUY"]:
            intent.status = ExecutionOrderState.SUBMITTING
            appended.append(self._event(session, "SHADOW_SUBMITTING", "Local shadow state only; no order submitted.", intent.intent_id))
            intent.status = ExecutionOrderState.SUBMITTED
            appended.append(self._event(session, "SHADOW_SUBMITTED", "Local shadow state only; no broker order exists.", intent.intent_id))
            intent.status = ExecutionOrderState.FILLED
            intent.filled_qty = intent.planned_qty
            appended.append(self._event(session, "SHADOW_FILLED", "Shadow buy simulated as filled.", intent.intent_id))
        session.steps.append(ExecutionStep("BUY", "SHADOW_FILLED", now, self.clock().isoformat()))
        appended.append(self._transition(session, ExecutionSessionState.RECONCILING, "Reconciling simulated holdings against target."))

        simulated = {item.code: item.quantity for item in snapshot.positions}
        for intent in session.order_intents:
            delta = intent.filled_qty if intent.side == "BUY" else -intent.filled_qty
            simulated[intent.code] = max(0, simulated.get(intent.code, 0) + delta)
            if simulated[intent.code] == 0:
                simulated.pop(intent.code)
        expected = {item.code: item.target_quantity for item in plan.target_positions if item.target_quantity > 0}
        differences = {
            code: simulated.get(code, 0) - expected.get(code, 0)
            for code in sorted(set(simulated).union(expected))
            if simulated.get(code, 0) != expected.get(code, 0)
        }
        session.final_reconciliation = ReconciliationResult(
            matched=not differences,
            expected_positions=expected,
            simulated_positions=simulated,
            differences=differences,
            estimated_cash_after=plan.estimated_cash_after,
        )
        if differences:
            session.failure_reason = "Shadow reconciliation did not match target holdings."
            appended.append(self._transition(session, ExecutionSessionState.FAILED, session.failure_reason))
        else:
            session.completed_at = self.clock().isoformat()
            appended.append(self._transition(session, ExecutionSessionState.SHADOW_COMPLETED, "Shadow reconciliation matched target holdings."))
        save_session(session, output_dir=self.session_dir, append_events=appended)
        return session


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QuantBuddy shadow-only execution orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)
    shadow = subparsers.add_parser("shadow-run", help="run a read-only shadow execution")
    shadow.add_argument("--plan-id", required=True)
    shadow.add_argument("--shadow-date", help="shadow-only test clock; never available to an execution mode")
    preflight = subparsers.add_parser("canary-preflight", help="read-only one-lot canary validation")
    preflight.add_argument("--plan-id", required=True)
    canary = subparsers.add_parser("canary-execute", help="interactive, controlled one-lot simulated canary")
    canary.add_argument("--plan-id", required=True)
    status = subparsers.add_parser("canary-status", help="query an existing canary order without resubmitting")
    status.add_argument("--session-id", required=True)
    reconcile = subparsers.add_parser("canary-reconcile", help="query/reconcile an existing canary session")
    reconcile.add_argument("--session-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command.startswith("canary-"):
        from .canary import CanaryConfig, CanaryOrchestrator

        runner = CanaryOrchestrator(config=CanaryConfig.from_env())
        if args.command == "canary-status":
            session = runner.status(args.session_id)
            print(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "canary-reconcile":
            session = runner.reconcile(args.session_id)
            print(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))
            return 0
        plan = load_execution_plan(args.plan_id)
        artifact = load_execution_artifact(find_latest_artifact(plan.strategy_id))
        if args.command == "canary-preflight":
            session = runner.preflight(plan, artifact.source_hash)
            print("CONTROLLED SIMULATED CANARY PREFLIGHT / NO ORDER SUBMITTED")
            print(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))
            return 0 if not session.blockers else 2
        session = runner.execute(plan, artifact.source_hash)
        print(f"Canary Session ID: {session.session_id}")
        print(f"State: {session.state.value}")
        print("FULL PLAN COMPLETED: false")
        return 0 if session.state.value not in {"FAILED", "UNKNOWN_REQUIRES_REVIEW"} else 2
    plan = load_execution_plan(args.plan_id)
    artifact = load_execution_artifact(find_latest_artifact(plan.strategy_id))
    orchestrator = ShadowOrchestrator()
    session = orchestrator.run(
        plan,
        expected_source_hash=artifact.source_hash,
        shadow_date=date.fromisoformat(args.shadow_date) if args.shadow_date else None,
    )
    print("SHADOW MODE")
    print("NO ORDER SUBMITTED")
    print("NO ORDER MODIFIED")
    print("NO ORDER CANCELLED")
    print(f"Session ID: {session.session_id}")
    print(f"State: {session.state.value}")
    print(f"Blockers: {len(session.blockers)}")
    print(f"Artifact directory: {DEFAULT_SESSION_DIR}")
    return 0 if session.state == ExecutionSessionState.SHADOW_COMPLETED else 2


if __name__ == "__main__":
    raise SystemExit(main())
