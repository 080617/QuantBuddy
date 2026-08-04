from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import akshare as ak
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONSTITUENTS_FILE = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "csi300_current.csv"
)

UNADJUSTED_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "unadjusted"
)

HFQ_DIR = (
    PROJECT_ROOT / "data" / "raw" / "akshare" / "hfq"
)

MANIFEST_FILE = (
    PROJECT_ROOT / "data" / "metadata" / "akshare_download_manifest.csv"
)

START_DATE = "20150101"
MAX_RETRIES = 5
REQUEST_DELAY_SECONDS = 0.5


REQUIRED_COLUMNS = {
    "日期",
    "股票代码",
    "开盘",
    "收盘",
    "最高",
    "最低",
    "成交量",
    "成交额",
}


def get_qlib_symbol(code: str, exchange: str) -> str:
    """把AKShare六位代码转换为Qlib代码，如 SZ000001。"""

    code = str(code).zfill(6)
    exchange = str(exchange)

    if "上海" in exchange:
        return f"SH{code}"

    if "深圳" in exchange:
        return f"SZ{code}"

    raise ValueError(f"无法识别交易所：code={code}, exchange={exchange}")


def validate_dataframe(
    df: pd.DataFrame,
    code: str,
    adjustment: str,
) -> pd.DataFrame:
    """检查单只股票下载结果。"""

    if df is None or df.empty:
        raise RuntimeError(
            f"{code} {adjustment} 数据为空"
        )

    missing_columns = REQUIRED_COLUMNS - set(df.columns)

    if missing_columns:
        raise RuntimeError(
            f"{code} {adjustment} 缺少字段："
            f"{sorted(missing_columns)}"
        )

    result = df.copy()

    result["日期"] = pd.to_datetime(
        result["日期"],
        errors="coerce",
    )

    numeric_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
    ]

    for column in numeric_columns:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    if result["日期"].isna().any():
        raise RuntimeError(
            f"{code} {adjustment} 存在无效日期"
        )

    invalid_numeric = result[numeric_columns].isna().sum()
    invalid_numeric = invalid_numeric[invalid_numeric > 0]

    if not invalid_numeric.empty:
        raise RuntimeError(
            f"{code} {adjustment} 存在无效数值："
            f"{invalid_numeric.to_dict()}"
        )

    if result["日期"].duplicated().any():
        count = int(result["日期"].duplicated().sum())

        raise RuntimeError(
            f"{code} {adjustment} 存在{count}个重复日期"
        )

    invalid_high = (
        result["最高"]
        < result[["开盘", "收盘", "最低"]].max(axis=1)
    )

    invalid_low = (
        result["最低"]
        > result[["开盘", "收盘", "最高"]].min(axis=1)
    )

    if invalid_high.any():
        raise RuntimeError(
            f"{code} {adjustment} 存在最高价异常"
        )

    if invalid_low.any():
        raise RuntimeError(
            f"{code} {adjustment} 存在最低价异常"
        )

    if (result[["开盘", "收盘", "最高", "最低"]] <= 0).any().any():
        raise RuntimeError(
            f"{code} {adjustment} 存在非正价格"
        )

    if (result["成交量"] < 0).any():
        raise RuntimeError(
            f"{code} {adjustment} 存在负成交量"
        )

    if (result["成交额"] < 0).any():
        raise RuntimeError(
            f"{code} {adjustment} 存在负成交额"
        )

    return (
        result
        .sort_values("日期")
        .reset_index(drop=True)
    )


