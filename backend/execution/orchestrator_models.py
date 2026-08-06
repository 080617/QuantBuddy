"""Stable models for the Phase 2D-A shadow execution orchestrator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from backend.futu.models import OrderRecord, QuoteSnapshot, TradableQuantity

from .models import AccountState, CurrentPosition, ExecutionBlocker, ExecutionWarning


class ExecutionSessionState(str, Enum):
    CREATED = "CREATED"
    PRECHECKING = "PRECHECKING"
    READY = "READY"
    SELLING = "SELLING"
    WAITING_FOR_SELLS = "WAITING_FOR_SELLS"
    BUYING = "BUYING"
    WAITING_FOR_BUYS = "WAITING_FOR_BUYS"
    RECONCILING = "RECONCILING"
    COMPLETED = "COMPLETED"
    SHADOW_COMPLETED = "SHADOW_COMPLETED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionOrderState(str, Enum):
    PLANNED = "PLANNED"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class ExecutionPricePolicy(str, Enum):
    REFERENCE_LIMIT = "REFERENCE_LIMIT"
    OPENING_SNAPSHOT_LIMIT = "OPENING_SNAPSHOT_LIMIT"
    CURRENT_SNAPSHOT_LIMIT = "CURRENT_SNAPSHOT_LIMIT"


@dataclass(slots=True)
class ExecutionOrderIntent:
    intent_id: str
    plan_id: str
    code: str
    side: str
    planned_qty: int
    reference_price: float
    current_price: float
    relative_deviation: float
    maximum_allowed_price: float
    minimum_allowed_price: float
    lot_size: int
    estimated_amount: float
    sequence: int
    status: ExecutionOrderState
    reason: str
    source_hash: str
    filled_qty: int = 0


@dataclass(frozen=True, slots=True)
class ExecutionEvent:
    sequence: int
    occurred_at: str
    event_type: str
    state: str
    message: str
    intent_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    name: str
    status: str
    started_at: str
    completed_at: str | None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    matched: bool
    expected_positions: dict[str, int]
    simulated_positions: dict[str, int]
    differences: dict[str, int]
    estimated_cash_after: float


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    session_id: str
    state: str
    intents: int
    filled_intents: int
    blockers: int
    warnings: int
    reconciliation_matched: bool


@dataclass(frozen=True, slots=True)
class ShadowSnapshot:
    captured_at: str
    execution_date: str
    account: AccountState
    positions: list[CurrentPosition]
    recent_orders: list[OrderRecord]
    quotes: dict[str, QuoteSnapshot]
    maximum_quantities: dict[str, TradableQuantity]


@dataclass(slots=True)
class ExecutionSession:
    schema_version: str
    session_id: str
    plan_id: str
    strategy_id: str
    mode: str
    signal_date: str
    planned_execution_date: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    market: str
    trading_environment: str
    account_id_masked: str
    state: ExecutionSessionState
    shadow_mode: bool
    shadow_date_override: str | None
    plan_source_hash: str
    plan_digest: str
    account_snapshot_hash: str
    price_policy: ExecutionPricePolicy
    order_intents: list[ExecutionOrderIntent] = field(default_factory=list)
    steps: list[ExecutionStep] = field(default_factory=list)
    events: list[ExecutionEvent] = field(default_factory=list)
    warnings: list[ExecutionWarning] = field(default_factory=list)
    blockers: list[ExecutionBlocker] = field(default_factory=list)
    failure_reason: str | None = None
    final_reconciliation: ReconciliationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        return normalize(asdict(self))
