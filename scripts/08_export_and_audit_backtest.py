from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import shutil
import sys
from pathlib import Path
from typing import Any

# Qlib 0.9.7 uses MLflow's local file backend by default.
# Newer MLflow versions require this compatibility switch.
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

import numpy as np
import pandas as pd
import qlib
from qlib.config import REG_CN
from qlib.data import D
from qlib.workflow import R


DEFAULT_EXPERIMENT = "workflow"
DEFAULT_RECORDER_ID = "254c3b835b174b5f9df375aee9a92256"
DEFAULT_INITIAL_CAPITAL = 100_000.0
ANNUALIZATION_FACTOR = 252

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_URI = PROJECT_ROOT / "data" / "qlib" / "cn_data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "backtest" / "v1"

ARTIFACT_NAMES = {
    "predictions": "pred.pkl",
    "labels": "label.pkl",
    "model": "params.pkl",
    "task": "task",
    "dataset": "dataset",
    "ic": "sig_analysis/ic.pkl",
    "rank_ic": "sig_analysis/ric.pkl",
    "daily_report": "portfolio_analysis/report_normal_1day.pkl",
    "positions": "portfolio_analysis/positions_normal_1day.pkl",
    "risk_analysis": "portfolio_analysis/port_analysis_1day.pkl",
    "daily_indicators": "portfolio_analysis/indicators_normal_1day.pkl",
    "daily_indicators_object": "portfolio_analysis/indicators_normal_1day_obj.pkl",
    "indicator_analysis": "portfolio_analysis/indicator_analysis_1day.pkl",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="导出并审计 QuantBuddy 的 Qlib LightGBM 回测结果。"
    )
    parser.add_argument(
        "--experiment",
        default=DEFAULT_EXPERIMENT,
        help=f"Qlib实验名称，默认：{DEFAULT_EXPERIMENT}",
    )
    parser.add_argument(
        "--recorder-id",
        default=DEFAULT_RECORDER_ID,
        help=f"Qlib Recorder ID，默认：{DEFAULT_RECORDER_ID}",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"输出目录，默认：{DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--skip-close-audit",
        action="store_true",
        help="跳过全股票池缺失close审计，可缩短运行时间。",
    )
    return parser.parse_args()


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if not math.isfinite(number) else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Series):
        return value.to_dict()
    if isinstance(value, pd.DataFrame):
        return value.reset_index().to_dict(orient="records")
    if isinstance(value, (set, tuple)):
        return list(value)
    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def safe_load(recorder: Any, name: str, required: bool = False) -> Any:
    try:
        print(f"读取 artifact：{name}")
        return recorder.load_object(name)
    except Exception as exc:
        if required:
            raise RuntimeError(f"必须的artifact读取失败：{name}") from exc
        print(f"  跳过：{name}（{type(exc).__name__}: {exc}）")
        return None


def list_artifact_tree(recorder: Any) -> list[str]:
    paths: set[str] = set()

    def visit(path: str | None, depth: int) -> None:
        if depth > 4:
            return
        try:
            entries = recorder.list_artifacts(path)
        except Exception:
            return

        for entry in entries:
            entry = str(entry).replace("\\", "/")
            paths.add(entry)

            # MLflow只在目录层级被查询时继续列出内容。
            # 已知Qlib目录优先递归，其他无扩展名的条目也尝试递归。
            name = entry.rsplit("/", 1)[-1]
            if (
                name in {"portfolio_analysis", "sig_analysis"}
                or "." not in name
            ):
                visit(entry, depth + 1)

    visit(None, 0)
    return sorted(paths)


