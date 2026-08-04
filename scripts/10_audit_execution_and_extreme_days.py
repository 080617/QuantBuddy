from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import numpy as np
import pandas as pd
import qlib
from qlib.config import REG_CN
from qlib.data import D


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "outputs" / "backtest" / "v1"
OUTPUT_DIR = INPUT_DIR / "execution_audit"
PROVIDER_URI = PROJECT_ROOT / "data" / "qlib" / "cn_data"

TOPK = 5
RISK_DEGREE_ASSUMPTION = 0.95
BOARD_LOT = 100
LIMIT_THRESHOLD = 0.095


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=lambda x: (
                x.isoformat()
                if isinstance(x, (pd.Timestamp, np.datetime64))
                else float(x)
                if isinstance(x, np.floating)
                else int(x)
                if isinstance(x, np.integer)
                else bool(x)
                if isinstance(x, np.bool_)
                else str(x)
            ),
        ),
        encoding="utf-8",
    )


def previous_date_map(dates: list[pd.Timestamp]) -> dict[pd.Timestamp, pd.Timestamp | None]:
    ordered = sorted(pd.Timestamp(x) for x in dates)
    result: dict[pd.Timestamp, pd.Timestamp | None] = {}
    previous: pd.Timestamp | None = None
    for date in ordered:
        result[date] = previous
        previous = date
    return result


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = [
        "top5_predictions.csv",
        "holdings.csv",
        "position_summary.csv",
        "daily_report.csv",
    ]
    missing = [name for name in required if not (INPUT_DIR / name).exists()]
    if missing:
        raise FileNotFoundError(f"缺少必要文件：{missing}")

    top5 = pd.read_csv(
        INPUT_DIR / "top5_predictions.csv",
        parse_dates=["datetime"],
    )
    holdings = pd.read_csv(
        INPUT_DIR / "holdings.csv",
        parse_dates=["datetime"],
    )
    position_summary = pd.read_csv(
        INPUT_DIR / "position_summary.csv",
        parse_dates=["datetime"],
    )
    report = pd.read_csv(
        INPUT_DIR / "daily_report.csv",
        parse_dates=["datetime"],
    )

    top5["instrument"] = top5["instrument"].astype(str).str.upper()
    holdings["instrument"] = holdings["instrument"].astype(str).str.upper()

    return (
        top5.sort_values(["datetime", "rank_desc"]),
        holdings.sort_values(["datetime", "instrument"]),
        position_summary.sort_values("datetime"),
        report.sort_values("datetime"),
    )


def set_by_date(df: pd.DataFrame) -> dict[pd.Timestamp, set[str]]:
    result: dict[pd.Timestamp, set[str]] = {}
    for date, group in df.groupby("datetime"):
        result[pd.Timestamp(date)] = set(group["instrument"].astype(str))
    return result


def infer_signal_lag(
    top5: pd.DataFrame,
    holdings: pd.DataFrame,
    trading_dates: list[pd.Timestamp],
) -> tuple[int, pd.DataFrame]:
    signal_sets = set_by_date(top5)
    holding_sets = set_by_date(holdings)
    prev_map = previous_date_map(trading_dates)

    rows: list[dict[str, Any]] = []
    for date in trading_dates:
        held = holding_sets.get(date, set())
        same_signal = signal_sets.get(date, set())
        previous_date = prev_map.get(date)
        previous_signal = signal_sets.get(previous_date, set()) if previous_date else set()

        same_overlap = len(held & same_signal)
        previous_overlap = len(held & previous_signal)

        rows.append(
            {
                "datetime": date,
                "holding_count": len(held),
                "same_day_top5_overlap": same_overlap,
                "previous_day_top5_overlap": previous_overlap,
            }
        )

    alignment = pd.DataFrame(rows)
    valid = alignment[alignment["holding_count"] > 0]

    same_mean = float(valid["same_day_top5_overlap"].mean()) if len(valid) else 0.0
    previous_mean = (
        float(valid["previous_day_top5_overlap"].mean()) if len(valid) else 0.0
    )

    # Qlib日频回测通常以此前信号形成下一交易日持仓；
    # 仍以实际重合度自动选择，避免硬编码。
    selected_lag = 1 if previous_mean >= same_mean else 0

    alignment["selected_signal_lag"] = selected_lag
    alignment["same_day_mean_overlap"] = same_mean
    alignment["previous_day_mean_overlap"] = previous_mean

    return selected_lag, alignment


