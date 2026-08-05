"""Deterministic, long-only dry-run order planning under Futu constraints."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math

from backend.futu.models import OrderRecord, QuoteSnapshot, TradableQuantity

from .models import (
    AccountState,
    CurrentPosition,
    ExecutionArtifact,
    ExecutionBlocker,
    ExecutionPlan,
    ExecutionWarning,
    PlannedOrder,
    PlanningConfig,
    TargetPosition,
)
from .reconciliation import reconcile_positions
from .safety import collect_execution_safety_blockers, deduplicate_blockers
from .signal_validator import ArtifactValidation
from .target_portfolio import derive_topk_dropout_transition


TERMINAL_ORDER_STATUSES = {
    "FILLED_ALL",
    "CANCELLED_ALL",
    "CANCELLED_PART",
    "SUBMIT_FAILED",
    "FAILED",
    "DISABLED",
    "DELETED",
}


def _fee(value: float, rate: float, minimum: float) -> float:
    return max(value * rate, minimum) if value > 0 else 0.0


def _stable_plan_id(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "plan-" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def _unfinished(order: OrderRecord) -> bool:
    return str(order.status).upper().rsplit(".", 1)[-1] not in TERMINAL_ORDER_STATUSES


def build_execution_plan(
    *,
    artifact: ExecutionArtifact,
    artifact_validation: ArtifactValidation,
    account: AccountState,
    current_positions: list[CurrentPosition],
    recent_orders: list[OrderRecord],
    quotes: dict[str, QuoteSnapshot],
    maximum_quantities: dict[str, TradableQuantity],
    managed_codes: set[str],
    config: PlanningConfig,
) -> ExecutionPlan:
    metadata = artifact.metadata
    actual_managed = {position.code for position in current_positions if position.managed}
    if actual_managed != managed_codes:
        managed_codes = actual_managed
    transition = derive_topk_dropout_transition(artifact.signals, managed_codes, metadata)
    reconciliation = reconcile_positions(current_positions, transition, artifact.signals)
    current_by_code = {position.code: position for position in current_positions}
    blockers = list(artifact_validation.blockers)
    warnings = list(artifact_validation.warnings)

    unmanaged = [position.code for position in current_positions if not position.managed]
    if unmanaged:
        blockers.append(
            ExecutionBlocker(
                "UNMANAGED_POSITIONS_PRESENT",
                "Account contains positions not explicitly assigned to this strategy; capital isolation is unknown.",
            )
        )
    if len(managed_codes) > metadata.topk:
        blockers.append(ExecutionBlocker("TOO_MANY_MANAGED_POSITIONS", "Managed holdings exceed Top-5."))

    relevant_codes = set(transition.sell).union(transition.buy).union(transition.keep)
    for order in recent_orders:
        if _unfinished(order) and order.code in relevant_codes:
            blockers.append(
                ExecutionBlocker(
                    "UNFINISHED_ORDER_CONFLICT",
                    "An unfinished order already exists for a relevant security.",
                    order.code,
                )
            )

    sell_orders: list[PlannedOrder] = []
    cash_after_sells = account.cash
    sequence = 1
    for code in transition.sell:
        position = current_by_code[code]
        quote = quotes.get(code)
        if quote is None or quote.last_price <= 0:
            blockers.append(ExecutionBlocker("MISSING_PRICE", "No valid sell reference price.", code))
            continue
        if quote.suspended:
            blockers.append(ExecutionBlocker("SUSPENDED_SECURITY", "Security is suspended.", code))
            continue
        if position.sellable_quantity < position.quantity:
            blockers.append(
                ExecutionBlocker(
                    "INSUFFICIENT_SELLABLE_QUANTITY",
                    "Full strategy exit exceeds can_sell_qty; no short sale is allowed.",
                    code,
                )
            )
        quantity = min(position.quantity, position.sellable_quantity)
        if quantity <= 0:
            continue
        lot_size = max(1, quote.lot_size)
        quantity = (quantity // lot_size) * lot_size
        if quantity <= 0:
            blockers.append(ExecutionBlocker("SELL_BELOW_ONE_LOT", "Sellable quantity is below one lot.", code))
            continue
        value = quantity * quote.last_price
        fee = _fee(value, metadata.close_cost, metadata.min_cost)
        sell_orders.append(
            PlannedOrder(
                sequence=sequence,
                phase="SELL_FIRST",
                side="SELL",
                code=code,
                quantity=quantity,
                limit_reference_price=quote.last_price,
                lot_size=lot_size,
                estimated_value=value,
                estimated_fee=fee,
                reason="TopkDropoutStrategy bottom-ranked managed holding selected for full exit.",
            )
        )
        cash_after_sells += value - fee
        sequence += 1

    cash_reserved = cash_after_sells * (1.0 - metadata.risk_degree)
    buy_pool = cash_after_sells * metadata.risk_degree
    budget_per_buy = buy_pool / len(transition.buy) if transition.buy else 0.0
    buy_orders: list[PlannedOrder] = []
    for code in transition.buy:
        quote = quotes.get(code)
        if quote is None or quote.last_price <= 0:
            blockers.append(ExecutionBlocker("MISSING_PRICE", "No valid buy reference price.", code))
            continue
        if quote.suspended:
            blockers.append(
                ExecutionBlocker(
                    "SUSPENDED_SECURITY",
                    "Selected security is suspended; no automatic rank-6 substitution is made.",
                    code,
                )
            )
            continue
        lot_size = quote.lot_size
        if lot_size <= 0:
            blockers.append(ExecutionBlocker("INVALID_LOT_SIZE", "Quote returned an invalid lot size.", code))
            continue
        quantity = math.floor(budget_per_buy / quote.last_price / lot_size) * lot_size
        if quantity < lot_size:
            blockers.append(
                ExecutionBlocker("INSUFFICIENT_CASH_FOR_ONE_LOT", "Allocated cash cannot buy one board lot.", code)
            )
            continue
        while quantity >= lot_size:
            candidate_value = quantity * quote.last_price
            if candidate_value + _fee(candidate_value, metadata.open_cost, metadata.min_cost) <= budget_per_buy:
                break
            quantity -= lot_size
        if quantity < lot_size:
            blockers.append(
                ExecutionBlocker(
                    "INSUFFICIENT_CASH_FOR_ONE_LOT",
                    "Allocated cash cannot cover one board lot plus configured fees.",
                    code,
                )
            )
            continue
        tradable = maximum_quantities.get(code)
        if tradable is None:
            blockers.append(ExecutionBlocker("MAX_BUY_MISSING", "Maximum tradable quantity was not queried.", code))
            continue
        maximum_lot_quantity = math.floor(tradable.maximum_cash_buy / lot_size) * lot_size
        if quantity > maximum_lot_quantity:
            blockers.append(
                ExecutionBlocker(
                    "MAX_BUY_INSUFFICIENT",
                    f"Planned quantity {quantity} exceeds maximum cash buy {tradable.maximum_cash_buy:g}.",
                    code,
                )
            )
            quantity = maximum_lot_quantity
        if quantity < lot_size:
            blockers.append(ExecutionBlocker("MAX_BUY_BELOW_ONE_LOT", "Maximum buy is below one lot.", code))
            continue
        value = quantity * quote.last_price
        fee = _fee(value, metadata.open_cost, metadata.min_cost)
        buy_orders.append(
            PlannedOrder(
                sequence=sequence,
                phase="BUY_AFTER_SELL_CONFIRMATION",
                side="BUY",
                code=code,
                quantity=quantity,
                limit_reference_price=quote.last_price,
                lot_size=lot_size,
                estimated_value=value,
                estimated_fee=fee,
                reason="TopkDropoutStrategy new member; execute only after sell completion is confirmed.",
            )
        )
        sequence += 1

    buy_cash = sum(order.estimated_value + order.estimated_fee for order in buy_orders)
    spendable_cash = max(0.0, cash_after_sells - cash_reserved)
    if buy_cash > spendable_cash + 1e-6:
        blockers.append(ExecutionBlocker("INSUFFICIENT_CASH", "Estimated buys and fees exceed risk-adjusted cash."))
    estimated_cash_after = cash_after_sells - buy_cash
    turnover_value = sum(order.estimated_value for order in sell_orders + buy_orders)
    estimated_turnover = turnover_value / account.total_assets if account.total_assets > 0 else float("inf")
    if not math.isfinite(estimated_turnover) or estimated_turnover > config.max_turnover_ratio:
        blockers.append(
            ExecutionBlocker(
                "TURNOVER_LIMIT_EXCEEDED",
                f"Estimated turnover {estimated_turnover:.4f} exceeds {config.max_turnover_ratio:.4f}.",
            )
        )
    if len(transition.desired_membership) > config.max_positions:
        blockers.append(ExecutionBlocker("POSITION_COUNT_LIMIT_EXCEEDED", "Target membership exceeds the position limit."))

    blockers.extend(
        collect_execution_safety_blockers(
            account=account,
            strategy_id=metadata.strategy_id,
            orders=sell_orders + buy_orders,
            config=config,
            dry_run=True,
        )
    )
    blockers = deduplicate_blockers(blockers)

    projected: dict[str, tuple[int, float, str]] = {}
    for position in current_positions:
        if position.managed and position.code not in transition.sell:
            price = position.reference_price or (
                position.market_value / position.quantity if position.market_value and position.quantity else 0.0
            )
            projected[position.code] = (position.quantity, price, "KEEP")
    for order in buy_orders:
        projected[order.code] = (order.quantity, order.limit_reference_price, "BUY")
    for code in transition.sell:
        if code not in projected:
            projected[code] = (0, quotes.get(code).last_price if quotes.get(code) else 0.0, "SELL")
    target_positions = [
        TargetPosition(
            code=code,
            target_quantity=quantity,
            reference_price=price,
            estimated_market_value=quantity * price,
            estimated_weight=(quantity * price / account.total_assets if account.total_assets > 0 else 0.0),
            transition=transition_name,
        )
        for code, (quantity, price, transition_name) in sorted(projected.items())
    ]

    id_payload = {
        "strategy_id": metadata.strategy_id,
        "signal_date": artifact.signal_date,
        "source_hash": artifact.source_hash,
        "artifact_validation": {
            "planned_execution_date": artifact_validation.planned_execution_date,
            "blockers": [asdict(item) for item in artifact_validation.blockers],
            "warnings": [asdict(item) for item in artifact_validation.warnings],
        },
        "account": asdict(account),
        "positions": [asdict(item) for item in sorted(current_positions, key=lambda item: item.code)],
        "orders": [asdict(item) for item in sorted(recent_orders, key=lambda item: item.order_id)],
        "quotes": {key: asdict(quotes[key]) for key in sorted(quotes)},
        "maximum_quantities": {key: asdict(maximum_quantities[key]) for key in sorted(maximum_quantities)},
        "managed_codes": sorted(managed_codes),
        "planning_config": asdict(config),
    }
    return ExecutionPlan(
        schema_version="quantbuddy.execution-plan.v1",
        plan_id=_stable_plan_id(id_payload),
        strategy_id=metadata.strategy_id,
        signal_date=artifact.signal_date,
        planned_execution_date=artifact_validation.planned_execution_date,
        generated_at=account.captured_at,
        source_artifact=artifact.source_artifact,
        source_hash=artifact.source_hash,
        account_id_masked=account.account_id_masked,
        market=account.market,
        trading_environment=account.trading_environment,
        cash_before=account.cash,
        market_value_before=account.market_value,
        total_assets_before=account.total_assets,
        target_positions=target_positions,
        current_positions=sorted(current_positions, key=lambda item: item.code),
        reconciliation=reconciliation,
        planned_sells=sell_orders,
        planned_buys=buy_orders,
        cash_reserved=cash_reserved,
        estimated_cash_after=estimated_cash_after,
        estimated_turnover=estimated_turnover,
        warnings=warnings,
        blockers=blockers,
        executable=not blockers,
        dry_run=True,
    )