def extract_initial_capital(task: Any) -> float:
    """从qrun保存的task配置中递归寻找backtest.account。"""

    def search(node: Any) -> float | None:
        if isinstance(node, dict):
            backtest = node.get("backtest")
            if isinstance(backtest, dict):
                account = safe_float(backtest.get("account"))
                if account is not None and account > 0:
                    return account

            for value in node.values():
                result = search(value)
                if result is not None:
                    return result

        elif isinstance(node, (list, tuple)):
            for value in node:
                result = search(value)
                if result is not None:
                    return result

        return None

    result = search(task)
    return result if result is not None else DEFAULT_INITIAL_CAPITAL


def normalize_datetime_index(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result.index = pd.to_datetime(result.index)
    result = result.sort_index()
    result.index.name = "datetime"
    return result


def calculate_max_drawdown(nav: pd.Series) -> float | None:
    clean = pd.to_numeric(nav, errors="coerce").dropna()
    if clean.empty:
        return None
    drawdown = clean / clean.cummax() - 1.0
    return safe_float(drawdown.min())


def calculate_performance(
    nav: pd.Series,
    daily_returns: pd.Series,
    annualization: int = ANNUALIZATION_FACTOR,
) -> dict[str, Any]:
    clean_nav = pd.to_numeric(nav, errors="coerce").dropna()
    clean_returns = pd.to_numeric(daily_returns, errors="coerce").dropna()

    if clean_nav.empty:
        return {
            "total_return": None,
            "cagr": None,
            "annualized_volatility": None,
            "sharpe_rf0": None,
            "max_drawdown": None,
        }

    start_nav = float(clean_nav.iloc[0])
    end_nav = float(clean_nav.iloc[-1])
    periods = len(clean_returns)

    total_return = end_nav / start_nav - 1.0 if start_nav > 0 else None
    cagr = None
    if start_nav > 0 and end_nav > 0 and periods > 0:
        cagr = (end_nav / start_nav) ** (annualization / periods) - 1.0

    annualized_volatility = None
    sharpe = None
    if len(clean_returns) >= 2:
        daily_std = float(clean_returns.std(ddof=1))
        annualized_volatility = daily_std * math.sqrt(annualization)
        if daily_std > 0:
            sharpe = (
                float(clean_returns.mean())
                / daily_std
                * math.sqrt(annualization)
            )

    return {
        "total_return": safe_float(total_return),
        "cagr": safe_float(cagr),
        "annualized_volatility": safe_float(annualized_volatility),
        "sharpe_rf0": safe_float(sharpe),
        "max_drawdown": calculate_max_drawdown(clean_nav),
    }


def build_daily_outputs(
    report: pd.DataFrame,
    initial_capital: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "account",
        "return",
        "turnover",
        "cost",
        "cash",
        "bench",
    }
    missing = required - set(report.columns)
    if missing:
        raise ValueError(
            f"report_normal缺少必要字段：{sorted(missing)}；"
            f"实际字段：{report.columns.tolist()}"
        )

    daily = normalize_datetime_index(report)

    # Qlib的return是成本前收益；account已实际扣除了交易成本。
    daily["strategy_return_before_cost"] = daily["return"]
    daily["strategy_return_after_cost_qlib"] = (
        daily["return"] - daily["cost"]
    )
    daily["account_return_after_cost"] = (
        daily["account"]
        .div(daily["account"].shift(1))
        .sub(1.0)
    )
    if len(daily):
        daily.iloc[
            0,
            daily.columns.get_loc("account_return_after_cost"),
        ] = daily.iloc[0]["account"] / initial_capital - 1.0

    daily["benchmark_return"] = daily["bench"]
    daily["excess_return_before_cost"] = (
        daily["return"] - daily["bench"]
    )
    daily["excess_return_after_cost"] = (
        daily["return"] - daily["bench"] - daily["cost"]
    )
    daily["cash_ratio"] = daily["cash"] / daily["account"]
    if "value" in daily.columns:
        daily["stock_value_ratio"] = daily["value"] / daily["account"]

    nav = pd.DataFrame(index=daily.index)
    nav["strategy_nav_after_cost"] = daily["account"] / initial_capital
    nav["strategy_nav_before_cost"] = (
        1.0 + daily["strategy_return_before_cost"].fillna(0.0)
    ).cumprod()
    nav["benchmark_nav"] = (
        1.0 + daily["benchmark_return"].fillna(0.0)
    ).cumprod()
    nav["qlib_excess_nav_after_cost"] = (
        1.0 + daily["excess_return_after_cost"].fillna(0.0)
    ).cumprod()

    nav["strategy_drawdown_after_cost"] = (
        nav["strategy_nav_after_cost"]
        / nav["strategy_nav_after_cost"].cummax()
        - 1.0
    )
    nav["benchmark_drawdown"] = (
        nav["benchmark_nav"]
        / nav["benchmark_nav"].cummax()
        - 1.0
    )

    return daily, nav


def position_payload(position: Any) -> dict[str, Any]:
    payload = getattr(position, "position", None)
    if isinstance(payload, dict):
        return payload
    if isinstance(position, dict):
        return position
    return {}


def flatten_positions(
    positions: dict[Any, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    holding_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for date_value, position in sorted(
        positions.items(),
        key=lambda item: pd.Timestamp(item[0]),
    ):
        date = pd.Timestamp(date_value)
        payload = position_payload(position)

        try:
            stock_list = sorted(position.get_stock_list())
        except Exception:
            stock_list = sorted(
                key
                for key, value in payload.items()
                if key not in {"cash", "cash_delay", "now_account_value"}
                and isinstance(value, dict)
            )

        try:
            account_value = float(position.calculate_value())
        except Exception:
            account_value = safe_float(payload.get("now_account_value"))

        try:
            cash = float(position.get_cash(include_settle=True))
        except Exception:
            cash = (
                safe_float(payload.get("cash")) or 0.0
            ) + (
                safe_float(payload.get("cash_delay")) or 0.0
            )

        stock_value = 0.0

        for symbol in stock_list:
            details = payload.get(symbol, {})
            try:
                amount = float(position.get_stock_amount(symbol))
            except Exception:
                amount = safe_float(details.get("amount"))

            try:
                price = float(position.get_stock_price(symbol))
            except Exception:
                price = safe_float(details.get("price"))

            try:
                weight = float(position.get_stock_weight(symbol))
            except Exception:
                weight = safe_float(details.get("weight"))

            amount = amount if amount is not None else np.nan
            price = price if price is not None else np.nan
            market_value = amount * price

            if math.isfinite(market_value):
                stock_value += market_value

            hold_days = safe_float(details.get("count_day"))

            holding_rows.append(
                {
                    "datetime": date,
                    "instrument": symbol,
                    "amount": amount,
                    "price": price,
                    "market_value": market_value,
                    "weight": weight,
                    "hold_days": hold_days,
                }
            )

        if account_value is None:
            account_value = stock_value + cash

        summary_rows.append(
            {
                "datetime": date,
                "account_value": account_value,
                "cash": cash,
                "stock_value_from_positions": stock_value,
                "cash_ratio": (
                    cash / account_value
                    if account_value not in (None, 0)
                    else np.nan
                ),
                "holding_count": len(stock_list),
            }
        )

    holdings = pd.DataFrame(holding_rows)
    position_summary = pd.DataFrame(summary_rows)

    if not holdings.empty:
        holdings = holdings.sort_values(
            ["datetime", "weight", "instrument"],
            ascending=[True, False, True],
        ).reset_index(drop=True)

    if not position_summary.empty:
        position_summary = position_summary.sort_values(
            "datetime"
        ).reset_index(drop=True)

    return holdings, position_summary


def infer_position_changes(holdings: pd.DataFrame) -> pd.DataFrame:
    """
    根据每日持仓数量变化推断调仓。
    这不是Qlib的逐笔成交记录，价格也是日末持仓参考价。
    """
    columns = [
        "datetime",
        "instrument",
        "change_type",
        "amount_change",
        "reference_price",
        "approximate_value",
    ]
    if holdings.empty:
        return pd.DataFrame(columns=columns)

    amount_matrix = holdings.pivot_table(
        index="datetime",
        columns="instrument",
        values="amount",
        aggfunc="last",
    ).fillna(0.0)

    amount_change = amount_matrix.diff()
    amount_change.iloc[0] = amount_matrix.iloc[0]

    stacked = amount_change.stack()
    stacked = stacked[
        ~np.isclose(stacked.to_numpy(dtype=float), 0.0)
    ]

    price_lookup = (
        holdings.set_index(["datetime", "instrument"])["price"]
        .to_dict()
    )

    rows: list[dict[str, Any]] = []
    for (date, symbol), change in stacked.items():
        price = safe_float(price_lookup.get((date, symbol)))
        rows.append(
            {
                "datetime": pd.Timestamp(date),
                "instrument": symbol,
                "change_type": "BUY" if change > 0 else "SELL",
                "amount_change": float(change),
                "reference_price": price,
                "approximate_value": (
                    abs(float(change)) * price
                    if price is not None
                    else None
                ),
            }
        )

    return pd.DataFrame(rows, columns=columns).sort_values(
        ["datetime", "change_type", "instrument"]
    )


def export_predictions(
    predictions: Any,
    labels: Any,
    output_dir: Path,
) -> dict[str, int]:
    if isinstance(predictions, pd.Series):
        predictions = predictions.to_frame("score")
    if not isinstance(predictions, pd.DataFrame):
        raise TypeError(
            f"pred.pkl应为DataFrame或Series，实际为：{type(predictions)}"
        )

    pred = predictions.copy()
    if "score" not in pred.columns and len(pred.columns) == 1:
        pred.columns = ["score"]

    pred_reset = pred.reset_index()
    required = {"datetime", "instrument", "score"}
    missing = required - set(pred_reset.columns)
    if missing:
        raise ValueError(
            f"预测结果缺少字段：{sorted(missing)}；"
            f"实际字段：{pred_reset.columns.tolist()}"
        )

    pred_reset["datetime"] = pd.to_datetime(
        pred_reset["datetime"]
    )
    pred_reset["rank_desc"] = pred_reset.groupby(
        "datetime"
    )["score"].rank(
        method="first",
        ascending=False,
    )
    pred_reset["score_percentile"] = pred_reset.groupby(
        "datetime"
    )["score"].rank(
        method="average",
        pct=True,
    )

    pred_reset = pred_reset.sort_values(
        ["datetime", "rank_desc"]
    )
    pred_reset.to_csv(
        output_dir / "predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    pred_reset[
        pred_reset["rank_desc"] <= 5
    ].to_csv(
        output_dir / "top5_predictions.csv",
        index=False,
        encoding="utf-8-sig",
    )

    if isinstance(labels, pd.Series):
        labels = labels.to_frame("label")
    if isinstance(labels, pd.DataFrame):
        label_df = labels.copy()
        if len(label_df.columns) == 1:
            label_df.columns = ["label"]
        joined = pred.join(label_df, how="left")
        joined.reset_index().to_csv(
            output_dir / "prediction_with_label.csv",
            index=False,
            encoding="utf-8-sig",
        )

    return {
        "prediction_rows": int(len(pred_reset)),
        "prediction_dates": int(pred_reset["datetime"].nunique()),
        "prediction_instruments": int(
            pred_reset["instrument"].nunique()
        ),
    }


def export_risk_dataframe(
    obj: Any,
    output_path: Path,
) -> None:
    if isinstance(obj, pd.Series):
        obj = obj.to_frame("value")
    if isinstance(obj, pd.DataFrame):
        obj.reset_index().to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig",
        )


def risk_value(
    risk_df: Any,
    section: str,
    metric: str,
) -> float | None:
    if not isinstance(risk_df, pd.DataFrame):
        return None
    if "risk" not in risk_df.columns:
        return None

    try:
        if isinstance(risk_df.index, pd.MultiIndex):
            return safe_float(risk_df.loc[(section, metric), "risk"])
    except Exception:
        pass

    reset = risk_df.reset_index()
    level_columns = [
        column
        for column in reset.columns
        if column != "risk"
    ]
    if len(level_columns) >= 2:
        mask = (
            reset[level_columns[0]].astype(str).eq(section)
            & reset[level_columns[1]].astype(str).eq(metric)
        )
        if mask.any():
            return safe_float(reset.loc[mask, "risk"].iloc[0])

    return None


def read_instrument_symbols() -> list[str]:
    instrument_file = (
        PROVIDER_URI / "instruments" / "csi300.txt"
    )
    if not instrument_file.exists():
        return []

    symbols: list[str] = []
    for line in instrument_file.read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()
        if not line:
            continue
        symbols.append(line.split("\t", 1)[0].upper())

    return sorted(set(symbols))


def audit_missing_close(
    report_index: pd.DatetimeIndex,
    output_dir: Path,
) -> dict[str, Any]:
    symbols = read_instrument_symbols()
    if not symbols or len(report_index) == 0:
        return {
            "audited": False,
            "reason": "股票池或回测日期为空",
        }

    audit_symbols = symbols + ["SH000300"]
    start_time = report_index.min().strftime("%Y-%m-%d")
    end_time = report_index.max().strftime("%Y-%m-%d")

    close_df = D.features(
        audit_symbols,
        ["$close"],
        start_time=start_time,
        end_time=end_time,
    )

    close_series = close_df["$close"]
    close_matrix = close_series.unstack("instrument")
    close_matrix = close_matrix.reindex(
        index=report_index,
        columns=audit_symbols,
    )

    missing_mask = close_matrix.isna()
    missing_long = (
        missing_mask.stack()
        .rename("is_missing")
        .reset_index()
    )
    missing_long = missing_long[
        missing_long["is_missing"]
    ].drop(columns="is_missing")

    missing_long.to_csv(
        output_dir / "missing_close.csv",
        index=False,
        encoding="utf-8-sig",
    )

    by_symbol = (
        missing_long.groupby("instrument")
        .size()
        .rename("missing_days")
        .sort_values(ascending=False)
        .reset_index()
    )
    by_symbol.to_csv(
        output_dir / "missing_close_by_instrument.csv",
        index=False,
        encoding="utf-8-sig",
    )

    return {
        "audited": True,
        "symbol_count_including_benchmark": len(audit_symbols),
        "date_count": len(report_index),
        "missing_cells": int(missing_mask.to_numpy().sum()),
        "symbols_with_missing_close": int(
            (missing_mask.sum(axis=0) > 0).sum()
        ),
    }


def monthly_and_yearly_returns(
    nav: pd.DataFrame,
    output_dir: Path,
) -> None:
    selected = nav[
        [
            "strategy_nav_after_cost",
            "benchmark_nav",
        ]
    ].copy()

    monthly_nav = selected.resample("ME").last()
    monthly_returns = monthly_nav.pct_change()
    if len(monthly_returns):
        # 第一月相对于1.0计算，避免丢掉首月。
        monthly_returns.iloc[0] = monthly_nav.iloc[0] - 1.0
    monthly_returns.index.name = "month"
    monthly_returns.to_csv(
        output_dir / "monthly_returns.csv",
        encoding="utf-8-sig",
    )

    yearly_nav = selected.resample("YE").last()
    yearly_returns = yearly_nav.pct_change()
    if len(yearly_returns):
        yearly_returns.iloc[0] = yearly_nav.iloc[0] - 1.0
    yearly_returns.index.name = "year"
    yearly_returns.to_csv(
        output_dir / "yearly_returns.csv",
        encoding="utf-8-sig",
    )


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()

    if not PROVIDER_URI.exists():
        raise FileNotFoundError(
            f"Qlib数据目录不存在：{PROVIDER_URI}"
        )

    # Qlib默认的MLflow路径是相对当前目录的。
    # 强制回到D:\QuantBuddy，确保读取到qrun创建的mlruns。
    os.chdir(PROJECT_ROOT)

    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("QuantBuddy：导出并审计Qlib回测")
    print("=" * 78)
    print(f"项目目录：{PROJECT_ROOT}")
    print(f"实验名称：{args.experiment}")
    print(f"Recorder ID：{args.recorder_id}")
    print(f"输出目录：{output_dir}")
    print("=" * 78)

    qlib.init(
        provider_uri=str(PROVIDER_URI),
        region=REG_CN,
    )

    recorder = R.get_recorder(
        recorder_id=args.recorder_id,
        experiment_name=args.experiment,
    )

    artifacts = list_artifact_tree(recorder)
    write_json(
        output_dir / "artifact_manifest.json",
        {
            "experiment": args.experiment,
            "recorder_id": args.recorder_id,
            "artifacts": artifacts,
        },
    )

    print("\nRecorder artifacts：")
    for artifact in artifacts:
        print(f"  - {artifact}")

    predictions = safe_load(
        recorder,
        ARTIFACT_NAMES["predictions"],
        required=True,
    )
    labels = safe_load(
        recorder,
        ARTIFACT_NAMES["labels"],
    )
    model = safe_load(
        recorder,
        ARTIFACT_NAMES["model"],
        required=True,
    )
    task = safe_load(
        recorder,
        ARTIFACT_NAMES["task"],
    )
    report = safe_load(
        recorder,
        ARTIFACT_NAMES["daily_report"],
        required=True,
    )
    positions = safe_load(
        recorder,
        ARTIFACT_NAMES["positions"],
        required=True,
    )
    risk_analysis = safe_load(
        recorder,
        ARTIFACT_NAMES["risk_analysis"],
    )
    indicator_analysis = safe_load(
        recorder,
        ARTIFACT_NAMES["indicator_analysis"],
    )
    daily_indicators = safe_load(
        recorder,
        ARTIFACT_NAMES["daily_indicators"],
    )
    ic_series = safe_load(
        recorder,
        ARTIFACT_NAMES["ic"],
    )
    rank_ic_series = safe_load(
        recorder,
        ARTIFACT_NAMES["rank_ic"],
    )

    if not isinstance(report, pd.DataFrame):
        raise TypeError(
            f"report_normal应为DataFrame，实际为：{type(report)}"
        )
    if not isinstance(positions, dict):
        raise TypeError(
            f"positions_normal应为dict，实际为：{type(positions)}"
        )

    initial_capital = extract_initial_capital(task)
    print(f"\n识别到初始资金：{initial_capital:,.2f}")

    prediction_stats = export_predictions(
        predictions,
        labels,
        output_dir,
    )

    daily_report, daily_nav = build_daily_outputs(
        report,
        initial_capital,
    )
    daily_report.to_csv(
        output_dir / "daily_report.csv",
        encoding="utf-8-sig",
    )
    daily_nav.to_csv(
        output_dir / "daily_nav.csv",
        encoding="utf-8-sig",
    )
    monthly_and_yearly_returns(
        daily_nav,
        output_dir,
    )

    # 保存原始持仓对象及可读展开结果。
    with (output_dir / "positions.pkl").open("wb") as file:
        pickle.dump(
            positions,
            file,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    holdings, position_summary = flatten_positions(
        positions
    )
    holdings.to_csv(
        output_dir / "holdings.csv",
        index=False,
        encoding="utf-8-sig",
    )
    position_summary.to_csv(
        output_dir / "position_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    inferred_changes = infer_position_changes(holdings)
    inferred_changes.to_csv(
        output_dir / "inferred_position_changes.csv",
        index=False,
        encoding="utf-8-sig",
    )

    # qrun在Qlib 0.9.7中把模型保存为params.pkl。
    # 对外复制成更直观的文件名，不修改Recorder中的原始artifact。
    with (output_dir / "trained_model.pkl").open("wb") as file:
        pickle.dump(
            model,
            file,
            protocol=pickle.HIGHEST_PROTOCOL,
        )

    if task is not None:
        with (output_dir / "task_config.pkl").open("wb") as file:
            pickle.dump(
                task,
                file,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        write_json(
            output_dir / "task_config.json",
            task,
        )

    export_risk_dataframe(
        risk_analysis,
        output_dir / "risk_analysis.csv",
    )
    export_risk_dataframe(
        indicator_analysis,
        output_dir / "indicator_analysis.csv",
    )
    export_risk_dataframe(
        daily_indicators,
        output_dir / "daily_indicators.csv",
    )
    export_risk_dataframe(
        ic_series,
        output_dir / "daily_ic.csv",
    )
    export_risk_dataframe(
        rank_ic_series,
        output_dir / "daily_rank_ic.csv",
    )

    try:
        recorder_metrics = recorder.list_metrics()
    except Exception as exc:
        print(
            f"读取Recorder metrics失败："
            f"{type(exc).__name__}: {exc}"
        )
        recorder_metrics = {}

    write_json(
        output_dir / "recorder_metrics.json",
        recorder_metrics,
    )

    if args.skip_close_audit:
        close_audit = {
            "audited": False,
            "reason": "用户指定--skip-close-audit",
        }
    else:
        print("\n检查回测区间内的$close缺失……")
        try:
            close_audit = audit_missing_close(
                pd.DatetimeIndex(daily_report.index),
                output_dir,
            )
        except Exception as exc:
            close_audit = {
                "audited": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
            print(
                f"close审计未完成："
                f"{close_audit['reason']}"
            )

    strategy_performance = calculate_performance(
        daily_nav["strategy_nav_after_cost"],
        daily_report["account_return_after_cost"],
    )
    benchmark_performance = calculate_performance(
        daily_nav["benchmark_nav"],
        daily_report["benchmark_return"],
    )

    holding_count_stats: dict[str, Any] = {}
    if not position_summary.empty:
        holding_count_stats = {
            "average_holding_count": safe_float(
                position_summary["holding_count"].mean()
            ),
            "minimum_holding_count": safe_float(
                position_summary["holding_count"].min()
            ),
            "maximum_holding_count": safe_float(
                position_summary["holding_count"].max()
            ),
            "average_cash_ratio": safe_float(
                position_summary["cash_ratio"].mean()
            ),
            "maximum_cash_ratio": safe_float(
                position_summary["cash_ratio"].max()
            ),
        }

    summary = {
        "metadata": {
            "project": "QuantBuddy",
            "experiment": args.experiment,
            "recorder_id": args.recorder_id,
            "provider_uri": str(PROVIDER_URI),
            "output_dir": str(output_dir),
            "initial_capital": initial_capital,
            "backtest_start": (
                daily_report.index.min().strftime("%Y-%m-%d")
                if len(daily_report)
                else None
            ),
            "backtest_end": (
                daily_report.index.max().strftime("%Y-%m-%d")
                if len(daily_report)
                else None
            ),
            "trading_days": int(len(daily_report)),
        },
        "predictions": prediction_stats,
        "signal_metrics": {
            "IC": safe_float(recorder_metrics.get("IC")),
            "ICIR": safe_float(recorder_metrics.get("ICIR")),
            "Rank IC": safe_float(
                recorder_metrics.get("Rank IC")
            ),
            "Rank ICIR": safe_float(
                recorder_metrics.get("Rank ICIR")
            ),
        },
        "strategy_after_cost": strategy_performance,
        "benchmark": benchmark_performance,
        "qlib_excess_analysis": {
            "annualized_return_after_cost": risk_value(
                risk_analysis,
                "excess_return_with_cost",
                "annualized_return",
            ),
            "information_ratio_after_cost": risk_value(
                risk_analysis,
                "excess_return_with_cost",
                "information_ratio",
            ),
            "max_drawdown_after_cost": risk_value(
                risk_analysis,
                "excess_return_with_cost",
                "max_drawdown",
            ),
            "annualized_return_before_cost": risk_value(
                risk_analysis,
                "excess_return_without_cost",
                "annualized_return",
            ),
        },
        "trading": {
            "average_daily_turnover_rate": safe_float(
                daily_report["turnover"].mean()
            ),
            "median_daily_turnover_rate": safe_float(
                daily_report["turnover"].median()
            ),
            "cumulative_turnover_currency": safe_float(
                daily_report["total_turnover"].iloc[-1]
            )
            if "total_turnover" in daily_report.columns
            and len(daily_report)
            else None,
            "cumulative_cost_currency": safe_float(
                daily_report["total_cost"].iloc[-1]
            )
            if "total_cost" in daily_report.columns
            and len(daily_report)
            else None,
            "average_daily_cost_rate": safe_float(
                daily_report["cost"].mean()
            ),
            "inferred_position_change_rows": int(
                len(inferred_changes)
            ),
            **holding_count_stats,
        },
        "data_quality": {
            "report_nan_counts": {
                column: int(value)
                for column, value in daily_report.isna().sum().items()
                if int(value) > 0
            },
            "holdings_with_nan_price": (
                int(holdings["price"].isna().sum())
                if not holdings.empty
                else 0
            ),
            "close_audit": close_audit,
        },
        "important_notes": [
            "股票池是当前沪深300固定成分股，历史回测存在幸存者偏差。",
            "Qlib的report.return为成本前收益；策略成本后净值以report.account/初始资金计算。",
            "inferred_position_changes.csv由每日持仓差分推断，不是逐笔成交回报。",
            "当前回测成交价为close，与最终T日收盘信号、T+1执行方案仍需进一步对齐。",
        ],
    }

    write_json(
        output_dir / "summary.json",
        summary,
    )

    print("\n" + "=" * 78)
    print("导出完成")
    print("=" * 78)
    print(f"输出目录：{output_dir}")
    print(f"预测记录：{prediction_stats['prediction_rows']:,}")
    print(f"回测交易日：{len(daily_report):,}")
    print(f"持仓明细：{len(holdings):,}")
    print(f"推断调仓记录：{len(inferred_changes):,}")
    print(
        "策略成本后总收益："
        f"{strategy_performance['total_return']:.2%}"
        if strategy_performance["total_return"] is not None
        else "策略成本后总收益：无法计算"
    )
    print(
        "策略成本后CAGR："
        f"{strategy_performance['cagr']:.2%}"
        if strategy_performance["cagr"] is not None
        else "策略成本后CAGR：无法计算"
    )
    print(
        "策略成本后最大回撤："
        f"{strategy_performance['max_drawdown']:.2%}"
        if strategy_performance["max_drawdown"] is not None
        else "策略成本后最大回撤：无法计算"
    )
    print("\n核心文件：")
    for name in [
        "summary.json",
        "daily_nav.csv",
        "daily_report.csv",
        "predictions.csv",
        "top5_predictions.csv",
        "holdings.csv",
        "position_summary.csv",
        "inferred_position_changes.csv",
        "risk_analysis.csv",
        "trained_model.pkl",
    ]:
        path = output_dir / name
        status = "已生成" if path.exists() else "未生成"
        print(f"  [{status}] {name}")
    print("=" * 78)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\n" + "=" * 78, file=sys.stderr)
        print("导出失败", file=sys.stderr)
        print(
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print("=" * 78, file=sys.stderr)
        raise