def download_with_retry(
    code: str,
    start_date: str,
    end_date: str,
    adjust: str,
) -> pd.DataFrame:
    """下载一只股票，失败时自动重试。"""

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )

            adjustment_name = adjust or "unadjusted"

            return validate_dataframe(
                df=df,
                code=code,
                adjustment=adjustment_name,
            )

        except Exception as exc:
            last_error = exc

            wait_seconds = min(2 ** attempt, 30)

            print(
                f"  下载失败，第{attempt}/{MAX_RETRIES}次："
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRIES:
                print(f"  {wait_seconds}秒后重试……")
                time.sleep(wait_seconds)

    raise RuntimeError(
        f"{code} 连续下载失败：{last_error}"
    )


def save_csv_atomic(
    df: pd.DataFrame,
    destination: Path,
) -> None:
    """先写临时文件，成功后替换正式文件。"""

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = destination.with_suffix(".csv.tmp")

    df.to_csv(
        temporary_file,
        index=False,
        encoding="utf-8-sig",
    )

    temporary_file.replace(destination)


def append_manifest(record: dict) -> None:
    """每完成一只股票就立即写入清单。"""

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
        constituents["日期"]
    )

    # 统一使用成分股文件对应的完整交易日
    target_end_date = (
        constituents["日期"]
        .max()
        .strftime("%Y%m%d")
    )

    UNADJUSTED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    HFQ_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    total = len(constituents)

    print("=" * 70)
    print("沪深300 AKShare 批量下载")
    print("=" * 70)
    print(f"股票数量：{total}")
    print(f"开始日期：{START_DATE}")
    print(f"结束日期：{target_end_date}")
    print(f"不复权目录：{UNADJUSTED_DIR}")
    print(f"后复权目录：{HFQ_DIR}")
    print("=" * 70)

    success_count = 0
    failure_count = 0
    skipped_count = 0

    for index, row in constituents.iterrows():
        code = row["成分券代码"]
        name = row["成分券名称"]
        exchange = row["交易所"]

        qlib_symbol = get_qlib_symbol(
            code=code,
            exchange=exchange,
        )

        unadjusted_file = (
            UNADJUSTED_DIR / f"{qlib_symbol}.csv"
        )

        hfq_file = (
            HFQ_DIR / f"{qlib_symbol}.csv"
        )

        print(
            f"\n[{index + 1}/{total}] "
            f"{qlib_symbol} {name}"
        )

        # 已完整保存的股票直接跳过，支持断点续传
        if unadjusted_file.exists() and hfq_file.exists():
            print("  两个文件均已存在，跳过")

            skipped_count += 1
            continue

        started_at = datetime.now()

        try:
            unadjusted_df = download_with_retry(
                code=code,
                start_date=START_DATE,
                end_date=target_end_date,
                adjust="",
            )

            hfq_df = download_with_retry(
                code=code,
                start_date=START_DATE,
                end_date=target_end_date,
                adjust="hfq",
            )

            unadjusted_dates = set(
                unadjusted_df["日期"]
            )

            hfq_dates = set(
                hfq_df["日期"]
            )

            if unadjusted_dates != hfq_dates:
                raise RuntimeError(
                    "不复权与后复权交易日期不一致："
                    f"raw={len(unadjusted_dates)}, "
                    f"hfq={len(hfq_dates)}"
                )

            save_csv_atomic(
                unadjusted_df,
                unadjusted_file,
            )

            save_csv_atomic(
                hfq_df,
                hfq_file,
            )

            append_manifest(
                {
                    "symbol": qlib_symbol,
                    "code": code,
                    "name": name,
                    "exchange": exchange,
                    "status": "success",
                    "raw_rows": len(unadjusted_df),
                    "hfq_rows": len(hfq_df),
                    "first_date": unadjusted_df["日期"].min(),
                    "last_date": unadjusted_df["日期"].max(),
                    "error": "",
                    "downloaded_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }
            )

            success_count += 1

            print(
                f"  成功：{len(unadjusted_df)}行，"
                f"{unadjusted_df['日期'].min().date()} 至 "
                f"{unadjusted_df['日期'].max().date()}"
            )

        except Exception as exc:
            failure_count += 1

            append_manifest(
                {
                    "symbol": qlib_symbol,
                    "code": code,
                    "name": name,
                    "exchange": exchange,
                    "status": "failed",
                    "raw_rows": "",
                    "hfq_rows": "",
                    "first_date": "",
                    "last_date": "",
                    "error": f"{type(exc).__name__}: {exc}",
                    "downloaded_at": datetime.now().isoformat(
                        timespec="seconds"
                    ),
                }
            )

            print(
                f"  最终失败："
                f"{type(exc).__name__}: {exc}"
            )

        elapsed = (
            datetime.now() - started_at
        ).total_seconds()

        print(f"  本只股票耗时：{elapsed:.1f}秒")

        time.sleep(REQUEST_DELAY_SECONDS)

    print("\n" + "=" * 70)
    print("批量下载结束")
    print(f"本次成功：{success_count}")
    print(f"本次跳过：{skipped_count}")
    print(f"本次失败：{failure_count}")
    print(f"下载清单：{MANIFEST_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()