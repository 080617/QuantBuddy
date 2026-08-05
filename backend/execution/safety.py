"""Independent safety gate for dry-run execution plans."""

from __future__ import annotations

from .models import AccountState, ExecutionBlocker, PlannedOrder, PlanningConfig


def collect_execution_safety_blockers(
    *,
    account: AccountState,
    strategy_id: str,
    orders: list[PlannedOrder],
    config: PlanningConfig,
    dry_run: bool,
) -> list[ExecutionBlocker]:
    blockers: list[ExecutionBlocker] = []
    if account.market != "CN":
        blockers.append(ExecutionBlocker("NON_CN_MARKET", "Execution planning only supports CN."))
    if account.trading_environment != "SIMULATE":
        blockers.append(ExecutionBlocker("REAL_ENVIRONMENT_REJECTED", "REAL trading is forbidden."))
    if account.status != "ACTIVE":
        blockers.append(ExecutionBlocker("ACCOUNT_NOT_ACTIVE", "The selected account is not ACTIVE."))
    if strategy_id not in config.allowed_strategy_ids:
        blockers.append(ExecutionBlocker("STRATEGY_NOT_ALLOWED", "Strategy is not allow-listed."))
    if not dry_run:
        blockers.append(ExecutionBlocker("DRY_RUN_REQUIRED", "Phase 2C requires dry_run=True."))
    daily_amount = 0.0
    for order in orders:
        if order.quantity <= 0 or order.lot_size <= 0 or order.quantity % order.lot_size != 0:
            blockers.append(
                ExecutionBlocker("INVALID_LOT_QUANTITY", "Order quantity is not a positive board lot.", order.code)
            )
        if order.limit_reference_price <= 0:
            blockers.append(ExecutionBlocker("INVALID_PRICE", "Reference price must be positive.", order.code))
        if order.side not in {"BUY", "SELL"}:
            blockers.append(ExecutionBlocker("SHORT_OR_UNKNOWN_SIDE", "Only long BUY/SELL transitions are allowed.", order.code))
        if order.estimated_value > config.max_single_order_amount:
            blockers.append(
                ExecutionBlocker(
                    "SINGLE_ORDER_LIMIT_EXCEEDED",
                    f"Estimated order value exceeds {config.max_single_order_amount:.2f}.",
                    order.code,
                )
            )
        daily_amount += order.estimated_value
    if daily_amount > config.max_daily_planned_amount:
        blockers.append(
            ExecutionBlocker(
                "DAILY_PLAN_LIMIT_EXCEEDED",
                f"Estimated daily planned amount exceeds {config.max_daily_planned_amount:.2f}.",
            )
        )
    return blockers


def deduplicate_blockers(blockers: list[ExecutionBlocker]) -> list[ExecutionBlocker]:
    unique = {(item.code, item.message, item.symbol): item for item in blockers}
    return [unique[key] for key in sorted(unique)]
