from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "outputs" / "backtest" / "v2"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "frontend" / "dashboard_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="把Qlib V2回测结果转换为Quant Buddy工作台前端JSON。"
    )
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser.parse_args()


def num(value: Any, digits: int = 10) -> float | int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if number.is_integer() and abs(number) < 9_007_199_254_740_991:
        return int(number)
    return round(number, digits)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"找不到文件：{path}")
    frame = pd.read_csv(path)
    if "datetime" in frame.columns:
        frame["datetime"] = pd.to_datetime(frame["datetime"])
    return frame


def load_name_map() -> dict[str, str]:
    path = PROJECT_ROOT / "data" / "raw" / "akshare" / "csi300_current.csv"
    if not path.exists():
        return {"SH000300": "沪深300"}

    frame = pd.read_csv(path, dtype=str)
    code_col = next(
        (c for c in ["成分券代码", "证券代码", "code", "symbol"] if c in frame.columns),
        None,
    )
    name_col = next(
        (c for c in ["成分券名称", "证券简称", "name"] if c in frame.columns),
        None,
    )
    exchange_col = next(
        (c for c in ["交易所", "exchange"] if c in frame.columns),
        None,
    )
    if code_col is None or name_col is None:
        return {"SH000300": "沪深300"}

    mapping: dict[str, str] = {"SH000300": "沪深300"}
    for _, row in frame.iterrows():
        code = str(row[code_col]).strip().zfill(6)
        name = str(row[name_col]).strip()
        exchange = str(row[exchange_col]) if exchange_col else ""
        if "上海" in exchange or exchange.upper().startswith("SH"):
            symbol = f"SH{code}"
        elif "深圳" in exchange or exchange.upper().startswith("SZ"):
            symbol = f"SZ{code}"
        else:
            symbol = f"SH{code}" if code.startswith(("5", "6", "9")) else f"SZ{code}"
        mapping[symbol] = name
    return mapping


def latest_portfolio(
    holdings: pd.DataFrame,
    position_summary: pd.DataFrame,
    names: dict[str, str],
) -> tuple[str, dict[str, Any]]:
    latest_date = pd.Timestamp(holdings["datetime"].max())
    latest = holdings[holdings["datetime"].eq(latest_date)].copy()
    latest["instrument"] = latest["instrument"].astype(str).str.upper()
    latest = latest.sort_values("weight", ascending=False)

    items = []
    for _, row in latest.iterrows():
        symbol = row["instrument"]
        items.append(
            {
                "instrument": symbol,
                "name": names.get(symbol, symbol),
                "weight": num(row.get("weight")),
                "amount": num(row.get("amount")),
                "referencePrice": num(row.get("price")),
                "marketValue": num(row.get("market_value")),
                "holdDays": num(row.get("hold_days")),
            }
        )

    position = position_summary[position_summary["datetime"].eq(latest_date)]
    row = position.iloc[0] if not position.empty else pd.Series(dtype=object)
    payload = {
        "date": latest_date.strftime("%Y-%m-%d"),
        "status": "historical-backtest-position",
        "accountValue": num(row.get("account_value")),
        "cash": num(row.get("cash")),
        "cashRatio": num(row.get("cash_ratio")),
        "holdingCount": num(row.get("holding_count", len(items))),
        "holdings": items,
    }
    return latest_date.strftime("%Y-%m-%d"), payload


