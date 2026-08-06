"""Run inference with the existing trained LightGBM model; never train a model."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pickle

import pandas as pd
import qlib
from qlib.constant import REG_CN
from qlib.utils import init_instance_by_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROVIDER_URI = PROJECT_ROOT / "data" / "qlib" / "cn_data"
MODEL_PATH = PROJECT_ROOT / "outputs" / "backtest" / "v2" / "trained_model.pkl"
TASK_PATH = PROJECT_ROOT / "outputs" / "backtest" / "v2" / "task_config.json"
SOURCE_MANIFEST = PROJECT_ROOT / "outputs" / "backtest" / "v2" / "artifact_manifest.json"
REFRESH_ROOT = PROJECT_ROOT / "outputs" / "market_refresh"
DEFAULT_OUTPUT = PROJECT_ROOT / "outputs" / "forward" / "v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _latest_refresh_manifest() -> tuple[Path, dict]:
    candidates = sorted(REFRESH_ROOT.glob("*/refresh_manifest.json"))
    if not candidates:
        raise FileNotFoundError("No market refresh manifest exists")
    path = candidates[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Reuse the frozen LightGBM model for forward inference")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    refresh_path, refresh = _latest_refresh_manifest()
    data_as_of = str(refresh["data_as_of"])
    next_trading_day = str(refresh["next_trading_day"])
    calendar = {
        line.strip()
        for line in (PROVIDER_URI / "calendars" / "day.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if data_as_of not in calendar or next_trading_day not in calendar:
        raise RuntimeError("Qlib calendar does not contain the refreshed signal/execution dates")
    task = json.loads(TASK_PATH.read_text(encoding="utf-8"))
    inference_task = deepcopy(task)
    handler = inference_task["dataset"]["kwargs"]["handler"]["kwargs"]
    handler["end_time"] = data_as_of
    inference_task["dataset"]["kwargs"]["segments"]["test"] = [data_as_of, data_as_of]

    os.chdir(PROJECT_ROOT)
    qlib.init(provider_uri=str(PROVIDER_URI), region=REG_CN)
    with MODEL_PATH.open("rb") as handle:
        model = pickle.load(handle)
    dataset = init_instance_by_config(inference_task["dataset"])
    predictions = model.predict(dataset, segment="test")
    if isinstance(predictions, pd.DataFrame):
        if len(predictions.columns) != 1:
            raise RuntimeError("Forward prediction returned more than one score column")
        predictions = predictions.iloc[:, 0]
    if not isinstance(predictions, pd.Series) or predictions.empty:
        raise RuntimeError("Forward prediction returned no scores")
    frame = predictions.rename("score").reset_index()
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="raise")
    frame = frame[frame["datetime"].eq(pd.Timestamp(data_as_of))].copy()
    frame = frame.dropna(subset=["score"])
    if len(frame) < 5:
        raise RuntimeError(f"Only {len(frame)} valid scores were produced for {data_as_of}")
    frame["rank_desc"] = frame["score"].rank(method="first", ascending=False).astype(int)
    frame["score_percentile"] = frame["score"].rank(method="average", pct=True)
    frame = frame.sort_values(["rank_desc", "instrument"])

    strategy = next(
        record["kwargs"]["config"]["strategy"]["kwargs"]
        for record in inference_task["record"]
        if record.get("class") == "PortAnaRecord"
    )
    topk = int(strategy["topk"])
    risk_degree = float(strategy["risk_degree"])
    target_weight = risk_degree / topk
    frame["target_weight"] = 0.0
    frame.loc[frame["rank_desc"].le(topk), "target_weight"] = target_weight

    output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_dir / "predictions.csv", index=False, encoding="utf-8")
    frame[frame["rank_desc"].le(topk)].to_csv(
        output_dir / "top5_predictions.csv", index=False, encoding="utf-8"
    )
    (output_dir / "task_config.json").write_text(
        json.dumps(inference_task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "experiment": "forward-inference",
        "recorder_id": f"forward-{source_manifest['recorder_id']}-{data_as_of}",
        "source_recorder_id": source_manifest["recorder_id"],
        "model_source": MODEL_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "model_sha256": _sha256(MODEL_PATH),
        "refresh_manifest": refresh_path.relative_to(PROJECT_ROOT).as_posix(),
        "data_as_of": data_as_of,
        "signal_date": data_as_of,
        "next_trading_day": next_trading_day,
        "inference_only": True,
        "retrained": False,
        "mock": False,
        "topk": topk,
        "risk_degree": risk_degree,
        "initial_target_weight_each": target_weight,
        "cash_reserve_weight": 1.0 - risk_degree,
        "generated_at": refresh["generated_at"],
    }
    (output_dir / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(frame.head(topk)[["instrument", "rank_desc", "score", "target_weight"]].to_string(index=False))


if __name__ == "__main__":
    main()
