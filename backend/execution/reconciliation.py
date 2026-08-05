"""Reconcile strategy membership with actual CN simulated positions."""

from __future__ import annotations

from .models import CurrentPosition, ReconciliationItem, SignalRecord
from .target_portfolio import PortfolioTransition


def reconcile_positions(
    current_positions: list[CurrentPosition],
    transition: PortfolioTransition,
    signals: list[SignalRecord],
) -> list[ReconciliationItem]:
    rank_by_code = {signal.code: signal.rank for signal in signals}
    current_by_code = {position.code: position for position in current_positions}
    items: list[ReconciliationItem] = []
    for position in sorted(current_positions, key=lambda item: item.code):
        if not position.managed:
            state = "UNMANAGED"
        elif position.code in transition.sell:
            state = "EXIT"
        else:
            state = "KEEP"
        items.append(
            ReconciliationItem(
                code=position.code,
                state=state,
                current_quantity=position.quantity,
                sellable_quantity=position.sellable_quantity,
                rank=rank_by_code.get(position.code),
            )
        )
    for code in transition.buy:
        if code not in current_by_code:
            items.append(
                ReconciliationItem(
                    code=code,
                    state="ENTER",
                    current_quantity=0,
                    sellable_quantity=0,
                    rank=rank_by_code.get(code),
                )
            )
    return sorted(items, key=lambda item: (item.state, item.code))