def latest_signal_and_operation(
    predictions: pd.DataFrame,
    top5: pd.DataFrame,
    holdings: pd.DataFrame,
    names: dict[str, str],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    signal_date = pd.Timestamp(top5["datetime"].max())
    latest_top5 = top5[top5["datetime"].eq(signal_date)].copy()
    latest_top5["instrument"] = latest_top5["instrument"].astype(str).str.upper()
    latest_top5 = latest_top5.sort_values("rank_desc")

    holding_date = pd.Timestamp(holdings["datetime"].max())
    held = set(
        holdings.loc[holdings["datetime"].eq(holding_date), "instrument"]
        .astype(str)
        .str.upper()
    )

    all_latest = predictions[predictions["datetime"].eq(signal_date)].copy()
    all_latest["instrument"] = all_latest["instrument"].astype(str).str.upper()
    score_map = all_latest.set_index("instrument")["score"].to_dict()
    rank_map = all_latest.set_index("instrument")["rank_desc"].to_dict()

    signal_items = []
    top_symbols = set()
    for _, row in latest_top5.iterrows():
        symbol = row["instrument"]
        top_symbols.add(symbol)
        signal_items.append(
            {
                "rank": num(row.get("rank_desc")),
                "instrument": symbol,
                "name": names.get(symbol, symbol),
                "score": num(row.get("score")),
                "scorePercentile": num(row.get("score_percentile")),
                "currentlyHeld": symbol in held,
            }
        )

    buy_candidates = [x for x in signal_items if not x["currentlyHeld"]]
    sell_candidates = []
    for symbol in held:
        if symbol not in top_symbols:
            sell_candidates.append(
                {
                    "instrument": symbol,
                    "name": names.get(symbol, symbol),
                    "score": num(score_map.get(symbol)),
                    "rank": num(rank_map.get(symbol)),
                }
            )
    sell_candidates.sort(
        key=lambda x: (x["score"] is None, x["score"] if x["score"] is not None else 0)
    )

    buy = buy_candidates[0] if buy_candidates else None
    sell = sell_candidates[0] if sell_candidates else None
    if buy and sell:
        action_type, label = "REPLACE_ONE", "建议观察一换一"
    elif buy:
        action_type, label = "BUY_CANDIDATE", "出现新候选"
    else:
        action_type, label = "HOLD", "继续持有"

    signal_payload = {
        "date": signal_date.strftime("%Y-%m-%d"),
        "status": "historical-model-output",
        "top5": signal_items,
    }
    operation_payload = {
        "type": action_type,
        "label": label,
        "buyCandidate": buy,
        "sellCandidate": sell,
        "previewOnly": True,
        "note": "这是历史模型信号预览，尚未接入实时行情、富途模拟盘和正式订单约束。",
    }
    return signal_date.strftime("%Y-%m-%d"), signal_payload, operation_payload


def risk_panel(
    summary: dict[str, Any],
    trading_days: int,
    underfilled_days: int,
    high_cash_days: int,
) -> dict[str, Any]:
    turnover = float(summary["trading"]["average_daily_turnover_rate"])
    drawdown = float(summary["strategy_after_cost"]["max_drawdown"])
    rank_ic = float(summary["signal_metrics"]["Rank IC"])
    return {
        "overall": "high",
        "overallLabel": "偏高",
        "method": "Quant Buddy Demo启发式风险标签",
        "factors": [
            {
                "key": "concentration",
                "label": "持仓集中度",
                "severity": "high",
                "value": "约5只股票",
                "reason": "Top-5组合对单只股票波动较敏感。",
            },
            {
                "key": "turnover",
                "label": "换手风险",
                "severity": "high" if turnover >= 0.30 else "medium",
                "value": num(turnover),
                "reason": "平均每日换手率较高，实盘滑点可能高于当前假设。",
            },
            {
                "key": "drawdown",
                "label": "历史回撤",
                "severity": "medium" if abs(drawdown) >= 0.20 else "low",
                "value": num(drawdown),
                "reason": "历史最大回撤超过20%。",
            },
            {
                "key": "model_signal",
                "label": "模型排序稳定性",
                "severity": "high" if rank_ic < 0.02 else "medium",
                "value": num(rank_ic),
                "reason": "Rank IC偏低，模型排序能力仍需继续验证。",
            },
            {
                "key": "execution",
                "label": "执行完整度",
                "severity": "medium",
                "value": {
                    "underfilledDays": underfilled_days,
                    "highCashDays": high_cash_days,
                    "tradingDays": trading_days,
                },
                "reason": "少量日期因不可交易或100股一手约束未持满5只。",
            },
        ],
    }


def monthly_payload(input_dir: Path) -> list[dict[str, Any]]:
    path = input_dir / "monthly_returns.csv"
    if not path.exists():
        return []
    frame = pd.read_csv(path)
    date_col = frame.columns[0]
    frame[date_col] = pd.to_datetime(frame[date_col])
    return [
        {
            "month": row[date_col].strftime("%Y-%m"),
            "strategyReturn": num(row.get("strategy_nav_after_cost")),
            "benchmarkReturn": num(row.get("benchmark_nav")),
        }
        for _, row in frame.iterrows()
    ]


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_file = input_dir / "summary.json"
    if not summary_file.exists():
        raise FileNotFoundError(f"找不到文件：{summary_file}")
    summary = json.loads(summary_file.read_text(encoding="utf-8"))

    nav = read_csv(input_dir / "daily_nav.csv").sort_values("datetime")
    holdings = read_csv(input_dir / "holdings.csv")
    position_summary = read_csv(input_dir / "position_summary.csv")
    predictions = read_csv(input_dir / "predictions.csv")
    top5 = read_csv(input_dir / "top5_predictions.csv")

    names = load_name_map()
    holding_date, portfolio = latest_portfolio(holdings, position_summary, names)
    signal_date, signals, operation = latest_signal_and_operation(
        predictions, top5, holdings, names
    )

    nav_curve = [
        {
            "date": row["datetime"].strftime("%Y-%m-%d"),
            "strategyNav": num(row.get("strategy_nav_after_cost")),
            "benchmarkNav": num(row.get("benchmark_nav")),
            "excessNav": num(row.get("qlib_excess_nav_after_cost")),
            "strategyDrawdown": num(row.get("strategy_drawdown_after_cost")),
        }
        for _, row in nav.iterrows()
    ]

    trading_days = int(summary["metadata"]["trading_days"])
    underfilled_days = int((position_summary["holding_count"] < 5).sum())
    high_cash_days = int((position_summary["cash_ratio"] > 0.20).sum())
    zero_holding_days = int((position_summary["holding_count"] == 0).sum())

    dashboard = {
        "product": {
            "name": "Quant Buddy",
            "page": "strategy-workbench",
            "language": "zh-CN",
            "dataMode": "historical-demo",
            "version": "dashboard_v1",
        },
        "asOf": {
            "backtestHoldingDate": holding_date,
            "latestSignalDate": signal_date,
            "generatedFrom": str(input_dir),
        },
        "modelSetup": {
            "model": "LightGBM",
            "featureSet": "Qlib Alpha158",
            "market": "当前沪深300固定股票池",
            "benchmark": "沪深300（SH000300）",
            "strategy": "TopkDropoutStrategy",
            "topk": 5,
            "nDrop": 1,
            "onlyTradable": True,
            "riskDegree": 0.95,
            "trainingPeriod": ["2015-01-01", "2021-12-31"],
            "validationPeriod": ["2022-01-01", "2023-12-31"],
            "testPeriod": ["2024-01-01", "2026-07-30"],
            "backtestPeriod": [
                summary["metadata"]["backtest_start"],
                summary["metadata"]["backtest_end"],
            ],
        },
        "performance": {
            "initialCapital": num(summary["metadata"]["initial_capital"]),
            "endingAccountValue": num(
                position_summary.sort_values("datetime").iloc[-1]["account_value"]
            ),
            "totalReturn": num(summary["strategy_after_cost"]["total_return"]),
            "cagr": num(summary["strategy_after_cost"]["cagr"]),
            "annualizedVolatility": num(
                summary["strategy_after_cost"]["annualized_volatility"]
            ),
            "sharpeRf0": num(summary["strategy_after_cost"]["sharpe_rf0"]),
            "maxDrawdown": num(summary["strategy_after_cost"]["max_drawdown"]),
            "benchmarkTotalReturn": num(summary["benchmark"]["total_return"]),
            "benchmarkCagr": num(summary["benchmark"]["cagr"]),
            "benchmarkMaxDrawdown": num(summary["benchmark"]["max_drawdown"]),
            "qlibAnnualizedExcessReturnAfterCost": num(
                summary["qlib_excess_analysis"]["annualized_return_after_cost"]
            ),
        },
        "signalQuality": {
            "IC": num(summary["signal_metrics"]["IC"]),
            "ICIR": num(summary["signal_metrics"]["ICIR"]),
            "rankIC": num(summary["signal_metrics"]["Rank IC"]),
            "rankICIR": num(summary["signal_metrics"]["Rank ICIR"]),
            "interpretation": "模型存在弱正向预测能力，但排序稳定性仍然偏低。",
        },
        "currentPortfolio": portfolio,
        "latestSignals": signals,
        "todayOperation": operation,
        "riskPanel": risk_panel(
            summary, trading_days, underfilled_days, high_cash_days
        ),
        "dataQuality": {
            "tradingDays": trading_days,
            "underfilledDays": underfilled_days,
            "underfilledDayRate": num(underfilled_days / trading_days),
            "highCashDays": high_cash_days,
            "highCashDayRate": num(high_cash_days / trading_days),
            "zeroHoldingDays": zero_holding_days,
            "missingCloseCells": num(
                summary["data_quality"]["close_audit"]["missing_cells"]
            ),
            "symbolsWithMissingClose": num(
                summary["data_quality"]["close_audit"]["symbols_with_missing_close"]
            ),
            "heldPositionsWithMissingPrice": num(
                summary["data_quality"]["holdings_with_nan_price"]
            ),
        },
        "trading": {
            "averageDailyTurnoverRate": num(
                summary["trading"]["average_daily_turnover_rate"]
            ),
            "medianDailyTurnoverRate": num(
                summary["trading"]["median_daily_turnover_rate"]
            ),
            "cumulativeTurnover": num(
                summary["trading"]["cumulative_turnover_currency"]
            ),
            "cumulativeCost": num(summary["trading"]["cumulative_cost_currency"]),
            "averageCashRatio": num(summary["trading"]["average_cash_ratio"]),
            "averageHoldingCount": num(
                summary["trading"]["average_holding_count"]
            ),
        },
        "communityEntry": {
            "enabled": True,
            "status": "frontend-placeholder",
            "title": "社区",
            "description": "发现并讨论其他用户分享的策略、因子与研究观点。",
            "featuredPosts": [],
        },
        "disclosures": [
            "本页面展示历史模拟回测，不代表真实交易结果或未来收益。",
            "股票池使用当前沪深300固定成分股，历史结果存在幸存者偏差。",
            "当前回测采用收盘价成交假设，尚未完全模拟T+1临近收盘执行。",
            "组合仅持有约5只股票，集中度和波动均较高。",
            "平均每日换手率较高，真实交易中的滑点可能高于当前假设。",
        ],
    }

    write_json(output_dir / "dashboard.json", dashboard)
    write_json(output_dir / "nav_curve.json", nav_curve)
    write_json(output_dir / "monthly_returns.json", monthly_payload(input_dir))
    write_json(output_dir / "current_holdings.json", portfolio)
    write_json(output_dir / "latest_signals.json", signals)
    write_json(output_dir / "operation_preview.json", operation)

    print("=" * 72)
    print("Quant Buddy工作台前端JSON生成完成")
    print("=" * 72)
    print(f"输入目录：{input_dir}")
    print(f"输出目录：{output_dir}")
    print(f"回测持仓日期：{holding_date}")
    print(f"最新信号日期：{signal_date}")
    print(f"当前持仓数：{len(portfolio['holdings'])}")
    print(f"净值点数：{len(nav_curve)}")
    print("已生成：dashboard.json、nav_curve.json、monthly_returns.json、")
    print("          current_holdings.json、latest_signals.json、operation_preview.json")
    print("=" * 72)


if __name__ == "__main__":
    main()
