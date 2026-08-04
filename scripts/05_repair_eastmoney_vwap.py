from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPORT_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "normalized_csi300_report.csv"
)
EM_RAW_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "unadjusted"
)
EM_HFQ_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "hfq"
)
OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "normalized" / "qlib_csv"
)
REPAIR_REPORT_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "eastmoney_vwap_repair_report.csv"
)


def load_em(path: Path) -> pd.DataFrame:
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
            "成交量": "raw_volume",
            "成交额": "amount",
        }
    )[
        [
            "date",
            "open",
            "close",
            "high",
            "low",
            "raw_volume",
            "amount",
        ]
    ].copy()

    result["date"] = pd.to_datetime(result["date"], errors="coerce")

    for column in [
        "open",
        "close",
        "high",
        "low",
        "raw_volume",
        "amount",
    ]:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    if result.isna().any().any():
        bad = result.isna().sum()
        bad = bad[bad > 0].to_dict()
        raise ValueError(f"{path.name} 存在无效字段：{bad}")

    return (
        result.sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def median_log_error(candidate: pd.Series, close: pd.Series) -> float:
    valid = (
        np.isfinite(candidate)
        & np.isfinite(close)
        & (candidate > 0)
        & (close > 0)
    )

    if not valid.any():
        return float("inf")

    return float(
        np.median(
            np.abs(
                np.log(
                    candidate[valid].to_numpy()
                    / close[valid].to_numpy()
                )
            )
        )
    )


def infer_volume_multiplier(raw: pd.DataFrame) -> tuple[float, float, float]:
    """
    东方财富历史行情中的成交量通常以“手”为单位。
    这里不盲目写死，而是通过成交额/成交量与收盘价的接近程度，
    在“股”和“手×100”两种口径中自动选择。
    """
    volume = raw["raw_volume"].astype(float)
    amount = raw["amount"].astype(float)
    close = raw["close"].astype(float)

    candidate_if_shares = amount / volume.replace(0, np.nan)
    candidate_if_hands = amount / (volume * 100.0).replace(0, np.nan)

    error_shares = median_log_error(candidate_if_shares, close)
    error_hands = median_log_error(candidate_if_hands, close)

    multiplier = 100.0 if error_hands < error_shares else 1.0
    return multiplier, error_shares, error_hands


def repair_one(symbol: str) -> dict:
    raw_file = EM_RAW_DIR / f"{symbol}.csv"
    hfq_file = EM_HFQ_DIR / f"{symbol}.csv"

    if not raw_file.exists() or not hfq_file.exists():
        raise FileNotFoundError(f"{symbol} 缺少东方财富原始文件对")

    raw = load_em(raw_file)
    hfq = load_em(hfq_file)

    multiplier, error_shares, error_hands = infer_volume_multiplier(raw)

    merged = raw.merge(
        hfq[["date", "close"]].rename(
            columns={"close": "hfq_close"}
        ),
        on="date",
        how="inner",
        validate="one_to_one",
    )

    if merged.empty:
        raise ValueError(f"{symbol} 不复权与后复权没有共同日期")

    first_hfq_close = float(merged.iloc[0]["hfq_close"])
    factor = (
        merged["hfq_close"] / merged["close"]
    ) / first_hfq_close

    volume_shares = merged["raw_volume"] * multiplier

    raw_vwap = np.where(
        volume_shares > 0,
        merged["amount"] / volume_shares,
        np.nan,
    )

    output = pd.DataFrame(
        {
            "date": merged["date"].dt.strftime("%Y-%m-%d"),
            "open": merged["open"] * factor,
            "high": merged["high"] * factor,
            "low": merged["low"] * factor,
            "close": merged["close"] * factor,
            "volume": volume_shares / factor,
            "factor": factor,
            "vwap": raw_vwap * factor,
        }
    )

    output = output.replace([np.inf, -np.inf], np.nan)

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "factor",
    ]
    if output[required].isna().any().any():
        bad = output[required].isna().sum()
        bad = bad[bad > 0].to_dict()
        raise ValueError(f"{symbol} 修复后存在无效值：{bad}")

    ratio = output["vwap"] / output["close"]
    valid_ratio = ratio[np.isfinite(ratio) & (ratio > 0)]

    if valid_ratio.empty:
        raise ValueError(f"{symbol} 无法得到有效VWAP")

    median_ratio = float(valid_ratio.median())

    # 日均成交价通常应与当天收盘价处在相同数量级。
    if not 0.5 <= median_ratio <= 2.0:
        raise ValueError(
            f"{symbol} 修复后VWAP/close中位数仍异常："
            f"{median_ratio:.6f}"
        )

    destination = OUTPUT_DIR / f"{symbol}.csv"
    temporary = destination.with_suffix(".csv.tmp")

    output.to_csv(
        temporary,
        index=False,
        encoding="utf-8",
    )
    temporary.replace(destination)

    return {
        "symbol": symbol,
        "volume_multiplier": multiplier,
        "error_assuming_shares": error_shares,
        "error_assuming_hands": error_hands,
        "median_vwap_close_ratio": median_ratio,
        "rows": len(output),
        "first_date": output.iloc[0]["date"],
        "last_date": output.iloc[-1]["date"],
        "status": "success",
        "error": "",
    }


def main() -> None:
    if not REPORT_FILE.exists():
        raise FileNotFoundError(f"找不到质量报告：{REPORT_FILE}")

    report = pd.read_csv(REPORT_FILE)
    required = {"symbol", "source", "status"}
    missing = required - set(report.columns)
    if missing:
        raise ValueError(
            f"质量报告缺少字段：{sorted(missing)}"
        )

    symbols = (
        report.loc[
            (report["source"] == "eastmoney")
            & (report["status"] == "success"),
            "symbol",
        ]
        .astype(str)
        .tolist()
    )

    if not symbols:
        raise RuntimeError("质量报告中没有找到东方财富股票")

    print("=" * 72)
    print("修复东方财富股票的成交量单位与VWAP")
    print("=" * 72)
    print(f"待处理股票：{len(symbols)}")

    records: list[dict] = []
    success_count = 0
    failure_count = 0

    for index, symbol in enumerate(symbols, start=1):
        print(f"[{index}/{len(symbols)}] {symbol}", end=" ")

        try:
            record = repair_one(symbol)
            records.append(record)
            success_count += 1

            print(
                "成功 "
                f"volume×{record['volume_multiplier']:.0f} "
                f"median(VWAP/close)="
                f"{record['median_vwap_close_ratio']:.6f}"
            )

        except Exception as exc:
            failure_count += 1
            records.append(
                {
                    "symbol": symbol,
                    "volume_multiplier": "",
                    "error_assuming_shares": "",
                    "error_assuming_hands": "",
                    "median_vwap_close_ratio": "",
                    "rows": "",
                    "first_date": "",
                    "last_date": "",
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            print(f"失败：{type(exc).__name__}: {exc}")

    pd.DataFrame(records).to_csv(
        REPAIR_REPORT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 72)
    print("修复任务结束")
    print(f"成功：{success_count}")
    print(f"失败：{failure_count}")
    print(f"修复报告：{REPAIR_REPORT_FILE}")
    print("=" * 72)

    if failure_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
