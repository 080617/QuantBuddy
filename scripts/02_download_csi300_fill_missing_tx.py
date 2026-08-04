from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import akshare as ak
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONSTITUENTS_FILE = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "csi300_current.csv"
)

# 之前东方财富接口已经成功下载的文件
OLD_UNADJUSTED_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "unadjusted"
)
OLD_HFQ_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "hfq"
)

# 之后通过腾讯接口补下载的文件
TX_UNADJUSTED_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare_tx" / "unadjusted"
)
TX_HFQ_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare_tx" / "hfq"
)

MANIFEST_FILE = (
    PROJECT_ROOT
    / "data"
    / "metadata"
    / "akshare_fill_missing_manifest.csv"
)

START_DATE = "20150101"
MAX_RETRIES = 5
REQUEST_DELAY_SECONDS = 1.2
STOCK_DELAY_SECONDS = 1.5
MAX_CONSECUTIVE_NETWORK_FAILURES = 5

TX_REQUIRED_COLUMNS = {
    "date",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
}

OLD_REQUIRED_COLUMNS = {
    "日期",
    "开盘",
    "收盘",
    "最高",
    "最低",
    "成交量",
    "成交额",
}


def to_symbols(code: str, exchange: str) -> tuple[str, str]:
    code = str(code).zfill(6)
    exchange = str(exchange)

    if "上海" in exchange:
        return f"sh{code}", f"SH{code}"
    if "深圳" in exchange:
        return f"sz{code}", f"SZ{code}"

    raise ValueError(f"无法识别交易所：code={code}, exchange={exchange}")


def csv_is_valid(path: Path, required_columns: set[str]) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False

    try:
        sample = pd.read_csv(path, nrows=5)
    except Exception:
        return False

    return required_columns.issubset(sample.columns)


def old_pair_is_valid(qlib_symbol: str) -> bool:
    return (
        csv_is_valid(
            OLD_UNADJUSTED_DIR / f"{qlib_symbol}.csv",
            OLD_REQUIRED_COLUMNS,
        )
        and csv_is_valid(
            OLD_HFQ_DIR / f"{qlib_symbol}.csv",
            OLD_REQUIRED_COLUMNS,
        )
    )


def tx_pair_is_valid(qlib_symbol: str) -> bool:
    return (
        csv_is_valid(
            TX_UNADJUSTED_DIR / f"{qlib_symbol}.csv",
            TX_REQUIRED_COLUMNS,
        )
        and csv_is_valid(
            TX_HFQ_DIR / f"{qlib_symbol}.csv",
            TX_REQUIRED_COLUMNS,
        )
    )


def validate_tx_dataframe(
    df: pd.DataFrame,
    symbol: str,
    adjustment: str,
) -> pd.DataFrame:
    if df is None or df.empty:
        raise RuntimeError(f"{symbol} {adjustment} 数据为空")

    missing = TX_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise RuntimeError(
            f"{symbol} {adjustment} 缺少字段：{sorted(missing)}；"
            f"实际字段：{df.columns.tolist()}"
        )

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
        "volume",
        "amount",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    if result["date"].isna().any():
        raise RuntimeError(f"{symbol} {adjustment} 存在无效日期")

    invalid_numeric = result[numeric_columns].isna().sum()
    invalid_numeric = invalid_numeric[invalid_numeric > 0]
    if not invalid_numeric.empty:
        raise RuntimeError(
            f"{symbol} {adjustment} 存在无效数值："
            f"{invalid_numeric.to_dict()}"
        )

    if result["date"].duplicated().any():
        raise RuntimeError(f"{symbol} {adjustment} 存在重复日期")

    bad_high = (
        result["high"]
        < result[["open", "close", "low"]].max(axis=1)
    )
    bad_low = (
        result["low"]
        > result[["open", "close", "high"]].min(axis=1)
    )

    if bad_high.any():
        raise RuntimeError(f"{symbol} {adjustment} 存在最高价异常")
    if bad_low.any():
        raise RuntimeError(f"{symbol} {adjustment} 存在最低价异常")
    if (
        result[["open", "close", "high", "low"]] <= 0
    ).any().any():
        raise RuntimeError(f"{symbol} {adjustment} 存在非正价格")
    if (result["volume"] < 0).any():
        raise RuntimeError(f"{symbol} {adjustment} 存在负成交量")
    if (result["amount"] < 0).any():
        raise RuntimeError(f"{symbol} {adjustment} 存在负成交额")

    return result.sort_values("date").reset_index(drop=True)


def is_network_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return True

    text = str(exc).lower()
    markers = (
        "remote end closed connection",
        "connection aborted",
        "connection reset",
        "timed out",
        "proxyerror",
    )
    return any(marker in text for marker in markers)


