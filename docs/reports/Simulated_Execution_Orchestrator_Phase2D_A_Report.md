# QuantBuddy Phase 2D-A — Simulated Execution Orchestrator Foundation and Shadow Run

Date: 2026-08-06

## 1. Scope and safety result

Phase 2D-A adds a recoverable, auditable **shadow-only** orchestrator around the existing `backend.futu` and `backend.execution` layers. It does not duplicate Futu Client, code mapping, account selection, Futu models, Safety, or Execution Plan models.

The command surface contains only:

```text
python -m backend.execution.orchestrator shadow-run --plan-id <plan_id>
```

There is no execution, place-order, live, modify, or cancel command. The integration run used `FUTU_ENABLE_SIMULATED_ORDERS=false`.

**SHADOW MODE / NO ORDER SUBMITTED / NO ORDER MODIFIED / NO ORDER CANCELLED**

## 2. State machine

The formal session state enum contains:

```text
CREATED
PRECHECKING
READY
SELLING
WAITING_FOR_SELLS
BUYING
WAITING_FOR_BUYS
RECONCILING
COMPLETED
SHADOW_COMPLETED
PAUSED
FAILED
CANCELLED
```

The actual initial-deployment Shadow Run followed:

```text
CREATED -> PRECHECKING -> READY
SELL phase: SKIPPED
BUYING -> RECONCILING -> SHADOW_COMPLETED
```

The local `SUBMITTING`, `SUBMITTED`, and `FILLED` intent events are explicitly marked as shadow simulation. They are not Futu order records and never modify broker state.

## 3. Execution Session model

The new stable models are in `backend/execution/orchestrator_models.py`:

- `ExecutionSession`
- `ExecutionStep`
- `ExecutionOrderIntent`
- `ExecutionOrderState`
- `ExecutionEvent`
- `ReconciliationResult`
- `ExecutionSummary`
- `ShadowSnapshot`
- `ExecutionPricePolicy`

The persisted session includes the requested plan/strategy/mode/date fields, masked account identifier, state, shadow flag, source hash, plan digest, account snapshot hash, ordered intents/events, warnings/blockers, failure reason, and final reconciliation. No full account ID or credential is stored.

## 4. Idempotency and recovery

- `session_id` is deterministically derived from `plan_id + plan source_hash`.
- One plan maps to one active session artifact by default.
- Re-running a paused session reloads the same session and reruns the complete read-only Precheck.
- Intent IDs are deterministic from the plan, sequence, symbol, side, quantity, and source hash.
- A completed or shadow-completed session cannot run again.
- A changed plan digest or source hash cannot resume an existing session.
- An `UNKNOWN` intent state pauses recovery and cannot be blindly resubmitted.
- Account position, order, cash, quote, lot-size, and tradable-quantity state is refreshed before every resume.
- Session JSON is an atomic latest-state snapshot; the JSONL event stream is append-only.

## 5. Precheck

`backend/execution/orchestrator_precheck.py` validates:

1. plan exists and deserializes;
2. `dry_run=true`;
3. `executable=true` and no plan blockers;
4. CN market;
5. SIMULATE environment;
6. ACTIVE account;
7. masked account identity remains consistent;
8. current date equals `planned_execution_date` (or an explicitly marked shadow-only clock override);
9. source hash remains unchanged;
10. holdings match the plan snapshot;
11. no relevant unfinished order exists;
12. current cash remains sufficient;
13. quotes are finite and positive;
14. target securities are not suspended;
15. quantities still match current lot sizes;
16. maximum cash-buy quantity remains sufficient;
17. single-order and total-plan persisted limits remain satisfied;
18. target symbols exactly match the projected plan holdings;
19. current prices remain inside the configured reference-price band;
20. no REAL path exists.

Immutable plan/security violations become `FAILED`; changing market/account conditions become `PAUSED`. No symbol is substituted and no plan is recalculated automatically.

## 6. Order intents

Each `PlannedOrder` is converted to a deterministic `ExecutionOrderIntent` containing:

- intent and plan IDs;
- code and side;
- planned quantity and lot size;
- plan reference price and current quote;
- relative deviation;
- minimum and maximum permitted reference band;
- estimated amount and sequence;
- local shadow status, reason, and source hash.

The real integration run produced five BUY intents and zero SELL intents. The SELL step is persisted as `SKIPPED`, which is required for `INITIAL_DEPLOYMENT`.

## 7. Price policy

The interface defines future semantic choices:

- `REFERENCE_LIMIT`
- `OPENING_SNAPSHOT_LIMIT`
- `CURRENT_SNAPSHOT_LIMIT`

Phase 2D-A uses `REFERENCE_LIMIT` only to display and validate the plan reference price, current snapshot, deviation, and allowed band. The conservative default blocker band is ±10%, corresponding to the standard A-share main-board daily price boundary; deviations above 5% also emit a prominent warning.

This is **not** an approved order-price decision. The strategy semantics remain: signal after T close, execute on T+1. Whether controlled execution eventually uses the opening price, an opening-period snapshot, another snapshot, or another limit-price rule remains unapproved and must be decided before any order-writing phase.

