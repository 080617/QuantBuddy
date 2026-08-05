"""CLI for artifact audit, read-only planning, and plan display.

There is intentionally no --execute option.
"""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path

from .artifact_loader import (
    DEFAULT_STRATEGY_ID,
    PROJECT_ROOT,
    export_execution_artifact,
    find_latest_artifact,
    load_execution_artifact,
)
from .models import PlanningConfig
from .persistence import find_plan, save_execution_plan
from .runtime import build_readonly_futu_plan
from .signal_validator import validate_execution_artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QuantBuddy Qlib dry-run execution adapter")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit-artifacts", help="export and validate the backend Qlib artifact")
    audit.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    plan = sub.add_parser("plan", help="collect read-only Futu state and save a dry-run plan")
    plan.add_argument("--strategy-id", default=DEFAULT_STRATEGY_ID)
    plan.add_argument("--managed-code", action="append", default=[])
    show = sub.add_parser("show", help="show a persisted dry-run plan")
    show.add_argument("--plan-id", required=True)
    return parser


def _artifact_and_validation(strategy_id: str):
    if strategy_id != DEFAULT_STRATEGY_ID:
        raise ValueError(f"Unsupported strategy: {strategy_id}")
    export_execution_artifact()
    artifact_path = find_latest_artifact(strategy_id)
    artifact = load_execution_artifact(artifact_path)
    config = PlanningConfig()
    validation = validate_execution_artifact(
        artifact, project_root=PROJECT_ROOT, config=config, as_of=date.today()
    )
    return artifact_path, artifact, config, validation


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "show":
        print(find_plan(args.plan_id).read_text(encoding="utf-8"))
        return 0
    artifact_path, artifact, config, validation = _artifact_and_validation(args.strategy_id)
    if args.command == "audit-artifacts":
        print(f"Artifact: {artifact_path}")
        print(f"Signal date: {artifact.signal_date}")
        print(f"Source hash: {artifact.source_hash}")
        print(f"Strategy: {artifact.metadata.strategy_class} topk={artifact.metadata.topk} n_drop={artifact.metadata.n_drop}")
        print(f"Weight semantics: {artifact.metadata.weight_semantics}")
        print(f"Blockers: {len(validation.blockers)}")
        for blocker in validation.blockers:
            print(f"  {blocker.code}: {blocker.message}")
        return 0
    plan = build_readonly_futu_plan(
        artifact=artifact,
        validation=validation,
        planning_config=config,
        managed_codes={code.strip().upper() for code in args.managed_code},
    )
    json_path, summary_path = save_execution_plan(plan)
    print("DRY RUN / NO ORDER SUBMITTED")
    print("NO ORDER MODIFIED")
    print("NO ORDER CANCELLED")
    print(f"Plan ID: {plan.plan_id}")
    print(f"Executable: {plan.executable}")
    print(f"Blockers: {len(plan.blockers)}")
    print(f"JSON: {json_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
