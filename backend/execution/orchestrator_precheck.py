"""Pure precheck rules for shadow execution; no Futu write method exists here."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
import math

from .models import ExecutionBlocker, ExecutionPlan, ExecutionWarning, PlannedOrder
from .orchestrator_models import ExecutionPricePolicy, ShadowSnapshot
from .order_planner import TERMINAL_ORDER_STATUSES


@dataclass(frozen=True, slots=True)
class PricePolicyConfig:
    policy: ExecutionPricePolicy = ExecutionPricePolicy.REFERENCE_LIMIT
    maximum_relative_deviation: float = 0.10
    warning_relative_deviation: float = 0.05

    def bounds(self, reference_price: float) -> tuple[float, float]:
        return (
            reference_price * (1.0 - self.maximum_relative_deviation),
            reference_price * (1.0 + self.maximum_relative_deviation),
        )


@dataclass(frozen=True, slots=True)
class PrecheckResult:
    blockers: list[ExecutionBlocker]
    warnings: list[ExecutionWarning]
    account_snapshot_hash: str


@dataclass(frozen=True, slots=True)
class OrderUpdateDecision:
    next_session_state: str
    remaining_quantity: int
    continue_other_orders: bool
    allow_resubmit: bool
    reason: str


def plan_digest(plan: ExecutionPlan) -> str:
    payload = json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshot_hash(snapshot: ShadowSnapshot) -> str:
    payload = {
        "account": asdict(snapshot.account),
        "positions": [asdict(item) for item in sorted(snapshot.positions, key=lambda item: item.code)],
        "orders": [asdict(item) for item in sorted(snapshot.recent_orders, key=lambda item: item.order_id)],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _unfinished(status: str) -> bool:
    return status.upper().rsplit(".", 1)[-1] not in TERMINAL_ORDER_STATUSES


def run_precheck(
    plan: ExecutionPlan,
    snapshot: ShadowSnapshot,
    *,
    expected_source_hash: str,
    price_config: PricePolicyConfig,
    effective_date: date,
    shadow_override: bool = False,
) -> PrecheckResult:
    blockers: list[ExecutionBlocker] = []
    warnings: list[ExecutionWarning] = []
    if not plan.dry_run:
        blockers.append(ExecutionBlocker("PLAN_NOT_DRY_RUN", "Orchestrator accepts dry-run plans only."))
    if not plan.executable or plan.blockers:
        blockers.append(ExecutionBlocker("PLAN_NOT_EXECUTABLE", "Plan is not executable or has blockers."))
    if plan.market != "CN" or snapshot.account.market != "CN":
        blockers.append(ExecutionBlocker("NON_CN_MARKET", "Only the CN market is supported."))
    if plan.trading_environment != "SIMULATE" or snapshot.account.trading_environment != "SIMULATE":
        blockers.append(ExecutionBlocker("REAL_ENVIRONMENT_REJECTED", "Only SIMULATE is allowed."))
    if snapshot.account.status != "ACTIVE":
        blockers.append(ExecutionBlocker("ACCOUNT_NOT_ACTIVE", "Account is not ACTIVE."))
    if snapshot.account.account_id_masked != plan.account_id_masked:
        blockers.append(ExecutionBlocker("ACCOUNT_CHANGED", "Selected masked account differs from the plan."))
    if plan.source_hash != expected_source_hash:
        blockers.append(ExecutionBlocker("SOURCE_HASH_CHANGED", "Plan source hash no longer matches."))
    if not plan.planned_execution_date:
        blockers.append(ExecutionBlocker("EXECUTION_DATE_MISSING", "Plan has no execution date."))
    elif effective_date.isoformat() != plan.planned_execution_date:
        planned_date = date.fromisoformat(plan.planned_execution_date)
        code = "PLAN_EXPIRED" if effective_date > planned_date else "EXECUTION_DATE_MISMATCH"
        blockers.append(ExecutionBlocker(code, "Current execution date does not match the plan."))
    if shadow_override:
        warnings.append(ExecutionWarning("SHADOW_DATE_OVERRIDE", "Shadow-only clock override was used."))

    planned_positions = {item.code: item.quantity for item in plan.current_positions}
    actual_positions = {item.code: item.quantity for item in snapshot.positions}
    if planned_positions != actual_positions:
        blockers.append(ExecutionBlocker("ACCOUNT_POSITIONS_CHANGED", "Current positions differ from plan creation."))
    relevant = {item.code for item in plan.planned_sells + plan.planned_buys}
    if any(_unfinished(item.status) and item.code in relevant for item in snapshot.recent_orders):
        blockers.append(ExecutionBlocker("UNFINISHED_ORDER_CONFLICT", "A related unfinished order exists."))

    all_orders = plan.planned_sells + plan.planned_buys
    required_cash = sum(item.estimated_value + item.estimated_fee for item in plan.planned_buys)
    if required_cash > snapshot.account.cash + sum(item.estimated_value for item in plan.planned_sells):
        blockers.append(ExecutionBlocker("INSUFFICIENT_CASH", "Current cash cannot fund planned buys."))
    if sum(item.estimated_value for item in all_orders) > plan.applied_max_daily_planned_amount + 1e-6:
        blockers.append(ExecutionBlocker("DAILY_PLAN_LIMIT_EXCEEDED", "Plan exceeds its persisted daily limit."))

    target_codes = {item.code for item in plan.target_positions if item.target_quantity > 0}
    projected_codes = {item.code for item in plan.planned_buys}.union(
        item.code for item in plan.current_positions if item.code not in {sell.code for sell in plan.planned_sells}
    )
    if target_codes != projected_codes:
        blockers.append(ExecutionBlocker("TARGET_MISMATCH", "Target securities do not match the plan sequence."))

    for order in all_orders:
        quote = snapshot.quotes.get(order.code)
        if quote is None or not math.isfinite(quote.last_price) or quote.last_price <= 0:
            blockers.append(ExecutionBlocker("INVALID_QUOTE", "Current quote is missing or invalid.", order.code))
            continue
        if quote.suspended:
            blockers.append(ExecutionBlocker("SUSPENDED_SECURITY", "Security is suspended.", order.code))
        if quote.lot_size <= 0 or order.lot_size != quote.lot_size or order.quantity % quote.lot_size:
            blockers.append(ExecutionBlocker("INVALID_LOT_QUANTITY", "Quantity no longer matches lot size.", order.code))
        minimum, maximum = price_config.bounds(order.limit_reference_price)
        if quote.last_price < minimum or quote.last_price > maximum:
            blockers.append(ExecutionBlocker(
                "PRICE_DEVIATION_EXCEEDED",
                f"Current quote deviation {(quote.last_price / order.limit_reference_price - 1.0):.2%} "
                f"is outside ±{price_config.maximum_relative_deviation:.2%}.",
                order.code,
            ))
        elif abs(quote.last_price / order.limit_reference_price - 1.0) > price_config.warning_relative_deviation:
            warnings.append(ExecutionWarning(
                "LARGE_PRICE_DEVIATION",
                f"Current quote deviation is {(quote.last_price / order.limit_reference_price - 1.0):.2%}; "
                "actual execution price policy remains unapproved.",
                order.code,
            ))
        if order.estimated_value > plan.applied_max_single_order_amount + 1e-6:
            blockers.append(ExecutionBlocker("SINGLE_ORDER_LIMIT_EXCEEDED", "Order exceeds its persisted limit.", order.code))
        if order.side == "BUY":
            maximum_quantity = snapshot.maximum_quantities.get(order.code)
            if maximum_quantity is None or order.quantity > maximum_quantity.maximum_cash_buy:
                blockers.append(ExecutionBlocker("MAX_BUY_INSUFFICIENT", "Maximum cash-buy quantity is insufficient.", order.code))
    unique = {(item.code, item.symbol): item for item in blockers}
    return PrecheckResult(list(unique.values()), warnings, snapshot_hash(snapshot))


def next_state_for_order_update(side: str, status: str) -> str:
    """Conservative future-write decision semantics, implemented without writes."""
    normalized = status.upper()
    if normalized in {"PARTIALLY_FILLED", "SUBMITTING", "SUBMITTED", "CANCEL_PENDING"}:
        return "WAITING_FOR_SELLS" if side.upper() == "SELL" else "WAITING_FOR_BUYS"
    if normalized in {"UNKNOWN"}:
        return "PAUSED"
    if normalized in {"REJECTED", "FAILED", "CANCELLED"}:
        return "FAILED"
    if normalized == "FILLED":
        return "READY"
    return "PAUSED"


def evaluate_order_update(side: str, status: str, planned_quantity: int, filled_quantity: int) -> OrderUpdateDecision:
    if planned_quantity <= 0 or not 0 <= filled_quantity <= planned_quantity:
        raise ValueError("Order quantities are inconsistent.")
    normalized = status.upper()
    remaining = planned_quantity - filled_quantity
    state = next_state_for_order_update(side, normalized)
    if normalized == "FILLED" and remaining != 0:
        return OrderUpdateDecision("PAUSED", remaining, False, False, "FILLED quantity mismatch requires reconciliation.")
    if normalized == "PARTIALLY_FILLED":
        return OrderUpdateDecision(state, remaining, False, False, "Wait and query; never submit the remainder blindly.")
    if normalized in {"SUBMITTING", "SUBMITTED", "CANCEL_PENDING"}:
        return OrderUpdateDecision(state, remaining, False, False, "Wait for a terminal broker state before progressing.")
    if normalized == "FILLED":
        return OrderUpdateDecision(state, 0, True, False, "Filled intent may advance the state machine.")
    if normalized in {"REJECTED", "FAILED", "CANCELLED"}:
        return OrderUpdateDecision(state, remaining, False, False, "Stop the batch and reconcile before any other buy.")
    return OrderUpdateDecision("PAUSED", remaining, False, False, "Unknown state must be queried and cannot be resubmitted.")
