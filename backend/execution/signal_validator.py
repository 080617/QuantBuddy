"""Strict structural and freshness validation for execution artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import math
from pathlib import Path

from backend.futu.code_mapper import qlib_to_futu

from .exceptions import ArtifactError
from .models import ExecutionArtifact, ExecutionBlocker, ExecutionWarning, PlanningConfig


@dataclass(frozen=True, slots=True)
class ArtifactValidation:
    planned_execution_date: str | None
    blockers: list[ExecutionBlocker]
    warnings: list[ExecutionWarning]


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ArtifactError(f"{field_name} must be an ISO date.") from exc


def _load_calendar(path: Path) -> list[date]:
    if not path.exists():
        raise ArtifactError(f"Qlib calendar is missing: {path}")
    return sorted({_parse_date(line.strip(), "calendar date") for line in path.read_text().splitlines() if line.strip()})


def _load_universe(path: Path, signal_date: date) -> set[str]:
    if not path.exists():
        raise ArtifactError(f"Frozen universe is missing: {path}")
    active: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise ArtifactError(f"Malformed universe row: {line!r}")
        code, start_text, end_text = parts
        if _parse_date(start_text, "universe start") <= signal_date <= _parse_date(end_text, "universe end"):
            active.add(code.upper())
    return active


def _verify_source_hash(artifact: ExecutionArtifact, project_root: Path) -> None:
    digest = hashlib.sha256()
    paths = [project_root / relative for relative in artifact.source_artifact]
    for path in sorted(paths, key=lambda item: item.as_posix()):
        if not path.exists():
            raise ArtifactError(f"Source artifact no longer exists: {path}")
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    if digest.hexdigest() != artifact.source_hash:
        raise ArtifactError("Execution artifact source_hash does not match its backend Qlib sources.")


def validate_execution_artifact(
    artifact: ExecutionArtifact,
    *,
    project_root: Path,
    config: PlanningConfig,
    as_of: date | None = None,
    verify_source_hash: bool = True,
) -> ArtifactValidation:
    """Raise for malformed/untrusted artifacts; return blockers for time-dependent safety stops."""
    if artifact.schema_version != "quantbuddy.execution-artifact.v1":
        raise ArtifactError("Unsupported execution artifact schema.")
    if artifact.is_mock or artifact.source_kind != "backend_qlib_recorder_export":
        raise ArtifactError("Mock or non-backend artifacts cannot drive execution planning.")
    if any("frontend/public/data" in item.replace("\\", "/").lower() for item in artifact.source_artifact):
        raise ArtifactError("Frontend display JSON cannot be an execution source.")
    if artifact.metadata.strategy_id not in config.allowed_strategy_ids:
        raise ArtifactError(f"Strategy is not allow-listed: {artifact.metadata.strategy_id}")
    if not artifact.recorder_id or len(artifact.source_hash) != 64 or len(artifact.config_hash) != 64:
        raise ArtifactError("Recorder ID and traceability hashes are required.")
    try:
        datetime.fromisoformat(artifact.generated_at)
    except ValueError as exc:
        raise ArtifactError("generated_at must be an ISO timestamp.") from exc
    signal_date = _parse_date(artifact.signal_date, "signal_date")
    metadata = artifact.metadata
    if metadata.market != "CN" or metadata.universe.lower() != "csi300":
        raise ArtifactError("Only the frozen CN CSI300 strategy is supported.")
    if not metadata.model or not metadata.feature_set:
        raise ArtifactError("Model and feature configuration are required.")
    if metadata.strategy_class != "TopkDropoutStrategy":
        raise ArtifactError("Only TopkDropoutStrategy is supported in Phase 2C.")
    if metadata.topk != 5 or metadata.n_drop != 1 or not (0 < metadata.risk_degree <= 1):
        raise ArtifactError("Top-5/n_drop/risk_degree configuration is inconsistent with the frozen strategy.")
    if metadata.method_sell != "bottom" or metadata.method_buy != "top":
        raise ArtifactError("Unsupported TopkDropoutStrategy buy/sell method.")
    if "retain unsold holdings without rebalancing" not in metadata.weight_semantics:
        raise ArtifactError("Weight semantics are missing or inconsistent with Qlib TopkDropoutStrategy.")
    if not artifact.signals:
        raise ArtifactError("Artifact contains no signals.")

    codes = [signal.code for signal in artifact.signals]
    if len(codes) != len(set(codes)):
        raise ArtifactError("Duplicate security codes are not allowed.")
    ranks = [signal.rank for signal in artifact.signals]
    if len(ranks) != len(set(ranks)) or min(ranks) != 1:
        raise ArtifactError("Signal ranks must be unique and start at 1.")
    for signal in artifact.signals:
        qlib_to_futu(signal.code)
        if not all(math.isfinite(value) for value in (signal.score, signal.score_percentile)):
            raise ArtifactError(f"Signal values must be finite: {signal.code}")
        if not 0 <= signal.score_percentile <= 1:
            raise ArtifactError(f"Invalid score percentile: {signal.code}")
    top = sorted(artifact.signals, key=lambda item: item.rank)[: metadata.topk]
    if [item.rank for item in top] != list(range(1, metadata.topk + 1)):
        raise ArtifactError("Top-5 count/ranks do not match strategy configuration.")

    universe_path = project_root / artifact.universe_path
    active_universe = _load_universe(universe_path, signal_date)
    outside = sorted(set(codes) - active_universe)
    if outside:
        raise ArtifactError(f"Signals outside the frozen CSI300 universe: {outside[:5]}")
    calendar = _load_calendar(project_root / artifact.calendar_path)
    if signal_date not in calendar:
        raise ArtifactError("signal_date is not present in the Qlib trading calendar.")
    if verify_source_hash:
        _verify_source_hash(artifact, project_root)

    blockers: list[ExecutionBlocker] = []
    warnings: list[ExecutionWarning] = []
    today = as_of or date.today()
    age = (today - signal_date).days
    if age < 0:
        blockers.append(ExecutionBlocker("SIGNAL_FROM_FUTURE", "Signal date is later than the planning date."))
    elif age > config.max_signal_age_calendar_days:
        blockers.append(
            ExecutionBlocker(
                "STALE_SIGNAL",
                f"Signal is {age} calendar days old; limit is {config.max_signal_age_calendar_days}.",
            )
        )
    next_dates = [item for item in calendar if item > signal_date]
    if next_dates:
        execution_date = next_dates[0].isoformat()
    else:
        execution_date = None
        blockers.append(
            ExecutionBlocker(
                "EXECUTION_DATE_NOT_IN_CALENDAR",
                "The frozen Qlib calendar has no trading session after the signal date.",
            )
        )
    if metadata.deal_price == "close":
        warnings.append(
            ExecutionWarning(
                "BACKTEST_CLOSE_PRICE_SEMANTICS",
                "Qlib used next-step close pricing; the dry-run uses current snapshots only as references.",
            )
        )
    return ArtifactValidation(execution_date, blockers, warnings)
