from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import akshare as ak
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "akshare"

CSI300_FILE = RAW_DIR / "csi300_current.csv"
SAMPLE_FILE = RAW_DIR / "000001_raw.csv"


def validate_stock_data(df: pd.DataFrame) -> None:
    """对AKShare原始日线数据进行最基础的数据质量检查。"""

    required_columns = {
        "日期",
        "股票代码",
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise RuntimeError(
            f"缺少必要字段：{sorted(missing_columns)}；"
            f"实际字段：{df.columns.tolist()}"
        )

    if df.empty:
        raise RuntimeError("股票历史数据为空")

    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")

    numeric_columns = [
        "开盘",
        "收盘",
        "最高",
        "最低",
        "成交量",
        "成交额",
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if df["日期"].isna().any():
        raise RuntimeError("存在无法解析的日期")

    if df[numeric_columns].isna().any().any():
        invalid_counts = df[numeric_columns].isna().sum()
        raise RuntimeError(
            "存在无法解析的数值：\n"
            f"{invalid_counts[invalid_counts > 0]}"
        )

    duplicate_count = int(df["日期"].duplicated().sum())

    if duplicate_count > 0:
        raise RuntimeError(f"发现 {duplicate_count} 个重复交易日期")

    bad_high = df["最高"] < df[["开盘", "收盘", "最低"]].max(axis=1)
    bad_low = df["最低"] > df[["开盘", "收盘", "最高"]].min(axis=1)
    negative_volume = df["成交量"] < 0
    negative_amount = df["成交额"] < 0

    if bad_high.any():
        raise RuntimeError(f"发现 {int(bad_high.sum())} 行最高价异常")

    if bad_low.any():
        raise RuntimeError(f"发现 {int(bad_low.sum())} 行最低价异常")

    if negative_volume.any():
        raise RuntimeError(f"发现 {int(negative_volume.sum())} 行负成交量")

    if negative_amount.any():
        raise RuntimeError(f"发现 {int(negative_amount.sum())} 行负成交额")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("AKShare 数据源测试")
    print("=" * 60)
    print(f"AKShare版本：{ak.__version__}")
    print(f"保存目录：{RAW_DIR}")

    # ---------------------------------------------------------
    # 1. 获取当前沪深300成分股
    # ---------------------------------------------------------
    print("\n[1/2] 正在获取当前沪深300成分股……")

    constituents = ak.index_stock_cons_csindex(symbol="000300")

    if constituents.empty:
        raise RuntimeError("沪深300成分股数据为空")

    constituents.to_csv(
        CSI300_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"成分股数量：{len(constituents)}")
    print(f"字段：{constituents.columns.tolist()}")
    print(f"已保存：{CSI300_FILE}")

    print("\n成分股前5行：")
    print(constituents.head().to_string(index=False))

    # ---------------------------------------------------------
    # 2. 下载平安银行不复权日线
    # ---------------------------------------------------------
    print("\n[2/2] 正在下载000001历史日线……")

    # 排除今天，避免在交易时段读到尚未完成的当日数据
    end_date = (date.today() - timedelta(days=1)).strftime("%Y%m%d")

    stock_data = ak.stock_zh_a_hist(
        symbol="000001",
        period="daily",
        start_date="20240101",
        end_date=end_date,
        adjust="",
    )

    validate_stock_data(stock_data)

    stock_data = stock_data.sort_values("日期").reset_index(drop=True)

    stock_data.to_csv(
        SAMPLE_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(f"数据行数：{len(stock_data)}")
    print(f"开始日期：{stock_data['日期'].min().date()}")
    print(f"结束日期：{stock_data['日期'].max().date()}")
    print(f"字段：{stock_data.columns.tolist()}")
    print(f"已保存：{SAMPLE_FILE}")

    print("\n最后5行：")
    print(stock_data.tail().to_string(index=False))

    print("\n" + "=" * 60)
    print("AKShare数据源测试通过")
    print("=" * 60)


if __name__ == "__main__":
    main()