def load_market_features(
    symbols: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    features = D.features(
        symbols,
        [
            "$close",
            "$factor",
            "$close/Ref($close,1)-1",
        ],
        start_time=start_date.strftime("%Y-%m-%d"),
        end_time=end_date.strftime("%Y-%m-%d"),
    ).reset_index()

    features = features.rename(
        columns={
            "$close": "adjusted_close",
            "$factor": "factor",
            "$close/Ref($close,1)-1": "daily_return",
        }
    )
    features["instrument"] = features["instrument"].astype(str).str.upper()
    features["datetime"] = pd.to_datetime(features["datetime"])
    features["raw_close"] = features["adjusted_close"] / features["factor"]
    features["one_lot_cost"] = features["raw_close"] * BOARD_LOT

    return features


def audit_low_holding_days(
    top5: pd.DataFrame,
    holdings: pd.DataFrame,
    position_summary: pd.DataFrame,
    report: pd.DataFrame,
    market: pd.DataFrame,
    signal_lag: int,
) -> pd.DataFrame:
    trading_dates = sorted(pd.Timestamp(x) for x in report["datetime"].unique())
    prev_map = previous_date_map(trading_dates)

    signal_groups = {
        pd.Timestamp(date): group.sort_values("rank_desc").copy()
        for date, group in top5.groupby("datetime")
    }
    holding_sets = set_by_date(holdings)

    report_by_date = report.set_index("datetime")
    position_by_date = position_summary.set_index("datetime")
    market_lookup = market.set_index(["datetime", "instrument"])

    rows: list[dict[str, Any]] = []

    low_days = position_summary[position_summary["holding_count"] < TOPK]

    for _, position_row in low_days.iterrows():
        date = pd.Timestamp(position_row["datetime"])
        signal_date = date if signal_lag == 0 else prev_map.get(date)
        signal_group = signal_groups.get(signal_date, pd.DataFrame())
        held = holding_sets.get(date, set())

        account_value = safe_float(position_row.get("account_value")) or 0.0
        target_budget = (
            account_value * RISK_DEGREE_ASSUMPTION / TOPK
            if account_value > 0
            else None
        )

        if signal_group.empty:
            rows.append(
                {
                    "datetime": date,
                    "signal_date": signal_date,
                    "holding_count": int(position_row["holding_count"]),
                    "cash_ratio": safe_float(position_row["cash_ratio"]),
                    "candidate_rank": None,
                    "candidate": None,
                    "candidate_score": None,
                    "raw_close": None,
                    "one_lot_cost": None,
                    "target_budget_per_stock": target_budget,
                    "daily_return": None,
                    "missing_price": True,
                    "limit_up_like": False,
                    "lot_unaffordable": False,
                    "likely_reason": "no_signal_available",
                }
            )
            continue

        missing_candidates = signal_group[
            ~signal_group["instrument"].isin(held)
        ].copy()

        # 第一优先审计最高排名、但没有进入实际持仓的候选。
        if missing_candidates.empty:
            rows.append(
                {
                    "datetime": date,
                    "signal_date": signal_date,
                    "holding_count": int(position_row["holding_count"]),
                    "cash_ratio": safe_float(position_row["cash_ratio"]),
                    "candidate_rank": None,
                    "candidate": None,
                    "candidate_score": None,
                    "raw_close": None,
                    "one_lot_cost": None,
                    "target_budget_per_stock": target_budget,
                    "daily_return": None,
                    "missing_price": False,
                    "limit_up_like": False,
                    "lot_unaffordable": False,
                    "likely_reason": "top5_already_held_but_position_count_low",
                }
            )
            continue

        candidate_row = missing_candidates.iloc[0]
        candidate = str(candidate_row["instrument"]).upper()

        market_row = None
        try:
            market_row = market_lookup.loc[(date, candidate)]
            if isinstance(market_row, pd.DataFrame):
                market_row = market_row.iloc[0]
        except KeyError:
            market_row = None

        raw_close = (
            safe_float(market_row.get("raw_close"))
            if market_row is not None
            else None
        )
        one_lot_cost = (
            safe_float(market_row.get("one_lot_cost"))
            if market_row is not None
            else None
        )
        daily_return = (
            safe_float(market_row.get("daily_return"))
            if market_row is not None
            else None
        )

        missing_price = raw_close is None
        limit_up_like = (
            daily_return is not None
            and daily_return >= LIMIT_THRESHOLD
        )
        lot_unaffordable = (
            one_lot_cost is not None
            and target_budget is not None
            and one_lot_cost > target_budget
        )

        if missing_price:
            reason = "missing_execution_price"
        elif limit_up_like:
            reason = "limit_up_like_buy_block"
        elif lot_unaffordable:
            reason = "board_lot_too_expensive"
        else:
            reason = "other_or_strategy_turnover_rule"

        rows.append(
            {
                "datetime": date,
                "signal_date": signal_date,
                "holding_count": int(position_row["holding_count"]),
                "cash_ratio": safe_float(position_row["cash_ratio"]),
                "candidate_rank": safe_float(candidate_row.get("rank_desc")),
                "candidate": candidate,
                "candidate_score": safe_float(candidate_row.get("score")),
                "raw_close": raw_close,
                "one_lot_cost": one_lot_cost,
                "target_budget_per_stock": target_budget,
                "daily_return": daily_return,
                "missing_price": missing_price,
                "limit_up_like": limit_up_like,
                "lot_unaffordable": lot_unaffordable,
                "likely_reason": reason,
            }
        )

    return pd.DataFrame(rows)


def audit_extreme_return_contributions(
    holdings: pd.DataFrame,
    report: pd.DataFrame,
    market: pd.DataFrame,
    count: int = 20,
) -> pd.DataFrame:
    trading_dates = sorted(pd.Timestamp(x) for x in report["datetime"].unique())
    prev_map = previous_date_map(trading_dates)

    holding_groups = {
        pd.Timestamp(date): group.copy()
        for date, group in holdings.groupby("datetime")
    }
    market_lookup = market.set_index(["datetime", "instrument"])

    return_column = (
        "account_return_after_cost"
        if "account_return_after_cost" in report.columns
        else "strategy_return_after_cost_qlib"
    )

    extreme_dates = (
        report.assign(abs_return=report[return_column].abs())
        .nlargest(count, "abs_return")["datetime"]
        .tolist()
    )

    rows: list[dict[str, Any]] = []

    for date_value in extreme_dates:
        date = pd.Timestamp(date_value)
        prior_date = prev_map.get(date)
        prior_holdings = holding_groups.get(prior_date, pd.DataFrame())

        if prior_holdings.empty:
            continue

        for _, holding in prior_holdings.iterrows():
            symbol = str(holding["instrument"]).upper()
            try:
                market_row = market_lookup.loc[(date, symbol)]
                if isinstance(market_row, pd.DataFrame):
                    market_row = market_row.iloc[0]
                stock_return = safe_float(market_row.get("daily_return"))
            except KeyError:
                stock_return = None

            weight = safe_float(holding.get("weight"))
            approximate_contribution = (
                weight * stock_return
                if weight is not None and stock_return is not None
                else None
            )

            portfolio_row = report.loc[
                report["datetime"].eq(date)
            ].iloc[0]

            rows.append(
                {
                    "datetime": date,
                    "prior_position_date": prior_date,
                    "instrument": symbol,
                    "prior_weight": weight,
                    "stock_daily_return": stock_return,
                    "approximate_contribution": approximate_contribution,
                    "portfolio_return_after_cost": safe_float(
                        portfolio_row.get(return_column)
                    ),
                }
            )

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(
            ["datetime", "approximate_contribution"],
            ascending=[True, False],
        )
    return result


def main() -> None:
    if not PROVIDER_URI.exists():
        raise FileNotFoundError(f"Qlib数据目录不存在：{PROVIDER_URI}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    top5, holdings, position_summary, report = load_inputs()
    trading_dates = sorted(pd.Timestamp(x) for x in report["datetime"].unique())

    qlib.init(
        provider_uri=str(PROVIDER_URI),
        region=REG_CN,
    )

    signal_lag, alignment = infer_signal_lag(
        top5,
        holdings,
        trading_dates,
    )
    alignment.to_csv(
        OUTPUT_DIR / "signal_alignment.csv",
        index=False,
        encoding="utf-8-sig",
    )

    symbols = sorted(
        set(top5["instrument"]) | set(holdings["instrument"])
    )
    market = load_market_features(
        symbols,
        min(trading_dates),
        max(trading_dates),
    )
    market.to_csv(
        OUTPUT_DIR / "market_features_used.csv",
        index=False,
        encoding="utf-8-sig",
    )

    low_holding = audit_low_holding_days(
        top5,
        holdings,
        position_summary,
        report,
        market,
        signal_lag,
    )
    low_holding.to_csv(
        OUTPUT_DIR / "low_holding_candidate_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    reason_summary = (
        low_holding["likely_reason"]
        .value_counts(dropna=False)
        .rename_axis("likely_reason")
        .reset_index(name="days")
    )
    reason_summary["share"] = (
        reason_summary["days"] / len(low_holding)
        if len(low_holding)
        else 0.0
    )
    reason_summary.to_csv(
        OUTPUT_DIR / "low_holding_reason_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    extreme = audit_extreme_return_contributions(
        holdings,
        report,
        market,
    )
    extreme.to_csv(
        OUTPUT_DIR / "extreme_day_contributions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    same_mean = safe_float(
        alignment["same_day_mean_overlap"].iloc[0]
    ) if len(alignment) else None
    previous_mean = safe_float(
        alignment["previous_day_mean_overlap"].iloc[0]
    ) if len(alignment) else None

    contribution_checks: list[dict[str, Any]] = []
    if not extreme.empty:
        for date, group in extreme.groupby("datetime"):
            portfolio_return = safe_float(
                group["portfolio_return_after_cost"].iloc[0]
            )
            explained = safe_float(
                group["approximate_contribution"].sum(min_count=1)
            )
            contribution_checks.append(
                {
                    "datetime": pd.Timestamp(date),
                    "portfolio_return_after_cost": portfolio_return,
                    "sum_previous_holdings_contribution": explained,
                    "difference": (
                        portfolio_return - explained
                        if portfolio_return is not None and explained is not None
                        else None
                    ),
                }
            )

    contribution_check_df = pd.DataFrame(contribution_checks)
    contribution_check_df.to_csv(
        OUTPUT_DIR / "extreme_day_contribution_check.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "signal_alignment": {
            "selected_signal_lag_trading_days": signal_lag,
            "same_day_mean_top5_overlap": same_mean,
            "previous_day_mean_top5_overlap": previous_mean,
        },
        "low_holding_days": {
            "total": int(len(low_holding)),
            "reason_counts": {
                str(row["likely_reason"]): int(row["days"])
                for _, row in reason_summary.iterrows()
            },
            "board_lot_too_expensive_days": int(
                low_holding["lot_unaffordable"].sum()
            ) if len(low_holding) else 0,
            "limit_up_like_days": int(
                low_holding["limit_up_like"].sum()
            ) if len(low_holding) else 0,
            "missing_execution_price_days": int(
                low_holding["missing_price"].sum()
            ) if len(low_holding) else 0,
        },
        "assumptions": {
            "topk": TOPK,
            "risk_degree_for_affordability_test": RISK_DEGREE_ASSUMPTION,
            "board_lot": BOARD_LOT,
            "limit_threshold": LIMIT_THRESHOLD,
            "note": (
                "缺仓原因是基于候选价格、100股一手、涨停阈值及Top5持仓差异的诊断；"
                "other_or_strategy_turnover_rule仍需结合Qlib逐笔订单确认。"
            ),
        },
    }
    write_json(
        OUTPUT_DIR / "execution_audit_summary.json",
        summary,
    )

    print("=" * 76)
    print("执行与异常收益审计完成")
    print("=" * 76)
    print(f"输出目录：{OUTPUT_DIR}")
    print(
        "选定的信号滞后："
        f"{signal_lag}个交易日 "
        f"(同日重合均值={same_mean:.3f}, "
        f"前一日重合均值={previous_mean:.3f})"
    )
    print(f"持仓不足5只的日期：{len(low_holding)}")
    print("缺仓原因统计：")
    for _, row in reason_summary.iterrows():
        print(
            f"  {row['likely_reason']}: "
            f"{int(row['days'])}天 "
            f"({float(row['share']):.1%})"
        )
    print("=" * 76)
    print("核心文件：")
    print("  execution_audit_summary.json")
    print("  low_holding_candidate_audit.csv")
    print("  low_holding_reason_summary.csv")
    print("  extreme_day_contributions.csv")
    print("  extreme_day_contribution_check.csv")
    print("=" * 76)


if __name__ == "__main__":
    main()
