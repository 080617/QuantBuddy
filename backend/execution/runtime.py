"""Read-only Futu snapshot collection and dry-run plan orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Callable

from backend.futu import AccountService, FutuClient, OrderService, QuoteService
from backend.futu.code_mapper import futu_to_qlib, qlib_to_futu
from backend.futu.models import OrderRecord, QuoteSnapshot, TradableQuantity
from backend.futu.safety import mask_identifier

from .models import AccountState, CurrentPosition, ExecutionArtifact, ExecutionPlan, PlanningConfig
from .order_planner import build_execution_plan
from .signal_validator import ArtifactValidation
from .target_portfolio import derive_topk_dropout_transition


def build_readonly_futu_plan(
    *,
    artifact: ExecutionArtifact,
    validation: ArtifactValidation,
    planning_config: PlanningConfig,
    managed_codes: set[str] | None = None,
    client_factory: Callable[[], FutuClient] = FutuClient,
    captured_at: str | None = None,
) -> ExecutionPlan:
    """Collect read-only state and plan. No write-capable method is referenced here."""
    managed_codes = managed_codes or set()
    with client_factory() as client:
        account_service = AccountService(client)
        quote_service = QuoteService(client)
        order_service = OrderService(client)
        account_summary = account_service.get_simulated_cn_account()
        funds = account_service.get_funds()
        futu_positions = account_service.get_positions()
        recent_orders = [
            replace(order, code=futu_to_qlib(order.code))
            for order in order_service.get_recent_orders()
        ]
        current_positions = [
            CurrentPosition(
                code=futu_to_qlib(position.code),
                quantity=int(position.quantity),
                sellable_quantity=int(position.sellable_quantity),
                reference_price=position.current_price,
                market_value=position.market_value,
                managed=futu_to_qlib(position.code) in managed_codes,
            )
            for position in futu_positions
        ]
        actual_managed = {position.code for position in current_positions if position.managed}
        transition = derive_topk_dropout_transition(artifact.signals, actual_managed, artifact.metadata)
        quote_codes = sorted(set(transition.keep).union(transition.sell).union(transition.buy))
        futu_codes = [qlib_to_futu(code) for code in quote_codes]
        snapshots = quote_service.get_snapshot(futu_codes) if futu_codes else []
        quotes: dict[str, QuoteSnapshot] = {
            futu_to_qlib(snapshot.code): QuoteSnapshot(
                code=futu_to_qlib(snapshot.code),
                name=snapshot.name,
                last_price=snapshot.last_price,
                lot_size=snapshot.lot_size,
                suspended=snapshot.suspended,
                update_time=snapshot.update_time,
                price_spread=snapshot.price_spread,
            )
            for snapshot in snapshots
        }
        maximum_quantities: dict[str, TradableQuantity] = {}
        for code in transition.buy:
            snapshot = quotes.get(code)
            if snapshot is None or snapshot.last_price <= 0 or snapshot.suspended:
                continue
            futu_code = qlib_to_futu(code)
            try:
                quantity = order_service.get_max_tradable_quantity(futu_code, snapshot.last_price)
            except Exception:
                continue
            maximum_quantities[code] = TradableQuantity(
                code=code,
                price=quantity.price,
                maximum_cash_buy=quantity.maximum_cash_buy,
                maximum_position_sell=quantity.maximum_position_sell,
                lot_size=quantity.lot_size,
            )
        account = AccountState(
            account_id_masked=mask_identifier(account_summary.account_id),
            market=account_summary.market,
            trading_environment=account_summary.environment,
            status=account_summary.status,
            captured_at=captured_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            cash=float(funds.cash or 0.0),
            market_value=float(funds.market_value or 0.0),
            total_assets=float(funds.total_assets or 0.0),
        )
        return build_execution_plan(
            artifact=artifact,
            artifact_validation=validation,
            account=account,
            current_positions=current_positions,
            recent_orders=recent_orders,
            quotes=quotes,
            maximum_quantities=maximum_quantities,
            managed_codes=actual_managed,
            config=planning_config,
        )
