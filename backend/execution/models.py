"""Stable, JSON-serializable models for dry-run execution planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class StrategyExecutionMetadata:
    strategy_id: str
    model: str
    feature_set: str
    market: str
    benchmark: str
    universe: str
    strategy_class: str
    topk: int
    n_drop: int
    risk_degree: float
    only_tradable: bool
    method_sell: str
    method_buy: str
    hold_thresh: int
    deal_price: str
    open_cost: float
    close_cost: float
    min_cost: float
    signal_timing: str
    execution_timing: str
    weight_semantics: str


@dataclass(frozen=True, slots=True)
class SignalRecord:
    code: str
    score: float
    rank: int
    score_percentile: float


@dataclass(frozen=True, slots=True)
class ExecutionArtifact:
    schema_version: str
    source_kind: str
    is_mock: bool
    generated_at: str
    signal_date: str
    source_artifact: list[str]
    source_hash: str
    config_hash: str
    recorder_id: str
    calendar_path: str
    universe_path: str
    metadata: StrategyExecutionMetadata
    signals: list[SignalRecord]


@dataclass(frozen=True, slots=True)
class TargetPosition:
    code: str
    target_quantity: int
    reference_price: float
    estimated_market_value: float
    estimated_weight: float
    transition: Literal["KEEP", "BUY", "SELL"]


@dataclass(frozen=True, slots=True)
class CurrentPosition:
    code: str
    quantity: int
    sellable_quantity: int
    reference_price: float | None
    market_value: float | None
    managed: bool


@dataclass(frozen=True, slots=True)
class AccountState:
    account_id_masked: str
    market: str
    trading_environment: str
    status: str
    captured_at: str
    cash: float
    market_value: float
    total_assets: float


@dataclass(frozen=True, slots=True)
class ReconciliationItem:
    code: str
    state: Literal["KEEP", "EXIT", "ENTER", "UNMANAGED"]
    current_quantity: int
    sellable_quantity: int
    rank: int | None


@dataclass(frozen=True, slots=True)
class PlannedOrder:
    sequence: int
    phase: Literal["SELL_FIRST", "BUY_AFTER_SELL_CONFIRMATION"]
    side: Literal["BUY", "SELL"]
    code: str
    quantity: int
    limit_reference_price: float
    lot_size: int
    estimated_value: float
    estimated_fee: float
    reason: str


@dataclass(frozen=True, slots=True)
class ExecutionBlocker:
    code: str
    message: str
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionWarning:
    code: str
    message: str
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class PlanningConfig:
    allowed_strategy_ids: tuple[str, ...] = ("strategy-hs300-lightgbm-top5",)
    max_signal_age_calendar_days: int = 3
    max_single_order_amount: float = 100_000.0
    max_daily_planned_amount: float = 500_000.0
    max_turnover_ratio: float = 0.50
    max_positions: int = 5


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    schema_version: str
    plan_id: str
    strategy_id: str
    signal_date: str
    planned_execution_date: str | None
    generated_at: str
    source_artifact: list[str]
    source_hash: str
    account_id_masked: str
    market: str
    trading_environment: str
    cash_before: float
    market_value_before: float
    total_assets_before: float
    target_positions: list[TargetPosition]
    current_positions: list[CurrentPosition]
    reconciliation: list[ReconciliationItem]
    planned_sells: list[PlannedOrder]
    planned_buys: list[PlannedOrder]
    cash_reserved: float
    estimated_cash_after: float
    estimated_turnover: float
    warnings: list[ExecutionWarning] = field(default_factory=list)
    blockers: list[ExecutionBlocker] = field(default_factory=list)
    executable: bool = False
    dry_run: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
