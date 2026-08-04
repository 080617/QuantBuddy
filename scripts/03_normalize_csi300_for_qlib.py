from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONSTITUENTS_FILE = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "csi300_current.csv"
)

EM_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "akshare" / "unadjusted"
EM_HFQ_DIR = PROJECT_ROOT / "data" / "raw" / "akshare" / "hfq"

TX_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "akshare_tx" / "unadjusted"
TX_HFQ_DIR = PROJECT_ROOT / "data" / "raw" / "akshare_tx" / "hfq"

OUTPUT_DIR = PROJECT_ROOT / "data" / "normalized" / "qlib_csv"
REPORT_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "normalized_csi300_report.csv"
)

OUTPUT_COLUMNS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "factor",
    "vwap",
]


def to_qlib_symbol(code: str, exchange: str) -> str:
    code = str(code).zfill(6)
    exchange = str(exchange)

    if "上海" in exchange:
        return f"SH{code}"
    if "深圳" in exchange:
        return f"SZ{code}"

    raise ValueError(f"无法识别交易所：code={code}, exchange={exchange}")


def pair_exists(raw_dir: Path, hfq_dir: Path, symbol: str) -> bool:
    raw_file = raw_dir / f"{symbol}.csv"
    hfq_file = hfq_dir / f"{symbol}.csv"
    return (
        raw_file.exists()
        and raw_file.stat().st_size > 0
        and hfq_file.exists()
        and hfq_file.stat().st_size > 0
    )


def select_source(symbol: str) -> tuple[str, Path, Path]:
    if pair_exists(TX_RAW_DIR, TX_HFQ_DIR, symbol):
        return "tencent", TX_RAW_DIR, TX_HFQ_DIR

    if pair_exists(EM_RAW_DIR, EM_HFQ_DIR, symbol):
        return "eastmoney", EM_RAW_DIR, EM_HFQ_DIR

    raise FileNotFoundError(f"{symbol} 缺少完整的不复权/后复权文件对")


