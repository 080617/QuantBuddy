"""Controlled one-lot simulated canary execution.

Importing this module is inert. The only write path requires two environment
switches, two fresh prechecks, and an interactive confirmation that is never a
CLI argument.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Callable
from zoneinfo import ZoneInfo

from backend.futu import AccountService, FutuClient, OrderService, QuoteService
from backend.futu.code_mapper import futu_to_qlib, qlib_to_futu
from backend.futu.models import (
    OrderBookTop,
    OrderRecord,
    OrderSide,
    PlaceOrderRequest,
    PlaceOrderResult,
    TradableQuantity,
)
from backend.futu.safety import mask_identifier

from .exceptions import PlanningError
from .models import ExecutionBlocker, ExecutionPlan, ExecutionWarning, PlannedOrder
from .orchestrator import collect_readonly_shadow_snapshot
from .orchestrator_models import ShadowSnapshot
from .orchestrator_precheck import PricePolicyConfig, plan_digest, snapshot_hash
from .persistence import load_execution_plan


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SESSION_DIR = PROJECT_ROOT / "artifacts" / "execution_sessions"
CONFIRMATION = "EXECUTE ONE-LOT CANARY"
TERMINAL_ORDER_STATES = {"FILLED", "CANCELLED", "REJECTED", "FAILED"}


class CanarySessionState(str, Enum):
    CREATED = "CREATED"
    PREFLIGHT_READY = "PREFLIGHT_READY"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    ABORTED_BY_USER = "ABORTED_BY_USER"
    FINAL_PRECHECK = "FINAL_PRECHECK"
    SUBMITTING = "SUBMITTING"
    TRACKING = "TRACKING"
    RECONCILING = "RECONCILING"
    CANARY_FILLED = "CANARY_FILLED"
    CANARY_PARTIALLY_FILLED = "CANARY_PARTIALLY_FILLED"
    CANARY_CANCELLED_NO_FILL = "CANARY_CANCELLED_NO_FILL"
    REJECTED = "REJECTED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    UNKNOWN_REQUIRES_REVIEW = "UNKNOWN_REQUIRES_REVIEW"


@dataclass(frozen=True, slots=True)
class CanaryConfig:
    market: str
    trading_environment: str
    enable_simulated_orders: bool
    enable_canary: bool
    max_order_amount: float = 50_000.0
    order_book_max_age_seconds: int = 15
    poll_interval_seconds: float = 3.0
    poll_timeout_seconds: float = 30.0
    price_policy: PricePolicyConfig = PricePolicyConfig()

    @classmethod
    def from_env(cls) -> "CanaryConfig":
        truth = {"1", "true", "yes", "on"}
        return cls(
            market=os.getenv("FUTU_MARKET", "CN").upper(),
            trading_environment=os.getenv("FUTU_TRD_ENV", "SIMULATE").upper(),
            enable_simulated_orders=os.getenv("FUTU_ENABLE_SIMULATED_ORDERS", "false").lower() in truth,
            enable_canary=os.getenv("EXECUTION_ENABLE_CANARY", "false").lower() in truth,
        )

    def require_write_enabled(self) -> None:
        if self.market != "CN":
            raise PlanningError("Canary requires FUTU_MARKET=CN.")
        if self.trading_environment != "SIMULATE":
            raise PlanningError("Canary requires FUTU_TRD_ENV=SIMULATE; REAL is forbidden.")
        if not self.enable_simulated_orders or not self.enable_canary:
            raise PlanningError("Both FUTU_ENABLE_SIMULATED_ORDERS=true and EXECUTION_ENABLE_CANARY=true are required.")


@dataclass(frozen=True, slots=True)
class CanaryCandidate:
    code: str
    name: str
    original_planned_qty: int
    canary_qty: int
    lot_size: int
    original_target_amount: float
    reference_price: float
    best_ask: float
    limit_price: float
    estimated_canary_amount: float
    maximum_allowed_price: float
    minimum_allowed_price: float
    maximum_cash_buy: float
    selection_reason: str
    remark: str


@dataclass(frozen=True, slots=True)
class CanaryReconciliation:
    submitted_qty: int
    dealt_qty: int
    remaining_qty: int
    dealt_avg_price: float | None
    final_order_status: str
    cash_before: float
    cash_after: float
    position_before: int
    position_after: int
    expected_position_change: int
    actual_position_change: int
    reconciliation_difference: int
    unresolved_uncertainty: str | None


@dataclass(slots=True)
class CanarySession:
    schema_version: str
    session_id: str
    plan_id: str
    plan_digest: str
    plan_source_hash: str
    strategy_id: str
    execution_mode: str
    canary_order_limit: int
    full_plan_completed: bool
    created_at: str
    updated_at: str
    state: CanarySessionState
    account_id_masked: str
    first_snapshot_hash: str
    final_snapshot_hash: str
    candidate: CanaryCandidate | None
    blockers: list[ExecutionBlocker] = field(default_factory=list)
    warnings: list[ExecutionWarning] = field(default_factory=list)
    place_attempted: bool = False
    place_call_count: int = 0
    cancel_call_count: int = 0
    order_id: str | None = None
    order_id_masked: str | None = None
    submitted_at: str | None = None
    request_hash: str | None = None
    initial_status: str | None = None
    final_status: str | None = None
    reconciliation: CanaryReconciliation | None = None
    requires_new_plan: bool = False
    events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        def normalize(value):
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value
        return normalize(asdict(self))


@dataclass(frozen=True, slots=True)
class CanaryPrecheck:
    snapshot: ShadowSnapshot
    order_book: OrderBookTop | None
    candidate: CanaryCandidate | None
    blockers: list[ExecutionBlocker]
    warnings: list[ExecutionWarning]


def _stable_id(prefix: str, payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{prefix}-" + hashlib.sha256(encoded.encode()).hexdigest()[:24]


def _mask_order_id(order_id: str) -> str:
    return "****" + order_id[-4:] if len(order_id) > 4 else "****"


def _finite_positive(value: float) -> bool:
    return value > 0 and value == value and value not in {float("inf"), float("-inf")}


def legalize_tick(price: float, tick_size: float) -> float:
    if not _finite_positive(price) or not _finite_positive(tick_size):
        raise PlanningError("Positive best ask and tick size are required.")
    price_decimal = Decimal(str(price))
    tick = Decimal(str(tick_size))
    return float((price_decimal / tick).to_integral_value(rounding=ROUND_CEILING) * tick)


def map_order_status(status: str) -> str:
    normalized = status.upper().rsplit(".", 1)[-1]
    mapping = {
        "SUBMITTING": "SUBMITTING", "SUBMITTED": "SUBMITTED",
        "WAITING_SUBMIT": "SUBMITTING", "SUBMITTED_ALL": "SUBMITTED",
        "FILLED_PART": "PARTIALLY_FILLED", "PARTIALLY_FILLED": "PARTIALLY_FILLED",
        "FILLED_ALL": "FILLED", "FILLED": "FILLED",
        "CANCEL_PENDING": "CANCEL_PENDING", "CANCELLING_PART": "CANCEL_PENDING",
        "CANCELLED_ALL": "CANCELLED", "CANCELLED_PART": "CANCELLED", "CANCELLED": "CANCELLED",
        "SUBMIT_FAILED": "REJECTED", "REJECTED": "REJECTED", "FAILED": "FAILED",
    }
    return mapping.get(normalized, "UNKNOWN")


def select_canary_order(plan: ExecutionPlan) -> PlannedOrder:
    if not plan.planned_buys:
        raise PlanningError("Plan has no BUY intent for a canary.")
    return min(plan.planned_buys, key=lambda item: (item.estimated_value, item.code, item.sequence))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return parsed.astimezone(timezone.utc)


def build_canary_precheck(
    plan: ExecutionPlan,
    snapshot: ShadowSnapshot,
    order_book: OrderBookTop | None,
    *,
    expected_source_hash: str,
    now: datetime,
    config: CanaryConfig,
    session_has_order_id: bool = False,
) -> CanaryPrecheck:
    blockers: list[ExecutionBlocker] = []
    warnings: list[ExecutionWarning] = []
    order = select_canary_order(plan)
    quote = snapshot.quotes.get(order.code)
    if plan.plan_id == "" or plan.source_hash != expected_source_hash:
        blockers.append(ExecutionBlocker("SOURCE_HASH_CHANGED", "Plan/source identity changed."))
    if plan.strategy_id != "strategy-hs300-lightgbm-top5":
        blockers.append(ExecutionBlocker("STRATEGY_NOT_ALLOWED", "Strategy is not allowed for canary."))
    if not plan.dry_run or not plan.executable or plan.blockers:
        blockers.append(ExecutionBlocker("PLAN_NOT_EXECUTABLE", "Plan is not a clean executable dry-run plan."))
    if plan.market != "CN" or snapshot.account.market != "CN" or config.market != "CN":
        blockers.append(ExecutionBlocker("NON_CN_MARKET", "Canary is CN-only."))
    if plan.trading_environment != "SIMULATE" or snapshot.account.trading_environment != "SIMULATE" or config.trading_environment != "SIMULATE":
        blockers.append(ExecutionBlocker("REAL_ENVIRONMENT_REJECTED", "Canary is SIMULATE-only."))
    if snapshot.account.status != "ACTIVE" or snapshot.account.account_id_masked != plan.account_id_masked:
        blockers.append(ExecutionBlocker("ACCOUNT_CHANGED", "Active simulated account no longer matches the plan."))
    if plan.planned_execution_date != now.date().isoformat():
        blockers.append(ExecutionBlocker("EXECUTION_DATE_MISMATCH", "Canary is only allowed on the planned execution date."))
    if {item.code: item.quantity for item in snapshot.positions} != {item.code: item.quantity for item in plan.current_positions}:
        blockers.append(ExecutionBlocker("ACCOUNT_POSITIONS_CHANGED", "Positions changed since plan creation."))
    if any(map_order_status(item.status) not in TERMINAL_ORDER_STATES and item.code == order.code for item in snapshot.recent_orders):
        blockers.append(ExecutionBlocker("UNFINISHED_ORDER_CONFLICT", "Related unfinished order exists.", order.code))
    if session_has_order_id:
        blockers.append(ExecutionBlocker("ORDER_ALREADY_RECORDED", "Session already has an order ID."))
    candidate = None
    if quote is None or not _finite_positive(quote.last_price):
        blockers.append(ExecutionBlocker("INVALID_QUOTE", "Target quote is missing or invalid.", order.code))
    elif quote.suspended:
        blockers.append(ExecutionBlocker("SUSPENDED_SECURITY", "Target security is suspended.", order.code))
    elif quote.lot_size <= 0:
        blockers.append(ExecutionBlocker("INVALID_LOT_SIZE", "Current lot size is invalid.", order.code))
    elif order_book is None or not _finite_positive(order_book.best_ask):
        blockers.append(ExecutionBlocker("BEST_ASK_MISSING", "Order book has no valid best ask; no last-price fallback is allowed.", order.code))
    else:
        if order_book.code != order.code:
            blockers.append(ExecutionBlocker("ORDER_BOOK_CODE_MISMATCH", "Order book is not for the selected plan symbol.", order.code))
        book_time = _parse_time(order_book.server_time)
        if book_time is None or abs((now.astimezone(timezone.utc) - book_time).total_seconds()) > config.order_book_max_age_seconds:
            blockers.append(ExecutionBlocker("ORDER_BOOK_STALE", "Order book server time is missing or stale.", order.code))
        quote_time = _parse_time(quote.update_time)
        if quote_time is None or abs((now.astimezone(timezone.utc) - quote_time).total_seconds()) > config.order_book_max_age_seconds:
            blockers.append(ExecutionBlocker("QUOTE_STALE", "Snapshot update_time is missing or stale.", order.code))
        tick = quote.price_spread or 0.0
        if not _finite_positive(tick):
            blockers.append(ExecutionBlocker("TICK_SIZE_MISSING", "Snapshot has no valid price_spread.", order.code))
        else:
            limit_price = legalize_tick(order_book.best_ask, tick)
            minimum, maximum = config.price_policy.bounds(order.limit_reference_price)
            canary_qty = quote.lot_size
            amount = limit_price * canary_qty
            maximum_quantity = snapshot.maximum_quantities.get(order.code)
            if limit_price < minimum or limit_price > maximum:
                blockers.append(ExecutionBlocker("PRICE_BAND_EXCEEDED", "Best ask exceeds the plan price band.", order.code))
            if maximum_quantity is None or maximum_quantity.maximum_cash_buy < canary_qty:
                blockers.append(ExecutionBlocker("MAX_BUY_INSUFFICIENT", "Maximum cash-buy quantity is below one lot.", order.code))
            if amount > snapshot.account.cash:
                blockers.append(ExecutionBlocker("INSUFFICIENT_CASH", "Cash is insufficient for the one-lot canary.", order.code))
            if amount > config.max_order_amount:
                blockers.append(ExecutionBlocker("CANARY_AMOUNT_LIMIT", "One-lot canary exceeds its amount cap.", order.code))
            session_suffix = _stable_id("s", {"plan": plan.plan_id, "account": snapshot.account.account_id_masked})[-8:]
            candidate = CanaryCandidate(
                code=order.code, name=quote.name, original_planned_qty=order.quantity,
                canary_qty=canary_qty, lot_size=quote.lot_size,
                original_target_amount=order.estimated_value, reference_price=order.limit_reference_price,
                best_ask=order_book.best_ask, limit_price=limit_price,
                estimated_canary_amount=amount, maximum_allowed_price=maximum,
                minimum_allowed_price=minimum,
                maximum_cash_buy=(maximum_quantity.maximum_cash_buy if maximum_quantity else 0),
                selection_reason="minimum estimated_value, then code, then sequence",
                remark=f"QB-CANARY-{session_suffix}",
            )
    return CanaryPrecheck(snapshot, order_book, candidate, blockers, warnings)


def collect_canary_snapshot(plan: ExecutionPlan, execution_date: date) -> tuple[ShadowSnapshot, OrderBookTop | None]:
    snapshot = collect_readonly_shadow_snapshot(plan, execution_date)
    order = select_canary_order(plan)
    with FutuClient() as client:
        futu_code = qlib_to_futu(order.code)
        book = QuoteService(client).get_order_book_top(futu_code)
        maximum = OrderService(client).get_max_tradable_quantity(futu_code, book.best_ask)
    normalized_maximum = TradableQuantity(
        code=order.code,
        price=maximum.price,
        maximum_cash_buy=maximum.maximum_cash_buy,
        maximum_position_sell=maximum.maximum_position_sell,
        lot_size=maximum.lot_size,
    )
    return (
        replace(
            snapshot,
            maximum_quantities={**snapshot.maximum_quantities, order.code: normalized_maximum},
        ),
        replace(book, code=futu_to_qlib(book.code)),
    )


def _session_path(session_id: str, directory: Path) -> Path:
    return directory / f"{session_id}.canary.json"


def _session_from_dict(payload: dict) -> CanarySession:
    return CanarySession(**{
        **payload,
        "state": CanarySessionState(payload["state"]),
        "candidate": CanaryCandidate(**payload["candidate"]) if payload.get("candidate") else None,
        "blockers": [ExecutionBlocker(**item) for item in payload.get("blockers", [])],
        "warnings": [ExecutionWarning(**item) for item in payload.get("warnings", [])],
        "reconciliation": CanaryReconciliation(**payload["reconciliation"]) if payload.get("reconciliation") else None,
    })


def load_canary_session(session_id: str, directory: Path = DEFAULT_SESSION_DIR) -> CanarySession:
    path = _session_path(session_id, directory)
    if not path.exists():
        raise PlanningError(f"Canary session not found: {session_id}")
    return _session_from_dict(json.loads(path.read_text(encoding="utf-8")))


def find_canary_session(plan_id: str, directory: Path = DEFAULT_SESSION_DIR) -> CanarySession | None:
    if not directory.exists():
        return None
    for path in sorted(directory.glob("canary-*.canary.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("plan_id") == plan_id:
            return _session_from_dict(payload)
    return None


def save_canary_session(session: CanarySession, directory: Path = DEFAULT_SESSION_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = _session_path(session.session_id, directory)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(session.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


class RealCanaryGateway:
    def place_once(self, candidate: CanaryCandidate) -> PlaceOrderResult:
        with FutuClient() as client:
            return OrderService(client).place_simulated_limit_order(PlaceOrderRequest(
                code=qlib_to_futu(candidate.code), side=OrderSide.BUY,
                quantity=candidate.canary_qty, price=candidate.limit_price, remark=candidate.remark,
            ))

    def get_order(self, order_id: str) -> OrderRecord | None:
        with FutuClient() as client:
            item = OrderService(client).get_order(order_id)
            return replace(item, code=futu_to_qlib(item.code)) if item else None

    def cancel_once(self, order_id: str) -> bool:
        with FutuClient() as client:
            return OrderService(client).cancel_simulated_order(order_id)


class CanaryOrchestrator:
    def __init__(self, *, config: CanaryConfig, snapshot_provider=collect_canary_snapshot,
                 gateway=None, session_dir: Path = DEFAULT_SESSION_DIR,
                 plan_loader=load_execution_plan,
                 clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc).replace(microsecond=0),
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self.config = config; self.snapshot_provider = snapshot_provider
        self.gateway = gateway or RealCanaryGateway(); self.session_dir = session_dir
        self.plan_loader = plan_loader; self.clock = clock; self.sleeper = sleeper

    def _event(self, session: CanarySession, kind: str, message: str) -> None:
        session.events.append({"sequence": len(session.events) + 1, "at": self.clock().isoformat(), "type": kind, "message": message})
        session.updated_at = self.clock().isoformat()

    def preflight(self, plan: ExecutionPlan, expected_source_hash: str) -> CanarySession:
        existing = find_canary_session(plan.plan_id, self.session_dir)
        if existing and (existing.order_id or existing.place_attempted or existing.state not in {CanarySessionState.ABORTED_BY_USER, CanarySessionState.PAUSED, CanarySessionState.FAILED}):
            raise PlanningError("Existing canary session cannot create another order attempt.")
        snap, book = self.snapshot_provider(plan, self.clock().date())
        result = build_canary_precheck(plan, snap, book, expected_source_hash=expected_source_hash,
                                       now=self.clock(), config=self.config,
                                       session_has_order_id=bool(existing and existing.order_id))
        now = self.clock().isoformat()
        session = existing or CanarySession(
            schema_version="quantbuddy.canary-session.v1",
            session_id=_stable_id("canary", {"plan": plan.plan_id, "source": plan.source_hash,
                                              "account": snap.account.account_id_masked}),
            plan_id=plan.plan_id, plan_digest=plan_digest(plan), plan_source_hash=plan.source_hash,
            strategy_id=plan.strategy_id, execution_mode="CANARY", canary_order_limit=1,
            full_plan_completed=False, created_at=now, updated_at=now,
            state=CanarySessionState.CREATED, account_id_masked=snap.account.account_id_masked,
            first_snapshot_hash=snapshot_hash(snap), final_snapshot_hash="", candidate=result.candidate,
        )
        session.candidate=result.candidate; session.blockers=result.blockers; session.warnings=result.warnings
        session.state=CanarySessionState.PREFLIGHT_READY if not result.blockers else CanarySessionState.PAUSED
        self._event(session, "PREFLIGHT", "Read-only canary preflight completed.")
        save_canary_session(session, self.session_dir)
        return session

    def execute(self, plan: ExecutionPlan, expected_source_hash: str, *, input_fn=input, output_fn=print) -> CanarySession:
        self.config.require_write_enabled()
        session = self.preflight(plan, expected_source_hash)
        if session.blockers or not session.candidate:
            return session
        candidate=session.candidate; session.state=CanarySessionState.AWAITING_CONFIRMATION
        save_canary_session(session, self.session_dir)
        output_fn("CONTROLLED SIMULATED CANARY\nCN / SIMULATE\nONE ORDER MAXIMUM\nONE LOT MAXIMUM")
        output_fn(json.dumps(asdict(candidate), ensure_ascii=False, indent=2))
        confirmation=input_fn(f"Type exactly '{CONFIRMATION}': ")
        if confirmation != CONFIRMATION:
            session.state=CanarySessionState.ABORTED_BY_USER
            self._event(session, "ABORTED", "Interactive confirmation did not match; no order submitted.")
            save_canary_session(session, self.session_dir); return session

        session.state=CanarySessionState.FINAL_PRECHECK
        try:
            fresh_plan = self.plan_loader(plan.plan_id)
        except Exception as exc:
            session.blockers = [ExecutionBlocker("PLAN_RELOAD_FAILED", f"Plan could not be reloaded: {type(exc).__name__}")]
            session.state = CanarySessionState.PAUSED
            self._event(session, "FINAL_PRECHECK_BLOCKED", "Plan no longer exists or cannot be reloaded.")
            save_canary_session(session, self.session_dir)
            return session
        if plan_digest(fresh_plan) != session.plan_digest or fresh_plan.source_hash != session.plan_source_hash:
            session.blockers = [ExecutionBlocker("PLAN_CHANGED", "Persisted plan changed after confirmation.")]
            session.state = CanarySessionState.PAUSED
            self._event(session, "FINAL_PRECHECK_BLOCKED", "Persisted plan identity changed after confirmation.")
            save_canary_session(session, self.session_dir)
            return session
        snap, book = self.snapshot_provider(fresh_plan, self.clock().date())
        final = build_canary_precheck(fresh_plan, snap, book, expected_source_hash=expected_source_hash,
                                      now=self.clock(), config=self.config,
                                      session_has_order_id=bool(session.order_id))
        session.final_snapshot_hash=snapshot_hash(snap); session.blockers=final.blockers
        if final.blockers or not final.candidate:
            session.state=CanarySessionState.PAUSED; self._event(session,"FINAL_PRECHECK_BLOCKED","Final fresh precheck failed.")
            save_canary_session(session,self.session_dir); return session
        session.candidate=final.candidate; candidate=final.candidate
        request={"plan_id":plan.plan_id,"code":candidate.code,"qty":candidate.canary_qty,
                 "price":candidate.limit_price,"remark":candidate.remark,"source_hash":plan.source_hash}
        session.request_hash=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        session.place_attempted=True; session.place_call_count=1; session.state=CanarySessionState.SUBMITTING
        self._event(session,"SUBMISSION_GUARD","Persistent one-attempt guard saved before broker call.")
        save_canary_session(session,self.session_dir)
        try:
            placed=self.gateway.place_once(candidate)
        except Exception as exc:
            session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
            self._event(session,"PLACE_RESULT_UNKNOWN",f"Place call did not return a safely recordable result: {type(exc).__name__}")
            save_canary_session(session,self.session_dir); return session
        session.order_id=placed.order_id; session.order_id_masked=_mask_order_id(placed.order_id)
        session.submitted_at=self.clock().isoformat(); session.initial_status=map_order_status(placed.status)
        session.state=CanarySessionState.TRACKING; self._event(session,"ORDER_ID_PERSISTED","Order ID persisted before status query.")
        save_canary_session(session,self.session_dir)
        return self._track_and_reconcile(fresh_plan, session, snap)

    def _track_and_reconcile(self, plan: ExecutionPlan, session: CanarySession, before: ShadowSnapshot) -> CanarySession:
        assert session.order_id and session.candidate
        deadline=self.clock().timestamp()+self.config.poll_timeout_seconds; latest=None
        while self.clock().timestamp() <= deadline:
            try: latest=self.gateway.get_order(session.order_id)
            except Exception:
                session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
                self._event(session,"QUERY_UNKNOWN","Order query failed; no retry submission or blind cancel.")
                save_canary_session(session,self.session_dir); return session
            if latest is None:
                session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
                self._event(session,"ORDER_NOT_FOUND","Known order ID was not returned; manual review required.")
                save_canary_session(session,self.session_dir); return session
            mapped=map_order_status(latest.status); session.final_status=mapped
            if mapped in TERMINAL_ORDER_STATES or mapped=="PARTIALLY_FILLED": break
            self.sleeper(self.config.poll_interval_seconds)
        if latest is None:
            session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
            save_canary_session(session,self.session_dir); return session
        dealt=int(latest.dealt_quantity); remaining=session.candidate.canary_qty-dealt
        mapped=map_order_status(latest.status)
        if mapped=="UNKNOWN":
            session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
            self._event(session,"UNKNOWN_STATUS","Unknown status forbids resubmission and blind cancellation.")
            save_canary_session(session,self.session_dir); return session
        if mapped in {"REJECTED","FAILED"}:
            session.state=CanarySessionState.REJECTED
        elif dealt < session.candidate.canary_qty and mapped not in {"CANCELLED","REJECTED","FAILED"}:
            if session.cancel_call_count:
                session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
                save_canary_session(session,self.session_dir); return session
            session.cancel_call_count=1; save_canary_session(session,self.session_dir)
            try:
                self.gateway.cancel_once(session.order_id)
            except Exception as exc:
                session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
                self._event(session,"CANCEL_RESULT_UNKNOWN",f"Cancel result is unknown: {type(exc).__name__}")
                save_canary_session(session,self.session_dir); return session
            self._event(session,"CANCEL_REQUESTED","Exactly one cancel requested for confirmed unfilled remainder.")
            final=self.gateway.get_order(session.order_id)
            if final is None:
                session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
                save_canary_session(session,self.session_dir); return session
            latest=final; dealt=int(final.dealt_quantity); remaining=session.candidate.canary_qty-dealt
            mapped=map_order_status(final.status); session.final_status=mapped
        session.state=CanarySessionState.RECONCILING
        after,_=self.snapshot_provider(plan,self.clock().date())
        before_qty=next((item.quantity for item in before.positions if item.code==session.candidate.code),0)
        after_qty=next((item.quantity for item in after.positions if item.code==session.candidate.code),0)
        actual=after_qty-before_qty; difference=actual-dealt
        uncertainty=None if difference==0 and mapped!="UNKNOWN" else "Position/order reconciliation requires review."
        session.reconciliation=CanaryReconciliation(
            submitted_qty=session.candidate.canary_qty,dealt_qty=dealt,remaining_qty=remaining,
            dealt_avg_price=latest.dealt_average_price,final_order_status=mapped,
            cash_before=before.account.cash,cash_after=after.account.cash,
            position_before=before_qty,position_after=after_qty,expected_position_change=dealt,
            actual_position_change=actual,reconciliation_difference=difference,unresolved_uncertainty=uncertainty,
        )
        if uncertainty:
            session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
        elif dealt==session.candidate.canary_qty:
            session.state=CanarySessionState.CANARY_FILLED
        elif dealt>0:
            session.state=CanarySessionState.CANARY_PARTIALLY_FILLED
        else:
            session.state=CanarySessionState.CANARY_CANCELLED_NO_FILL if mapped=="CANCELLED" else CanarySessionState.REJECTED
        session.full_plan_completed=False; session.requires_new_plan=dealt>0
        self._event(session,"RECONCILED","Canary finalized; remaining Top-5 orders were not submitted.")
        save_canary_session(session,self.session_dir); return session

    def status(self, session_id: str) -> CanarySession:
        session=load_canary_session(session_id,self.session_dir)
        if session.order_id:
            item=self.gateway.get_order(session.order_id)
            session.final_status=map_order_status(item.status) if item else "UNKNOWN"
            self._event(session,"STATUS_QUERY","Recovery queried existing order ID only.")
            save_canary_session(session,self.session_dir)
        return session

    def reconcile(self, session_id: str) -> CanarySession:
        session=load_canary_session(session_id,self.session_dir)
        if not session.order_id:
            raise PlanningError("Cannot reconcile a canary session without an order ID.")
        plan=self.plan_loader(session.plan_id)
        if plan_digest(plan) != session.plan_digest or plan.source_hash != session.plan_source_hash:
            raise PlanningError("Cannot reconcile because the persisted plan changed.")
        item=self.gateway.get_order(session.order_id)
        snapshot,_=self.snapshot_provider(plan,self.clock().date())
        if item is None or session.candidate is None:
            session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
            session.final_status="UNKNOWN"
            self._event(session,"RECOVERY_RECONCILE_UNKNOWN","Known order could not be reconciled; no write was attempted.")
            save_canary_session(session,self.session_dir); return session
        mapped=map_order_status(item.status); dealt=int(item.dealt_quantity)
        before_qty=next((position.quantity for position in plan.current_positions if position.code==session.candidate.code),0)
        after_qty=next((position.quantity for position in snapshot.positions if position.code==session.candidate.code),0)
        actual=after_qty-before_qty; difference=actual-dealt
        unresolved=None
        if mapped=="UNKNOWN" or mapped not in TERMINAL_ORDER_STATES:
            unresolved="Order remains non-terminal or unknown; manual review is required."
        elif difference != 0:
            unresolved="Position/order reconciliation requires review."
        session.final_status=mapped
        session.final_snapshot_hash=snapshot_hash(snapshot)
        session.reconciliation=CanaryReconciliation(
            submitted_qty=session.candidate.canary_qty,dealt_qty=dealt,
            remaining_qty=max(session.candidate.canary_qty-dealt,0),
            dealt_avg_price=item.dealt_average_price,final_order_status=mapped,
            cash_before=plan.cash_before,cash_after=snapshot.account.cash,
            position_before=before_qty,position_after=after_qty,
            expected_position_change=dealt,actual_position_change=actual,
            reconciliation_difference=difference,unresolved_uncertainty=unresolved,
        )
        if unresolved:
            session.state=CanarySessionState.UNKNOWN_REQUIRES_REVIEW
        elif dealt==session.candidate.canary_qty:
            session.state=CanarySessionState.CANARY_FILLED
        elif dealt>0:
            session.state=CanarySessionState.CANARY_PARTIALLY_FILLED
        else:
            session.state=CanarySessionState.CANARY_CANCELLED_NO_FILL if mapped=="CANCELLED" else CanarySessionState.REJECTED
        session.full_plan_completed=False; session.requires_new_plan=dealt>0
        self._event(session,"RECOVERY_RECONCILED","Query-only recovery reconciled the known order; no write was attempted.")
        save_canary_session(session,self.session_dir); return session
