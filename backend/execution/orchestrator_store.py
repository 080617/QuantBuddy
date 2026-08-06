"""Non-destructive session snapshots plus append-only event logs."""

from __future__ import annotations

import json
from pathlib import Path

from .exceptions import PlanningError
from .models import ExecutionBlocker, ExecutionWarning
from .orchestrator_models import (
    ExecutionEvent,
    ExecutionOrderIntent,
    ExecutionOrderState,
    ExecutionPricePolicy,
    ExecutionSession,
    ExecutionSessionState,
    ExecutionStep,
    ReconciliationResult,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SESSION_DIR = PROJECT_ROOT / "artifacts" / "execution_sessions"


def session_from_dict(payload: dict) -> ExecutionSession:
    return ExecutionSession(
        **{
            **payload,
            "state": ExecutionSessionState(payload["state"]),
            "price_policy": ExecutionPricePolicy(payload["price_policy"]),
            "order_intents": [
                ExecutionOrderIntent(**{**item, "status": ExecutionOrderState(item["status"])})
                for item in payload.get("order_intents", [])
            ],
            "steps": [ExecutionStep(**item) for item in payload.get("steps", [])],
            "events": [ExecutionEvent(**item) for item in payload.get("events", [])],
            "warnings": [ExecutionWarning(**item) for item in payload.get("warnings", [])],
            "blockers": [ExecutionBlocker(**item) for item in payload.get("blockers", [])],
            "final_reconciliation": (
                ReconciliationResult(**payload["final_reconciliation"])
                if payload.get("final_reconciliation")
                else None
            ),
        }
    )


def load_session(session_id: str, output_dir: Path = DEFAULT_SESSION_DIR) -> ExecutionSession:
    path = output_dir / f"{session_id}.json"
    if not path.exists():
        raise PlanningError(f"Execution session not found: {session_id}")
    return session_from_dict(json.loads(path.read_text(encoding="utf-8")))


def find_session_for_plan(plan_id: str, output_dir: Path = DEFAULT_SESSION_DIR) -> ExecutionSession | None:
    if not output_dir.exists():
        return None
    for path in sorted(output_dir.glob("session-*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("plan_id") == plan_id:
            return session_from_dict(payload)
    return None


def _summary(session: ExecutionSession) -> str:
    matched = session.final_reconciliation.matched if session.final_reconciliation else False
    return "\n".join(
        [
            f"# Shadow Execution Session {session.session_id}",
            "",
            "**SHADOW MODE / NO ORDER SUBMITTED / NO ORDER MODIFIED / NO ORDER CANCELLED**",
            "",
            f"- Plan: `{session.plan_id}`",
            f"- State: `{session.state.value}`",
            f"- Mode: `{session.mode}`",
            f"- Execution date: `{session.planned_execution_date}`",
            f"- Shadow date override: `{session.shadow_date_override or 'NONE'}`",
            f"- Account: `{session.account_id_masked}`",
            f"- Order intents: `{len(session.order_intents)}`",
            f"- Blockers: `{len(session.blockers)}`",
            f"- Reconciliation matched: `{matched}`",
            "",
        ]
    )


def save_session(
    session: ExecutionSession,
    *,
    output_dir: Path = DEFAULT_SESSION_DIR,
    append_events: list[ExecutionEvent] | None = None,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{session.session_id}.json"
    summary_path = output_dir / f"{session.session_id}.md"
    event_path = output_dir / f"{session.session_id}.events.jsonl"
    temporary = json_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(session.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(json_path)
    summary_path.write_text(_summary(session), encoding="utf-8")
    if append_events:
        with event_path.open("a", encoding="utf-8") as handle:
            for event in append_events:
                handle.write(json.dumps(event.__dict__ if hasattr(event, "__dict__") else {
                    "sequence": event.sequence,
                    "occurred_at": event.occurred_at,
                    "event_type": event.event_type,
                    "state": event.state,
                    "message": event.message,
                    "intent_id": event.intent_id,
                }, ensure_ascii=False, sort_keys=True) + "\n")
    return json_path, summary_path, event_path
