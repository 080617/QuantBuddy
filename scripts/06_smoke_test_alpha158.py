from __future__ import annotations

from pathlib import Path

import pandas as pd
import qlib
from qlib.constant import REG_CN
from qlib.contrib.data.handler import Alpha158
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_URI = PROJECT_ROOT / "data" / "qlib" / "cn_data"

START_TIME = "2015-01-01"
END_TIME = "2026-07-30"

SEGMENTS = {
    "train": ("2015-01-01", "2021-12-31"),
    "valid": ("2022-01-01", "2023-12-31"),
    "test": ("2024-01-01", "2026-07-30"),
}


def count_feature_columns(df: pd.DataFrame) -> int:
    if isinstance(df.columns, pd.MultiIndex):
        top_level = df.columns.get_level_values(0)
        return int((top_level == "feature").sum())

    return len(df.columns)


def count_label_columns(df: pd.DataFrame) -> int:
    if isinstance(df.columns, pd.MultiIndex):
        top_level = df.columns.get_level_values(0)
        return int((top_level == "label").sum())

    return 0


def main() -> None:
    if not PROVIDER_URI.exists():
        raise FileNotFoundError(f"Qlib数据目录不存在：{PROVIDER_URI}")

    print("=" * 72)
    print("Alpha158 数据集最小验证")
    print("=" * 72)
    print(f"Qlib数据目录：{PROVIDER_URI}")
    print("股票池：csi300")
    print(f"总区间：{START_TIME} 至 {END_TIME}")
    print(f"分段：{SEGMENTS}")
    print("=" * 72)

    qlib.init(
        provider_uri=str(PROVIDER_URI),
        region=REG_CN,
    )

    handler = Alpha158(
        instruments="csi300",
        start_time=START_TIME,
        end_time=END_TIME,
        fit_start_time=SEGMENTS["train"][0],
        fit_end_time=SEGMENTS["train"][1],
    )

    dataset = DatasetH(
        handler=handler,
        segments=SEGMENTS,
    )

    all_passed = True

    for segment in ("train", "valid", "test"):
        data = dataset.prepare(
            segment,
            col_set=["feature", "label"],
            data_key=DataHandlerLP.DK_L,
        )

        feature_count = count_feature_columns(data)
        label_count = count_label_columns(data)

        instrument_count = (
            data.index.get_level_values("instrument").nunique()
            if isinstance(data.index, pd.MultiIndex)
            and "instrument" in data.index.names
            else 0
        )

        date_count = (
            data.index.get_level_values("datetime").nunique()
            if isinstance(data.index, pd.MultiIndex)
            and "datetime" in data.index.names
            else 0
        )

        total_nan = int(data.isna().sum().sum())
        duplicate_rows = int(data.index.duplicated().sum())

        print(f"\n[{segment}]")
        print(f"数据形状：{data.shape}")
        print(f"特征数量：{feature_count}")
        print(f"标签数量：{label_count}")
        print(f"股票数量：{instrument_count}")
        print(f"交易日数量：{date_count}")
        print(f"缺失值数量：{total_nan}")
        print(f"重复索引数量：{duplicate_rows}")

        if not data.empty:
            print("前3行：")
            print(data.head(3).to_string())

        segment_ok = (
            not data.empty
            and feature_count == 158
            and label_count == 1
            and instrument_count > 0
            and date_count > 0
            and duplicate_rows == 0
        )

        print(f"分段结果：{'通过' if segment_ok else '未通过'}")
        all_passed = all_passed and segment_ok

    print("\n" + "=" * 72)
    if all_passed:
        print("Alpha158最小验证通过")
        print("下一步可以配置LightGBM训练与回测")
    else:
        print("Alpha158最小验证未通过，请检查上方具体分段")
        raise SystemExit(1)
    print("=" * 72)


if __name__ == "__main__":
    main()
