from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONSTITUENTS_FILE = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "csi300_current.csv"
)
OLD_REPORT_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "normalized_csi300_report.csv"
)

EM_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "akshare" / "unadjusted"
EM_HFQ_DIR = PROJECT_ROOT / "data" / "raw" / "akshare" / "hfq"

TX_RAW_DIR = PROJECT_ROOT / "data" / "raw" / "akshare_tx" / "unadjusted"
TX_HFQ_DIR = PROJECT_ROOT / "data" / "raw" / "akshare_tx" / "hfq"

OUTPUT_DIR = PROJECT_ROOT / "data" / "normalized" / "qlib_csv"
REPORT_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "normalized_csi300_report_v2.csv"
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


def load_old_source_map() -> dict[str, str]:
    if not OLD_REPORT_FILE.exists():
        return {}

    report = pd.read_csv(OLD_REPORT_FILE)
    if not {"symbol", "source"}.issubset(report.columns):
        return {}

    return {
        str(row["symbol"]): str(row["source"])
        for _, row in report.iterrows()
        if str(row["source"]) in {"eastmoney", "tencent"}
    }


def select_source(
    symbol: str,
    old_source_map: dict[str, str],
) -> tuple[str, Path, Path]:
    preferred = old_source_map.get(symbol)

    if preferred == "tencent" and pair_exists(
        TX_RAW_DIR, TX_HFQ_DIR, symbol
    ):
        return "tencent", TX_RAW_DIR, TX_HFQ_DIR

    if preferred == "eastmoney" and pair_exists(
        EM_RAW_DIR, EM_HFQ_DIR, symbol
    ):
        return "eastmoney", EM_RAW_DIR, EM_HFQ_DIR

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

    return parse_frame(result, path.name)


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
        raise ValueError(
            f"{path.name} 缺少字段：{sorted(missing)}；"
            f"实际字段：{df.columns.tolist()}"
        )

    result = df.rename(
        columns={"volume": "raw_volume"}
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

    return parse_frame(result, path.name)


def parse_frame(df: pd.DataFrame, file_name: str) -> pd.DataFrame:
    result = df.copy()
    result["date"] = pd.to_datetime(
        result["date"],
        errors="coerce",
    )

    numeric_columns = [
        "open",
        "close",
        "high",
        "low",
        "raw_volume",
        "amount",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    if result[["date", *numeric_columns]].isna().any().any():
        bad = result[["date", *numeric_columns]].isna().sum()
        bad = bad[bad > 0].to_dict()
        raise ValueError(f"{file_name} 存在无效字段：{bad}")

    if result["date"].duplicated().any():
        raise ValueError(f"{file_name} 存在重复日期")

    if (result[["open", "close", "high", "low"]] <= 0).any().any():
        raise ValueError(f"{file_name} 存在非正价格")

    if (result[["raw_volume", "amount"]] < 0).any().any():
        raise ValueError(f"{file_name} 存在负成交量或成交额")

    return result.sort_values("date").reset_index(drop=True)


def load_source_file(source: str, path: Path) -> pd.DataFrame:
    if source == "eastmoney":
        return load_eastmoney(path)
    if source == "tencent":
        return load_tencent(path)

    raise ValueError(f"未知来源：{source}")


def median_log_error(
    candidate_vwap: pd.Series,
    close: pd.Series,
) -> float:
    valid = (
        np.isfinite(candidate_vwap)
        & np.isfinite(close)
        & (candidate_vwap > 0)
        & (close > 0)
    )

    if not valid.any():
        return float("inf")

    ratio = (
        candidate_vwap[valid].to_numpy()
        / close[valid].to_numpy()
    )

    return float(np.median(np.abs(np.log(ratio))))


def infer_volume_multiplier(
    raw: pd.DataFrame,
) -> tuple[float, float, float]:
    """
    自动判断 raw_volume 的单位：
    - multiplier=1：原字段已经是“股”
    - multiplier=100：原字段是“手”，需乘100转换成“股”

    判断依据：成交额 / 成交股数 应与当天股价处于同一数量级。
    """
    volume = raw["raw_volume"].astype(float)
    amount = raw["amount"].astype(float)
    close = raw["close"].astype(float)

    nonzero_volume = volume.replace(0, np.nan)

    vwap_if_shares = amount / nonzero_volume
    vwap_if_hands = amount / (nonzero_volume * 100.0)

    error_if_shares = median_log_error(vwap_if_shares, close)
    error_if_hands = median_log_error(vwap_if_hands, close)

    multiplier = (
        100.0
        if error_if_hands < error_if_shares
        else 1.0
    )

    return multiplier, error_if_shares, error_if_hands


def normalize_one_stock(
    symbol: str,
    source: str,
    raw_file: Path,
    hfq_file: Path,
) -> tuple[pd.DataFrame, dict]:
    raw = load_source_file(source, raw_file)
    hfq = load_source_file(source, hfq_file)

    multiplier, error_shares, error_hands = (
        infer_volume_multiplier(raw)
    )

    merged = raw.merge(
        hfq[["date", "close"]].rename(
            columns={"close": "hfq_close"}
        ),
        on="date",
        how="inner",
        validate="one_to_one",
    )

    if merged.empty:
        raise ValueError(
            f"{symbol} 不复权与后复权没有共同日期"
        )

    first_hfq_close = float(
        merged.iloc[0]["hfq_close"]
    )

    if (
        not np.isfinite(first_hfq_close)
        or first_hfq_close <= 0
    ):
        raise ValueError(
            f"{symbol} 首个后复权收盘价无效"
        )

    factor = (
        merged["hfq_close"] / merged["close"]
    ) / first_hfq_close

    if (
        (~np.isfinite(factor)).any()
        or (factor <= 0).any()
    ):
        raise ValueError(
            f"{symbol} factor存在无效值"
        )

    volume_shares = (
        merged["raw_volume"].astype(float)
        * multiplier
    )

    raw_vwap = np.where(
        volume_shares > 0,
        merged["amount"].astype(float)
        / volume_shares,
        np.nan,
    )

    output = pd.DataFrame(
        {
            "date": merged["date"].dt.strftime(
                "%Y-%m-%d"
            ),
            "open": merged["open"] * factor,
            "high": merged["high"] * factor,
            "low": merged["low"] * factor,
            "close": merged["close"] * factor,
            "volume": volume_shares / factor,
            "factor": factor,
            "vwap": raw_vwap * factor,
        }
    )

    output = output.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    required_no_nan = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "factor",
    ]

    if output[required_no_nan].isna().any().any():
        bad = (
            output[required_no_nan]
            .isna()
            .sum()
        )
        bad = bad[bad > 0].to_dict()
        raise ValueError(
            f"{symbol} 标准化后存在缺失：{bad}"
        )

    ratio = output["vwap"] / output["close"]
    valid_ratio = ratio[
        np.isfinite(ratio)
        & (ratio > 0)
    ]

    if valid_ratio.empty:
        raise ValueError(
            f"{symbol} 无法得到有效VWAP"
        )

    median_ratio = float(valid_ratio.median())

    if not 0.5 <= median_ratio <= 2.0:
        raise ValueError(
            f"{symbol} VWAP/close中位数异常："
            f"{median_ratio:.6f}"
        )

    output = output[OUTPUT_COLUMNS]

    report = {
        "symbol": symbol,
        "source": source,
        "volume_multiplier": multiplier,
        "error_assuming_shares": error_shares,
        "error_assuming_hands": error_hands,
        "raw_rows": len(raw),
        "hfq_rows": len(hfq),
        "common_rows": len(merged),
        "first_date": output.iloc[0]["date"],
        "last_date": output.iloc[-1]["date"],
        "median_vwap_close_ratio": median_ratio,
        "factor_min": float(
            output["factor"].min()
        ),
        "factor_max": float(
            output["factor"].max()
        ),
        "status": "success",
        "error": "",
    }

    return output, report


def main() -> None:
    if not CONSTITUENTS_FILE.exists():
        raise FileNotFoundError(
            f"找不到成分股文件："
            f"{CONSTITUENTS_FILE}"
        )

    constituents = pd.read_csv(
        CONSTITUENTS_FILE,
        dtype={
            "成分券代码": str,
            "交易所": str,
        },
    )

    constituents["成分券代码"] = (
        constituents["成分券代码"]
        .astype(str)
        .str.zfill(6)
    )

    old_source_map = load_old_source_map()

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    REPORT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    reports: list[dict] = []
    success_count = 0
    failure_count = 0
    multiplier_1_count = 0
    multiplier_100_count = 0

    print("=" * 72)
    print("沪深300 Qlib标准化 V2：自动识别成交量单位")
    print("=" * 72)

    for index, row in constituents.iterrows():
        symbol = to_qlib_symbol(
            row["成分券代码"],
            row["交易所"],
        )

        print(
            f"[{index + 1}/{len(constituents)}] "
            f"{symbol}",
            end=" ",
        )

        try:
            source, raw_dir, hfq_dir = (
                select_source(
                    symbol,
                    old_source_map,
                )
            )

            output, report = normalize_one_stock(
                symbol=symbol,
                source=source,
                raw_file=(
                    raw_dir / f"{symbol}.csv"
                ),
                hfq_file=(
                    hfq_dir / f"{symbol}.csv"
                ),
            )

            destination = (
                OUTPUT_DIR / f"{symbol}.csv"
            )
            temporary = destination.with_suffix(
                ".csv.tmp"
            )

            output.to_csv(
                temporary,
                index=False,
                encoding="utf-8",
            )
            temporary.replace(destination)

            reports.append(report)
            success_count += 1

            if report["volume_multiplier"] == 100:
                multiplier_100_count += 1
            else:
                multiplier_1_count += 1

            print(
                f"成功 source={source} "
                f"volume×"
                f"{report['volume_multiplier']:.0f} "
                f"median(VWAP/close)="
                f"{report['median_vwap_close_ratio']:.6f}"
            )

        except Exception as exc:
            failure_count += 1

            reports.append(
                {
                    "symbol": symbol,
                    "source": "",
                    "volume_multiplier": "",
                    "error_assuming_shares": "",
                    "error_assuming_hands": "",
                    "raw_rows": "",
                    "hfq_rows": "",
                    "common_rows": "",
                    "first_date": "",
                    "last_date": "",
                    "median_vwap_close_ratio": "",
                    "factor_min": "",
                    "factor_max": "",
                    "status": "failed",
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

            print(
                f"失败："
                f"{type(exc).__name__}: {exc}"
            )

    pd.DataFrame(reports).to_csv(
        REPORT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n" + "=" * 72)
    print("V2标准化结束")
    print(f"成功：{success_count}")
    print(f"失败：{failure_count}")
    print(f"判定为股（×1）：{multiplier_1_count}")
    print(f"判定为手（×100）：{multiplier_100_count}")
    print(f"输出目录：{OUTPUT_DIR}")
    print(f"质量报告：{REPORT_FILE}")
    print("=" * 72)

    if failure_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