The first real Precheck correctly paused at the original provisional ±5% guard because SH600176 and SZ000657 moved approximately 6.16% and 9.98%. After replacing that arbitrary threshold with the documented ±10% CN guard and preserving >5% warnings, the same session safely resumed and completed its shadow reconciliation.

## 8. Actual INITIAL_DEPLOYMENT Shadow Run

- Plan: `plan-5a1633963d613a7a30f64f9a`
- Session: `session-210b5aa49b2d374271fbb895`
- Mode: `INITIAL_DEPLOYMENT`
- Signal date: `2026-08-05`
- Planned/current execution date: `2026-08-06`
- Shadow clock override: none
- State: `SHADOW_COMPLETED`
- SELL step: `SKIPPED`
- BUY intents: 5
- Blockers: 0
- Warnings: backtest-close reference semantics plus large-deviation warnings for SH600176 and SZ000657
- Event records: 24, including the safe pause and later resumed Precheck

No order identifier was created and no Futu write method was called.

## 9. Expected holdings and cash

Shadow reconciliation matched exactly:

| Code | Simulated target quantity |
|---|---:|
| SH600176 | 4,800 |
| SH600460 | 6,200 |
| SZ000657 | 3,300 |
| SZ000988 | 1,800 |
| SZ002837 | 3,600 |

- Reconciliation differences: none
- Reconciliation matched: true
- Estimated cash after the original plan and fees: **62,462.4655 CNY**

These are shadow holdings only. The actual Futu account remains unchanged.

## 10. Partial fills and failures

`evaluate_order_update` defines conservative future behavior without writing orders:

- `PARTIALLY_FILLED`: calculate the exact remainder, enter the matching WAITING state, query again, and never submit the remainder blindly.
- sell `SUBMITTING` / `SUBMITTED` / `PARTIALLY_FILLED`: stay in `WAITING_FOR_SELLS`; buying is forbidden until sells reach a known terminal result and reconciliation passes.
- buy failure/rejection/cancellation: stop the remaining buy batch and reconcile; do not continue creating portfolio drift.
- query timeout or `UNKNOWN`: enter `PAUSED`; duplicate submission is forbidden.
- `FILLED` with a quantity mismatch: pause for reconciliation.
- process restart: reload session + append-only events, verify plan digest/source hash, refresh all read-only state, and rerun Precheck.

## 11. Persistence

Session artifacts are stored under the already ignored `artifacts/` tree:

```text
artifacts/execution_sessions/
  session-210b5aa49b2d374271fbb895.json
  session-210b5aa49b2d374271fbb895.md
  session-210b5aa49b2d374271fbb895.events.jsonl
```

JSON contains machine state, Markdown contains a human summary, and JSONL is append-only. Historical completed sessions cannot be restarted.

## 12. Tests

- New focused Orchestrator tests: 27 passed.
- Full backend suite: **75 passed**.
- Python compilation/syntax check: PASS.

Coverage includes all 25 requested cases: initial SELL skip, rebalance ordering, duplicate-session prevention, completed-session refusal, expiry/date/hash/account/cash/order/suspension/price/max-quantity/lot blockers, partial/unknown state decisions, recovery, zero place/modify/cancel references, stable serialization/events/intents, and CN + SIMULATE enforcement.

## 13. Futu read-only integration evidence

The real Shadow Run read:

- simulated CN account and funds;
- current positions;
- recent orders;
- five current snapshots and lot sizes;
- maximum cash-buy quantity for each planned BUY.

Both Futu contexts closed normally. Console output explicitly stated:

```text
SHADOW MODE
NO ORDER SUBMITTED
NO ORDER MODIFIED
NO ORDER CANCELLED
```

## 14. Modified files

- `backend/execution/orchestrator.py`
- `backend/execution/orchestrator_models.py`
- `backend/execution/orchestrator_precheck.py`
- `backend/execution/orchestrator_store.py`
- `backend/execution/persistence.py`
- `backend/tests/test_orchestrator.py`
- `docs/Simulated_Execution_Orchestrator_Phase2D_A_Report.md`

No Phase 2D-A change was made under `frontend/`.

## 15. Not implemented and readiness decision

Not implemented by design:

- no simulated order placement;
- no order modification or cancellation;
- no actual fill polling;
- no approved execution-price policy;
- no real trading or unlock path;
- no scheduler/daemon;
- no frontend changes;
- no model retraining or new strategy.

The foundation is structurally ready for a separately approved controlled simulated-execution phase, but that future phase must first freeze the real order price policy, explicit activation controls, human confirmation, fill polling, and incident rollback procedure.

## Final status

- Orchestrator 结构：PASS
- 状态机：PASS
- 执行前检查：PASS
- 幂等保护：PASS
- 订单意图：PASS
- INITIAL_DEPLOYMENT Shadow Run：PASS
- 持仓对账模拟：PASS
- 中断恢复：PASS
- Mock 单元测试：PASS
- Futu 只读 Shadow Test：PASS
- 订单写操作：NOT EXECUTED
- READY_FOR_CONTROLLED_SIMULATED_EXECUTION：YES