def load_eastmoney(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")

    required = {
        "日期",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} 缺少字段：{sorted(missing)}")

    result = df.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
    )[
        ["date", "open", "close", "high", "low", "volume", "amount"]
    ].copy()

    result["date"] = pd.to_datetime(result["date"], errors="coerce")

    for column in ["open", "close", "high", "low", "volume", "amount"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result["volume"] = result["volume"] * 100.0

    return result


def load_tencent(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")

    required = {
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} 缺少字段：{sorted(missing)}")

    result = df[
        ["date", "open", "close", "high", "low", "volume", "amount"]
    ].copy()

    result["date"] = pd.to_datetime(result["date"], errors="coerce")

    for column in ["open", "close", "high", "low", "volume", "amount"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    return result


def load_source_file(source: str, path: Path) -> pd.DataFrame:
    if source == "eastmoney":
        return load_eastmoney(path)
    if source == "tencent":
        return load_tencent(path)

    raise ValueError(f"未知来源：{source}")


def validate_base_frame(df: pd.DataFrame, symbol: str, label: str) -> None:
    if df.empty:
        raise ValueError(f"{symbol} {label} 数据为空")

    if df["date"].isna().any():
        raise ValueError(f"{symbol} {label} 存在无效日期")

    numeric_columns = ["open", "close", "high", "low", "volume", "amount"]
    if df[numeric_columns].isna().any().any():
        bad = df[numeric_columns].isna().sum()
        bad = bad[bad > 0].to_dict()
        raise ValueError(f"{symbol} {label} 存在无效数值：{bad}")

    if df["date"].duplicated().any():
        raise ValueError(f"{symbol} {label} 存在重复日期")

    if (df[["open", "close", "high", "low"]] <= 0).any().any():
        raise ValueError(f"{symbol} {label} 存在非正价格")

    if (df[["volume", "amount"]] < 0).any().any():
        raise ValueError(f"{symbol} {label} 存在负成交量或成交额")


def normalize_one_stock(
    symbol: str,
    source: str,
    raw_file: Path,
    hfq_file: Path,
) -> tuple[pd.DataFrame, dict]:
    raw = load_source_file(source, raw_file)
    hfq = load_source_file(source, hfq_file)

    validate_base_frame(raw, symbol, "unadjusted")
    validate_base_frame(hfq, symbol, "hfq")

    raw = raw.sort_values("date").drop_duplicates("date", keep="last")
    hfq = hfq.sort_values("date").drop_duplicates("date", keep="last")

    merged = raw.merge(
        hfq[["date", "close"]].rename(columns={"close": "hfq_close"}),
        on="date",
        how="inner",
        validate="one_to_one",
    )

    if merged.empty:
        raise ValueError(f"{symbol} 不复权与后复权没有共同日期")

    first_hfq_close = float(merged.iloc[0]["hfq_close"])
    if not np.isfinite(first_hfq_close) or first_hfq_close <= 0:
        raise ValueError(f"{symbol} 首个后复权收盘价无效")

    corporate_ratio = merged["hfq_close"] / merged["close"]
    factor = corporate_ratio / first_hfq_close

    if (~np.isfinite(factor)).any() or (factor <= 0).any():
        raise ValueError(f"{symbol} factor存在无效值")

    volume_shares = merged["volume"].astype(float)
    raw_vwap = np.where(
        volume_shares > 0,
        merged["amount"].astype(float) / volume_shares,
        np.nan,
    )

    output = pd.DataFrame(
        {
            "date": merged["date"].dt.strftime("%Y-%m-%d"),
            "open": merged["open"] * factor,
            "high": merged["high"] * factor,
            "low": merged["low"] * factor,
            "close": merged["close"] * factor,
            "volume": np.where(
                factor > 0,
                volume_shares / factor,
                np.nan,
            ),
            "factor": factor,
            "vwap": raw_vwap * factor,
        }
    )

    output = output.replace([np.inf, -np.inf], np.nan)

    required_no_nan = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "factor",
    ]
    if output[required_no_nan].isna().any().any():
        bad = output[required_no_nan].isna().sum()
        bad = bad[bad > 0].to_dict()
        raise ValueError(f"{symbol} 标准化后存在缺失：{bad}")

    if not np.isclose(float(output.iloc[0]["close"]), 1.0, atol=1e-6):
        raise ValueError(
            f"{symbol} 首日调整后close未归一化为1："
            f"{output.iloc[0]['close']}"
        )

    output = output[OUTPUT_COLUMNS]

    report = {
        "symbol": symbol,
        "source": source,
        "raw_rows": len(raw),
        "hfq_rows": len(hfq),
        "common_rows": len(merged),
        "raw_only_dates": len(set(raw["date"]) - set(hfq["date"])),
        "hfq_only_dates": len(set(hfq["date"]) - set(raw["date"])),
        "first_date": output.iloc[0]["date"],
        "last_date": output.iloc[-1]["date"],
        "first_adjusted_close": float(output.iloc[0]["close"]),
        "last_adjusted_close": float(output.iloc[-1]["close"]),
        "factor_min": float(output["factor"].min()),
        "factor_max": float(output["factor"].max()),
        "zero_volume_rows": int((volume_shares == 0).sum()),
        "vwap_missing_rows": int(output["vwap"].isna().sum()),
        "status": "success",
        "error": "",
    }

    return output, report


def main() -> None:
    if not CONSTITUENTS_FILE.exists():
        raise FileNotFoundError(f"找不到成分股文件：{CONSTITUENTS_FILE}")

    constituents = pd.read_csv(
        CONSTITUENTS_FILE,
        dtype={"成分券代码": str, "交易所": str},
    )

    constituents["成分券代码"] = (
        constituents["成分券代码"].astype(str).str.zfill(6)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)

    reports: list[dict] = []
    success_count = 0
    failure_count = 0

    print("=" * 72)
    print("沪深300 原始数据统一与Qlib CSV标准化")
    print("=" * 72)

    for index, row in constituents.iterrows():
        symbol = to_qlib_symbol(
            row["成分券代码"],
            row["交易所"],
        )

        print(f"[{index + 1}/{len(constituents)}] {symbol}", end=" ")

        try:
            source, raw_dir, hfq_dir = select_source(symbol)

            output, report = normalize_one_stock(
                symbol=symbol,
                source=source,
                raw_file=raw_dir / f"{symbol}.csv",
                hfq_file=hfq_dir / f"{symbol}.csv",
            )

            destination = OUTPUT_DIR / f"{symbol}.csv"
            temporary = destination.with_suffix(".csv.tmp")

            output.to_csv(
                temporary,
                index=False,
                encoding="utf-8",
            )
            temporary.replace(destination)

            reports.append(report)
            success_count += 1

            print(
                f"成功 source={source} rows={len(output)} "
                f"{report['first_date']}→{report['last_date']}"
            )

        except Exception as exc:
            failure_count += 1
            reports.append(
                {
                    "symbol": symbol,
                    "source": "",
                    "raw_rows": "",
                    "hfq_rows": "",
                    "common_rows": "",
                    "raw_only_dates": "",
                    "hfq_only_dates": "",
                    "first_date": "",
                    "last_date": "",
                    "first_adjusted_close": "",
                    "last_adjusted_close": "",
                    "factor_min": "",
                    "factor_max": "",
                    "zero_volume_rows": "",
                    "vwap_missing_rows": "",
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"失败：{type(exc).__name__}: {exc}")

    report_df = pd.DataFrame(reports)
    report_df.to_csv(
        REPORT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 72)
    print("标准化结束")
    print(f"成功：{success_count}")
    print(f"失败：{failure_count}")
    print(f"输出目录：{OUTPUT_DIR}")
    print(f"质量报告：{REPORT_FILE}")
    print("=" * 72)

    if failure_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
