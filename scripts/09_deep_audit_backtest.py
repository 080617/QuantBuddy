from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "outputs" / "backtest" / "v1"
OUTPUT_DIR = INPUT_DIR / "deep_audit"


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
                else str(x)
            ),
        ),
        encoding="utf-8",
    )


def main() -> None:
    required = [
        "daily_nav.csv",
        "daily_report.csv",
        "position_summary.csv",
        "holdings.csv",
        "missing_close.csv",
        "summary.json",
    ]
    missing_files = [
        name for name in required if not (INPUT_DIR / name).exists()
    ]
    if missing_files:
        raise FileNotFoundError(
            f"缺少必要文件：{missing_files}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    nav = pd.read_csv(
        INPUT_DIR / "daily_nav.csv",
        parse_dates=["datetime"],
    ).sort_values("datetime")

    report = pd.read_csv(
        INPUT_DIR / "daily_report.csv",
        parse_dates=["datetime"],
    ).sort_values("datetime")

    position_summary = pd.read_csv(
        INPUT_DIR / "position_summary.csv",
        parse_dates=["datetime"],
    ).sort_values("datetime")

    holdings = pd.read_csv(
        INPUT_DIR / "holdings.csv",
        parse_dates=["datetime"],
    )

    missing_close = pd.read_csv(
        INPUT_DIR / "missing_close.csv",
        parse_dates=["datetime"],
    )

    summary = json.loads(
        (INPUT_DIR / "summary.json").read_text(encoding="utf-8")
    )

    # 1) 检查缺失close是否与实际持仓重叠
    held_missing = holdings.merge(
        missing_close,
        on=["datetime", "instrument"],
        how="inner",
    )
    held_missing.to_csv(
        OUTPUT_DIR / "held_on_missing_close_days.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 2) 检查持仓不足、现金过高、收益异常和换手异常的日期
    merged = report.merge(
        position_summary[
            [
                "datetime",
                "holding_count",
                "cash_ratio",
            ]
        ],
        on="datetime",
        how="left",
        suffixes=("", "_position"),
    )

    return_column = (
        "account_return_after_cost"
        if "account_return_after_cost" in merged.columns
        else "strategy_return_after_cost_qlib"
    )

    abnormal = merged[
        (merged["holding_count"] < 5)
        | (merged["cash_ratio_position"] > 0.20)
        | (merged[return_column].abs() > 0.08)
        | (merged["turnover"] > merged["turnover"].quantile(0.99))
    ].copy()

    abnormal.to_csv(
        OUTPUT_DIR / "abnormal_days.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 3) 月度收益
    nav = nav.set_index("datetime")
    monthly_nav = nav[
        ["strategy_nav_after_cost", "benchmark_nav"]
    ].resample("ME").last()

    monthly_return = monthly_nav.pct_change()
    if len(monthly_return):
        monthly_return.iloc[0] = monthly_nav.iloc[0] - 1.0

    monthly_return = monthly_return.rename(
        columns={
            "strategy_nav_after_cost": "strategy_monthly_return",
            "benchmark_nav": "benchmark_monthly_return",
        }
    )
    monthly_return["excess_monthly_return"] = (
        monthly_return["strategy_monthly_return"]
        - monthly_return["benchmark_monthly_return"]
    )
    monthly_return.reset_index().to_csv(
        OUTPUT_DIR / "monthly_return_audit.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 4) 收益是否集中在少数交易日
    daily_returns = pd.to_numeric(
        report[return_column],
        errors="coerce",
    ).dropna()

    positive_returns = daily_returns[daily_returns > 0]
    top_10_positive = positive_returns.nlargest(10)

    positive_sum = float(positive_returns.sum())
    top_10_positive_share = (
        float(top_10_positive.sum() / positive_sum)
        if positive_sum > 0
        else None
    )

    top_days = report.loc[
        daily_returns.abs().sort_values(ascending=False).head(20).index,
        [
            "datetime",
            return_column,
            "turnover",
            "cost",
            "cash",
            "account",
        ],
    ].copy()
    top_days.to_csv(
        OUTPUT_DIR / "largest_absolute_return_days.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 5) 持仓数量与现金分布
    holding_distribution = (
        position_summary["holding_count"]
        .value_counts()
        .sort_index()
        .rename_axis("holding_count")
        .reset_index(name="days")
    )
    holding_distribution["share"] = (
        holding_distribution["days"] / len(position_summary)
    )
    holding_distribution.to_csv(
        OUTPUT_DIR / "holding_count_distribution.csv",
        index=False,
        encoding="utf-8-sig",
    )

    zero_holding_days = position_summary[
        position_summary["holding_count"] == 0
    ].copy()
    zero_holding_days.to_csv(
        OUTPUT_DIR / "zero_holding_days.csv",
        index=False,
        encoding="utf-8-sig",
    )

    high_cash_days = position_summary[
        position_summary["cash_ratio"] > 0.20
    ].copy()
    high_cash_days.to_csv(
        OUTPUT_DIR / "high_cash_days.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # 6) 最佳/最差月份
    best_months = (
        monthly_return["strategy_monthly_return"]
        .nlargest(5)
        .reset_index()
    )
    worst_months = (
        monthly_return["strategy_monthly_return"]
        .nsmallest(5)
        .reset_index()
    )

    best_months.to_csv(
        OUTPUT_DIR / "best_months.csv",
        index=False,
        encoding="utf-8-sig",
    )
    worst_months.to_csv(
        OUTPUT_DIR / "worst_months.csv",
        index=False,
        encoding="utf-8-sig",
    )

    result = {
        "core_result": {
            "strategy_cagr": summary["strategy_after_cost"]["cagr"],
            "strategy_sharpe_rf0": summary["strategy_after_cost"]["sharpe_rf0"],
            "strategy_max_drawdown": summary["strategy_after_cost"]["max_drawdown"],
            "benchmark_cagr": summary["benchmark"]["cagr"],
            "IC": summary["signal_metrics"]["IC"],
            "Rank_IC": summary["signal_metrics"]["Rank IC"],
        },
        "missing_close": {
            "all_missing_cells": summary["data_quality"]["close_audit"]["missing_cells"],
            "symbols_with_missing_close": summary["data_quality"]["close_audit"]["symbols_with_missing_close"],
            "held_missing_overlap_rows": int(len(held_missing)),
            "held_missing_overlap_dates": int(
                held_missing["datetime"].nunique()
            ) if not held_missing.empty else 0,
            "held_missing_overlap_symbols": int(
                held_missing["instrument"].nunique()
            ) if not held_missing.empty else 0,
        },
        "portfolio_structure": {
            "zero_holding_days": int(len(zero_holding_days)),
            "high_cash_days_over_20pct": int(len(high_cash_days)),
            "days_with_exactly_5_holdings": int(
                (position_summary["holding_count"] == 5).sum()
            ),
            "days_with_fewer_than_5_holdings": int(
                (position_summary["holding_count"] < 5).sum()
            ),
            "median_holding_count": safe_float(
                position_summary["holding_count"].median()
            ),
            "median_cash_ratio": safe_float(
                position_summary["cash_ratio"].median()
            ),
        },
        "return_concentration": {
            "top_10_positive_days_share_of_all_positive_return_sum": safe_float(
                top_10_positive_share
            ),
            "largest_daily_gain": safe_float(daily_returns.max()),
            "largest_daily_loss": safe_float(daily_returns.min()),
            "positive_days": int((daily_returns > 0).sum()),
            "negative_days": int((daily_returns < 0).sum()),
        },
        "trading": {
            "average_daily_turnover_rate": summary["trading"]["average_daily_turnover_rate"],
            "median_daily_turnover_rate": summary["trading"]["median_daily_turnover_rate"],
            "cumulative_turnover_currency": summary["trading"]["cumulative_turnover_currency"],
            "cumulative_cost_currency": summary["trading"]["cumulative_cost_currency"],
        },
        "audit_flags": {
            "weak_rank_ic_vs_high_cagr": (
                summary["signal_metrics"]["Rank IC"] < 0.02
                and summary["strategy_after_cost"]["cagr"] > 0.40
            ),
            "held_positions_with_missing_close": len(held_missing) > 0,
            "daily_turnover_above_30pct": (
                summary["trading"]["average_daily_turnover_rate"] > 0.30
            ),
            "fixed_current_csi300_survivorship_bias": True,
        },
    }

    write_json(
        OUTPUT_DIR / "deep_audit_summary.json",
        result,
    )

    print("=" * 72)
    print("深度审计完成")
    print("=" * 72)
    print(f"输出目录：{OUTPUT_DIR}")
    print(f"缺失close总单元格：{result['missing_close']['all_missing_cells']}")
    print(
        "缺失close与实际持仓重叠："
        f"{result['missing_close']['held_missing_overlap_rows']} 条"
    )
    print(
        "持仓少于5只的交易日："
        f"{result['portfolio_structure']['days_with_fewer_than_5_holdings']}"
    )
    print(
        "现金比例高于20%的交易日："
        f"{result['portfolio_structure']['high_cash_days_over_20pct']}"
    )
    print(
        "单日最大上涨："
        f"{result['return_concentration']['largest_daily_gain']:.2%}"
    )
    print(
        "单日最大下跌："
        f"{result['return_concentration']['largest_daily_loss']:.2%}"
    )
    print(
        "前10个正收益日占全部正收益之和："
        f"{result['return_concentration']['top_10_positive_days_share_of_all_positive_return_sum']:.2%}"
    )
    print("=" * 72)
    print("核心文件：deep_audit_summary.json")


if __name__ == "__main__":
    main()
