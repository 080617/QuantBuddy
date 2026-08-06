"""Non-overwriting persistence for auditable execution plans."""

from __future__ import annotations

import json
from pathlib import Path

from .exceptions import PlanningError
from .models import (
    CurrentPosition,
    ExecutionBlocker,
    ExecutionPlan,
    ExecutionWarning,
    PlannedOrder,
    ReconciliationItem,
    TargetPosition,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAN_DIR = PROJECT_ROOT / "artifacts" / "execution_plans"


def _summary(plan: ExecutionPlan) -> str:
    lines = [
        f"# Execution Plan {plan.plan_id}",
        "",
        "**DRY RUN / NO ORDER SUBMITTED / NO ORDER MODIFIED / NO ORDER CANCELLED**",
        "",
        f"- Strategy: `{plan.strategy_id}`",
        f"- Signal date: `{plan.signal_date}`",
        f"- Planned execution date: `{plan.planned_execution_date or 'UNRESOLVED'}`",
        f"- Account: `{plan.account_id_masked}`",
        f"- Environment: `{plan.market} / {plan.trading_environment}`",
        f"- Executable: `{plan.executable}`",
        f"- Planned sells: `{len(plan.planned_sells)}`",
        f"- Planned buys: `{len(plan.planned_buys)}`",
        f"- Estimated turnover: `{plan.estimated_turnover:.6f}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(
        [f"- `{item.code}` {item.symbol or ''} - {item.message}" for item in plan.blockers]
        or ["- None"]
    )
    lines.extend(["", "## Warnings", ""])
    lines.extend(
        [f"- `{item.code}` {item.symbol or ''} - {item.message}" for item in plan.warnings]
        or ["- None"]
    )
    lines.extend(["", "## Planned sequence", ""])
    for order in plan.planned_sells + plan.planned_buys:
        lines.append(
            f"{order.sequence}. `{order.phase}` {order.side} `{order.code}` "
            f"{order.quantity} @ reference {order.limit_reference_price:.4f}"
        )
    if not plan.planned_sells and not plan.planned_buys:
        lines.append("- No candidate orders.")
    lines.append("")
    return "\n".join(lines)


def save_execution_plan(plan: ExecutionPlan, output_dir: Path = DEFAULT_PLAN_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{plan.plan_id}.json"
    summary_path = output_dir / f"{plan.plan_id}.md"
    json_payload = json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    summary_payload = _summary(plan)
    for path, payload in ((json_path, json_payload), (summary_path, summary_payload)):
        if path.exists():
            if path.read_text(encoding="utf-8") != payload:
                raise PlanningError(f"Refusing to overwrite a different plan artifact: {path}")
        else:
            path.write_text(payload, encoding="utf-8")
    return json_path, summary_path


def find_plan(plan_id: str, output_dir: Path = DEFAULT_PLAN_DIR) -> Path:
    path = output_dir / f"{plan_id}.json"
    if not path.exists():
        raise PlanningError(f"Plan not found: {plan_id}")
    return path


def load_execution_plan(plan_id: str, output_dir: Path = DEFAULT_PLAN_DIR) -> ExecutionPlan:
    payload = json.loads(find_plan(plan_id, output_dir).read_text(encoding="utf-8"))
    try:
        return ExecutionPlan(
            **{
                **payload,
                "target_positions": [TargetPosition(**item) for item in payload["target_positions"]],
                "current_positions": [CurrentPosition(**item) for item in payload["current_positions"]],
                "reconciliation": [ReconciliationItem(**item) for item in payload["reconciliation"]],
                "planned_sells": [PlannedOrder(**item) for item in payload["planned_sells"]],
                "planned_buys": [PlannedOrder(**item) for item in payload["planned_buys"]],
                "warnings": [ExecutionWarning(**item) for item in payload.get("warnings", [])],
                "blockers": [ExecutionBlocker(**item) for item in payload.get("blockers", [])],
            }
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanningError(f"Invalid execution plan artifact: {plan_id}") from exc
