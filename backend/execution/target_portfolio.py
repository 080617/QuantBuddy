"""Reproduce Qlib TopkDropoutStrategy membership transitions without inventing weights."""

from __future__ import annotations

from dataclasses import dataclass

from .models import SignalRecord, StrategyExecutionMetadata


@dataclass(frozen=True, slots=True)
class PortfolioTransition:
    keep: tuple[str, ...]
    sell: tuple[str, ...]
    buy: tuple[str, ...]
    desired_membership: tuple[str, ...]


def derive_topk_dropout_transition(
    signals: list[SignalRecord],
    managed_codes: set[str],
    metadata: StrategyExecutionMetadata,
) -> PortfolioTransition:
    """Mirror Qlib 0.9.7 membership logic for method_sell=bottom/method_buy=top.

    Quantity/weight is deliberately not calculated here. Qlib retains unsold holdings
    and only splits post-sell cash across newly bought names.
    """
    score_by_code = {signal.code: signal.score for signal in signals}
    ordered_signals = [item.code for item in sorted(signals, key=lambda item: (item.rank, item.code))]
    current = sorted(managed_codes, key=lambda code: (-score_by_code.get(code, float("-inf")), code))
    new_count = max(0, metadata.n_drop + metadata.topk - len(current))
    today = [code for code in ordered_signals if code not in managed_codes][:new_count]
    combined = sorted(
        set(current).union(today), key=lambda code: (-score_by_code.get(code, float("-inf")), code)
    )
    bottom = set(combined[-metadata.n_drop :]) if metadata.n_drop > 0 else set()
    sells = tuple(code for code in current if code in bottom)
    buy_count = max(0, len(sells) + metadata.topk - len(current))
    buys = tuple(today[:buy_count])
    sell_set = set(sells)
    keeps = tuple(code for code in current if code not in sell_set)
    desired = tuple(list(keeps) + list(buys))
    return PortfolioTransition(keep=keeps, sell=sells, buy=buys, desired_membership=desired)