def download_tx_with_retry(
    tx_symbol: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> pd.DataFrame:
    adjustment_name = "unadjusted" if adjust == "" else adjust
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = ak.stock_zh_a_hist_tx(
                symbol=tx_symbol,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            time.sleep(REQUEST_DELAY_SECONDS)
            return validate_tx_dataframe(
                df,
                tx_symbol,
                adjustment_name,
            )

        except Exception as exc:
            last_error = exc
            wait_seconds = min(
                3 * (2 ** (attempt - 1)),
                45,
            )

            print(
                f"  {adjustment_name} "
                f"第{attempt}/{MAX_RETRIES}次失败："
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRIES:
                print(f"  {wait_seconds}秒后重试……")
                time.sleep(wait_seconds)

    raise RuntimeError(
        f"{tx_symbol} {adjustment_name} 连续下载失败："
        f"{last_error}"
    )


def save_csv_atomic(
    df: pd.DataFrame,
    destination: Path,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_suffix(".csv.tmp")
    df.to_csv(
        temporary,
        index=False,
        encoding="utf-8-sig",
    )
    temporary.replace(destination)


def append_manifest(record: dict) -> None:
    MANIFEST_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_header = not MANIFEST_FILE.exists()

    pd.DataFrame([record]).to_csv(
        MANIFEST_FILE,
        mode="a",
        header=write_header,
        index=False,
        encoding="utf-8-sig",
    )


def main() -> None:
    if not CONSTITUENTS_FILE.exists():
        raise FileNotFoundError(
            f"找不到成分股文件：{CONSTITUENTS_FILE}"
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

    constituents["日期"] = pd.to_datetime(
        constituents["日期"],
        errors="raise",
    )

    end_date = (
        constituents["日期"]
        .max()
        .strftime("%Y%m%d")
    )

    TX_UNADJUSTED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )
    TX_HFQ_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    reused_old_count = 0
    reused_tx_count = 0
    downloaded_count = 0
    failed_count = 0
    consecutive_network_failures = 0

    print("=" * 72)
    print("沪深300 AKShare 腾讯接口补缺下载")
    print("=" * 72)
    print("规则：已有完整东方财富数据则直接复用，不重复下载")
    print("规则：只有缺失股票才从腾讯接口下载")
    print(f"股票数量：{len(constituents)}")
    print(f"开始日期：{START_DATE}")
    print(f"结束日期：{end_date}")
    print("=" * 72)

    for index, row in constituents.iterrows():
        code = row["成分券代码"]
        name = row["成分券名称"]
        exchange = row["交易所"]

        tx_symbol, qlib_symbol = to_symbols(
            code,
            exchange,
        )

        print(
            f"\n[{index + 1}/{len(constituents)}] "
            f"{qlib_symbol} {name}"
        )

        if tx_pair_is_valid(qlib_symbol):
            print("  腾讯版两个完整文件均已存在，跳过")
            reused_tx_count += 1
            continue

        if old_pair_is_valid(qlib_symbol):
            print("  东方财富版两个完整文件均已存在，复用并跳过")
            reused_old_count += 1
            continue

        started_at = datetime.now()

        try:
            raw_df = download_tx_with_retry(
                tx_symbol,
                START_DATE,
                end_date,
                "",
            )

            hfq_df = download_tx_with_retry(
                tx_symbol,
                START_DATE,
                end_date,
                "hfq",
            )

            common_dates = (
                set(raw_df["date"])
                & set(hfq_df["date"])
            )

            if not common_dates:
                raise RuntimeError(
                    "不复权与后复权没有共同交易日期"
                )

            save_csv_atomic(
                raw_df,
                TX_UNADJUSTED_DIR / f"{qlib_symbol}.csv",
            )
            save_csv_atomic(
                hfq_df,
                TX_HFQ_DIR / f"{qlib_symbol}.csv",
            )

            append_manifest(
                {
                    "symbol": qlib_symbol,
                    "name": name,
                    "source": "tencent",
                    "status": "success",
                    "raw_rows": len(raw_df),
                    "hfq_rows": len(hfq_df),
                    "first_date": raw_df["date"].min().date(),
                    "last_date": raw_df["date"].max().date(),
                    "error": "",
                    "recorded_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }
            )

            downloaded_count += 1
            consecutive_network_failures = 0

            print(
                f"  腾讯下载成功："
                f"raw={len(raw_df)}行，"
                f"hfq={len(hfq_df)}行"
            )

        except Exception as exc:
            failed_count += 1

            if is_network_error(exc):
                consecutive_network_failures += 1
            else:
                consecutive_network_failures = 0

            append_manifest(
                {
                    "symbol": qlib_symbol,
                    "name": name,
                    "source": "tencent",
                    "status": "failed",
                    "raw_rows": "",
                    "hfq_rows": "",
                    "first_date": "",
                    "last_date": "",
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                    "recorded_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }
            )

            print(
                f"  最终失败："
                f"{type(exc).__name__}: {exc}"
            )

            if (
                consecutive_network_failures
                >= MAX_CONSECUTIVE_NETWORK_FAILURES
            ):
                print("\n" + "!" * 72)
                print(
                    "连续5只股票网络失败，"
                    "程序主动停止。"
                )
                print(
                    "稍后重新运行同一命令即可继续补缺。"
                )
                print("!" * 72)
                break

        elapsed = (
            datetime.now() - started_at
        ).total_seconds()

        print(f"  本只股票耗时：{elapsed:.1f}秒")
        time.sleep(STOCK_DELAY_SECONDS)

    print("\n" + "=" * 72)
    print("本次任务结束")
    print(f"复用东方财富文件：{reused_old_count}")
    print(f"复用腾讯文件：{reused_tx_count}")
    print(f"本次腾讯新下载：{downloaded_count}")
    print(f"本次失败：{failed_count}")
    print(f"清单：{MANIFEST_FILE}")
    print("=" * 72)


if __name__ == "__main__":
    main()
