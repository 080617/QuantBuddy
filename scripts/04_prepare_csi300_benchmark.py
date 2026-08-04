from __future__ import annotations

from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = (
    PROJECT_ROOT / "data" / "normalized" / "qlib_csv" / "SH000300.csv"
)

START_DATE = "20150101"
END_DATE = "20260730"


def main() -> None:
    print("正在通过腾讯接口下载沪深300指数……")

    df = ak.stock_zh_index_daily_tx(symbol="sh000300")

    if df is None or df.empty:
        raise RuntimeError("沪深300指数数据为空")

    required = {"date", "open", "high", "low", "close", "amount"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(
            f"指数数据缺少字段：{sorted(missing)}；"
            f"实际字段：{df.columns.tolist()}"
        )

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for column in ["open", "high", "low", "close", "amount"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    start = pd.Timestamp("2015-01-01")
    end = pd.Timestamp("2026-07-30")

    df = (
        df.loc[(df["date"] >= start) & (df["date"] <= end)]
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )

    if df.empty:
        raise RuntimeError("指定区间内没有沪深300指数数据")

    if df[["date", "open", "high", "low", "close", "amount"]].isna().any().any():
        raise RuntimeError("沪深300指数存在无法解析的字段")

    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise RuntimeError("沪深300指数存在非正价格")

    first_close = float(df.iloc[0]["close"])
    factor = 1.0 / first_close

    # 腾讯指数接口的 amount 字段为成交量口径；这里只用于满足
    # Qlib 基础字段要求，基准收益实际由 close 计算。
    raw_volume = df["amount"].astype(float) * 100.0

    output = pd.DataFrame(
        {
            "date": df["date"].dt.strftime("%Y-%m-%d"),
            "open": df["open"] * factor,
            "high": df["high"] * factor,
            "low": df["low"] * factor,
            "close": df["close"] * factor,
            "volume": raw_volume / factor,
            "factor": factor,
            # 指数接口没有逐日成交额字段，基准仅需收盘价；
            # 为保持字段完整，vwap 使用调整后收盘价占位。
            "vwap": df["close"] * factor,
        }
    )

    if not np.isclose(float(output.iloc[0]["close"]), 1.0, atol=1e-8):
        raise RuntimeError("沪深300指数首日收盘价归一化失败")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUTPUT_FILE.with_suffix(".csv.tmp")

    output.to_csv(temporary, index=False, encoding="utf-8")
    temporary.replace(OUTPUT_FILE)

    print(f"数据行数：{len(output)}")
    print(f"日期范围：{output.iloc[0]['date']} 至 {output.iloc[-1]['date']}")
    print(f"已保存：{OUTPUT_FILE}")
    print("沪深300基准数据准备完成")


if __name__ == "__main__":
    main()
