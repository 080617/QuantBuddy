from __future__ import annotations

from datetime import date

from backend.execution.models import (
    AccountState,
    ExecutionArtifact,
    PlanningConfig,
    SignalRecord,
    StrategyExecutionMetadata,
)
from backend.execution.signal_validator import ArtifactValidation


def metadata(**changes):
    values = dict(
        strategy_id="strategy-hs300-lightgbm-top5",
        model="LGBModel",
        feature_set="Alpha158",
        market="CN",
        benchmark="SH000300",
        universe="csi300",
        strategy_class="TopkDropoutStrategy",
        topk=5,
        n_drop=1,
        risk_degree=0.95,
        only_tradable=True,
        method_sell="bottom",
        method_buy="top",
        hold_thresh=1,
        deal_price="close",
        open_cost=0.0005,
        close_cost=0.0015,
        min_cost=5.0,
        signal_timing="previous Qlib trade step signal (T) selected by shift=1",
        execution_timing="next Qlib trade step (T+1) at configured close deal_price",
        weight_semantics=(
            "retain unsold holdings without rebalancing; sell selected holdings in full; "
            "split post-sell cash * risk_degree equally only across newly bought names"
        ),
    )
    values.update(changes)
    return StrategyExecutionMetadata(**values)


def signals(count: int = 7):
    codes = ["SH600000", "SH600009", "SH600010", "SH600011", "SH600015", "SH600016", "SH600018"]
    return [
        SignalRecord(
            code=code,
            score=1.0 - index / 10,
            rank=index + 1,
            score_percentile=1 - index / 20,
            target_weight=0.19 if index < 5 else 0.0,
        )
        for index, code in enumerate(codes[:count])
    ]


def artifact(**changes):
    values = dict(
        schema_version="quantbuddy.execution-artifact.v1",
        source_kind="backend_qlib_recorder_export",
        is_mock=False,
        generated_at="2026-07-30T12:00:00+00:00",
        signal_date="2026-07-30",
        source_artifact=["outputs/backtest/v2/predictions.csv"],
        source_hash="a" * 64,
        config_hash="b" * 64,
        recorder_id="recorder-test",
        calendar_path="data/qlib/cn_data/calendars/day.txt",
        universe_path="data/qlib/cn_data/instruments/csi300.txt",
        metadata=metadata(),
        signals=signals(),
        data_as_of="2026-07-30",
    )
    values.update(changes)
    return ExecutionArtifact(**values)


def validation(*, blockers=None):
    return ArtifactValidation("2026-07-31", blockers or [], [])


def account(**changes):
    values = dict(
        account_id_masked="****1001",
        market="CN",
        trading_environment="SIMULATE",
        status="ACTIVE",
        captured_at="2026-07-31T01:00:00+00:00",
        cash=100_000.0,
        market_value=0.0,
        total_assets=100_000.0,
    )
    values.update(changes)
    return AccountState(**values)


def permissive_config(**changes):
    values = dict(
        max_signal_age_calendar_days=10,
        max_single_order_amount=1_000_000.0,
        max_daily_planned_amount=2_000_000.0,
        max_turnover_ratio=1.0,
    )
    values.update(changes)
    return PlanningConfig(**values)
