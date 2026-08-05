"""Export and load a traceable backend Qlib execution artifact.

The frontend dashboard JSON is deliberately not accepted as an execution source.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from .exceptions import ArtifactError
from .models import ExecutionArtifact, SignalRecord, StrategyExecutionMetadata


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKTEST_DIR = PROJECT_ROOT / "outputs" / "backtest" / "v2"
DEFAULT_ARTIFACT_DIR = PROJECT_ROOT / "outputs" / "execution_artifacts"
DEFAULT_CALENDAR_PATH = PROJECT_ROOT / "data" / "qlib" / "cn_data" / "calendars" / "day.txt"
DEFAULT_UNIVERSE_PATH = PROJECT_ROOT / "data" / "qlib" / "cn_data" / "instruments" / "csi300.txt"
DEFAULT_STRATEGY_ID = "strategy-hs300-lightgbm-top5"


def _sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        if not path.exists():
            raise ArtifactError(f"Required Qlib source is missing: {path}")
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _finite_float(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ArtifactError(f"{field_name} is not numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ArtifactError(f"{field_name} must be finite.")
    return number


def _load_strategy_metadata(task: dict[str, Any]) -> StrategyExecutionMetadata:
    try:
        model = task["model"]
        handler = task["dataset"]["kwargs"]["handler"]
        port_config = next(
            record["kwargs"]["config"]
            for record in task["record"]
            if record.get("class") == "PortAnaRecord"
        )
        strategy = port_config["strategy"]
        strategy_kwargs = strategy["kwargs"]
        backtest = port_config["backtest"]
        exchange = backtest["exchange_kwargs"]
    except (KeyError, StopIteration, TypeError) as exc:
        raise ArtifactError("Qlib task_config.json does not contain the expected model/strategy configuration.") from exc

    return StrategyExecutionMetadata(
        strategy_id=DEFAULT_STRATEGY_ID,
        model=str(model["class"]),
        feature_set=str(handler["class"]),
        market="CN",
        benchmark=str(backtest["benchmark"]),
        universe=str(handler["kwargs"]["instruments"]),
        strategy_class=str(strategy["class"]),
        topk=int(strategy_kwargs["topk"]),
        n_drop=int(strategy_kwargs["n_drop"]),
        risk_degree=_finite_float(strategy_kwargs["risk_degree"], "risk_degree"),
        only_tradable=bool(strategy_kwargs["only_tradable"]),
        method_sell=str(strategy_kwargs.get("method_sell", "bottom")),
        method_buy=str(strategy_kwargs.get("method_buy", "top")),
        hold_thresh=int(strategy_kwargs.get("hold_thresh", 1)),
        deal_price=str(exchange["deal_price"]),
        open_cost=_finite_float(exchange["open_cost"], "open_cost"),
        close_cost=_finite_float(exchange["close_cost"], "close_cost"),
        min_cost=_finite_float(exchange["min_cost"], "min_cost"),
        signal_timing="previous Qlib trade step signal (T) selected by shift=1",
        execution_timing="next Qlib trade step (T+1) at configured close deal_price",
        weight_semantics=(
            "retain unsold holdings without rebalancing; sell selected holdings in full; "
            "split post-sell cash * risk_degree equally only across newly bought names"
        ),
    )


def export_execution_artifact(
    *,
    backtest_dir: Path = DEFAULT_BACKTEST_DIR,
    output_dir: Path = DEFAULT_ARTIFACT_DIR,
    calendar_path: Path = DEFAULT_CALENDAR_PATH,
    universe_path: Path = DEFAULT_UNIVERSE_PATH,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    """Create a normalized artifact from backend Qlib recorder exports, without retraining."""
    task_path = backtest_dir / "task_config.json"
    predictions_path = backtest_dir / "predictions.csv"
    top5_path = backtest_dir / "top5_predictions.csv"
    manifest_path = backtest_dir / "artifact_manifest.json"
    source_paths = [task_path, predictions_path, top5_path, manifest_path, calendar_path, universe_path]
    for path in source_paths:
        if not path.exists():
            raise ArtifactError(f"Required Qlib source is missing: {path}")

    task = json.loads(task_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metadata = _load_strategy_metadata(task)
    predictions = pd.read_csv(predictions_path)
    required_columns = {"datetime", "instrument", "score", "rank_desc", "score_percentile"}
    if not required_columns.issubset(predictions.columns):
        missing = sorted(required_columns - set(predictions.columns))
        raise ArtifactError(f"predictions.csv is missing columns: {missing}")
    predictions["datetime"] = pd.to_datetime(predictions["datetime"], errors="raise")
    signal_date = pd.Timestamp(predictions["datetime"].max())
    latest = predictions[predictions["datetime"].eq(signal_date)].copy()
    latest = latest.sort_values(["rank_desc", "instrument"])
    signals = [
        SignalRecord(
            code=str(row["instrument"]).upper(),
            score=_finite_float(row["score"], "score"),
            rank=int(_finite_float(row["rank_desc"], "rank")),
            score_percentile=_finite_float(row["score_percentile"], "score_percentile"),
        )
        for _, row in latest.iterrows()
    ]
    source_hash = _sha256_files(source_paths)
    config_hash = hashlib.sha256(task_path.read_bytes()).hexdigest()
    generated_at = datetime.fromtimestamp(
        max(path.stat().st_mtime for path in source_paths), tz=timezone.utc
    ).replace(microsecond=0).isoformat()
    artifact = ExecutionArtifact(
        schema_version="quantbuddy.execution-artifact.v1",
        source_kind="backend_qlib_recorder_export",
        is_mock=False,
        generated_at=generated_at,
        signal_date=signal_date.strftime("%Y-%m-%d"),
        source_artifact=[_relative(path, project_root) for path in source_paths],
        source_hash=source_hash,
        config_hash=config_hash,
        recorder_id=str(manifest.get("recorder_id", "")),
        calendar_path=_relative(calendar_path, project_root),
        universe_path=_relative(universe_path, project_root),
        metadata=metadata,
        signals=signals,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{metadata.strategy_id}_{artifact.signal_date}_{source_hash[:12]}.json"
    serialized = json.dumps(asdict(artifact), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if output_path.exists() and output_path.read_text(encoding="utf-8") != serialized:
        raise ArtifactError(f"Refusing to overwrite a different artifact: {output_path}")
    output_path.write_text(serialized, encoding="utf-8")
    return output_path


def artifact_from_dict(payload: dict[str, Any]) -> ExecutionArtifact:
    try:
        return ExecutionArtifact(
            schema_version=str(payload["schema_version"]),
            source_kind=str(payload["source_kind"]),
            is_mock=bool(payload["is_mock"]),
            generated_at=str(payload["generated_at"]),
            signal_date=str(payload["signal_date"]),
            source_artifact=[str(item) for item in payload["source_artifact"]],
            source_hash=str(payload["source_hash"]),
            config_hash=str(payload["config_hash"]),
            recorder_id=str(payload["recorder_id"]),
            calendar_path=str(payload["calendar_path"]),
            universe_path=str(payload["universe_path"]),
            metadata=StrategyExecutionMetadata(**payload["metadata"]),
            signals=[SignalRecord(**item) for item in payload["signals"]],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ArtifactError("Execution artifact is missing required fields or has invalid types.") from exc


def load_execution_artifact(path: Path) -> ExecutionArtifact:
    if not path.exists():
        raise ArtifactError(f"Execution artifact does not exist: {path}")
    return artifact_from_dict(json.loads(path.read_text(encoding="utf-8")))


def find_latest_artifact(
    strategy_id: str = DEFAULT_STRATEGY_ID, output_dir: Path = DEFAULT_ARTIFACT_DIR
) -> Path:
    candidates = sorted(output_dir.glob(f"{strategy_id}_*.json"))
    if not candidates:
        raise ArtifactError(f"No normalized execution artifact found for {strategy_id}.")
    return candidates[-1]
