# QuantBuddy Phase 2D-B1 — Controlled Simulated Canary Execution

Date: 2026-08-06

## 1. Scope and safety outcome

Phase 2D-B1 adds a deliberately narrow execution path around the approved dry-run plan. It can submit at most one CN simulated BUY limit order, for exactly one current board lot, only after two independent fresh prechecks and an exact interactive confirmation.

No canary order was executed while implementing or validating this phase. The only OpenD integration run was `canary-preflight`, with both write switches explicitly set to `false`.

```text
NO ORDER SUBMITTED
NO ORDER MODIFIED
NO ORDER CANCELLED
```

The implementation does not provide `--live`, `--execute-all`, `--skip-precheck`, `--ignore-date`, `--ignore-price-band`, or `--ignore-existing-orders`. It contains no trade-unlock flow and no complete Top-5 deployment command.

## 2. Canary selection

The selector considers only BUY intents already present in the immutable Execution Plan and sorts by:

```text
(estimated_value, code, sequence)
```

This makes selection stable for the same plan and account snapshot. Users cannot substitute another symbol at the terminal.

Approved plan input:

- Plan ID: `plan-5a1633963d613a7a30f64f9a`
- Strategy: `strategy-hs300-lightgbm-top5`
- Signal date: 2026-08-05
- Planned execution date: 2026-08-06
- Plan mode: `INITIAL_DEPLOYMENT`
- Plan properties: `dry_run=true`, `executable=true`, `blockers=[]`

Deterministically selected canary:

- Code: `SZ000988`
- Name in existing product data: 华工科技
- Original planned quantity: 1,800 shares
- Current lot size / canary quantity: 100 shares
- Original planned estimated value: CNY 180,774.00
- Selection reason: minimum estimated value, followed by code and sequence as deterministic tie-breakers

The original plan remains unchanged. The separate Canary Session always records:

```text
execution_mode=CANARY
canary_order_limit=1
full_plan_completed=false
```

## 3. Dual safety switches

A write attempt is rejected unless all four conditions hold simultaneously:

```text
FUTU_MARKET=CN
FUTU_TRD_ENV=SIMULATE
FUTU_ENABLE_SIMULATED_ORDERS=true
EXECUTION_ENABLE_CANARY=true
```

`REAL`, a non-CN market, or either disabled/missing write switch fails closed. The read-only preflight does not require write switches and therefore can be inspected safely.

## 4. Two fresh prechecks

The execution path performs one full read-only precheck before showing the confirmation prompt. After the user types the exact phrase, it reloads the persisted plan, verifies its digest and source hash, and obtains a second fresh account/market snapshot. The first result is never reused as the final authorization.

Each precheck verifies:

- persisted plan identity, digest, source hash, strategy ID, `dry_run`, executability, and planned date;
- the same masked CN + SIMULATE + ACTIVE account;
- funds, positions, current/recent orders, target quote, suspension state, current lot size, and maximum cash-buy quantity;
- no related unfinished order;
- selected symbol remains in the plan;
- canary quantity equals exactly one current lot;
- sufficient cash and maximum buy quantity;
- fresh snapshot and ORDER_BOOK timestamps;
- valid best ask, price band, tick size, and canary amount cap;
- no existing session order ID or prior placement attempt.

For the selected symbol, maximum cash-buy quantity is refreshed again at the current best-ask price rather than relying on a quantity calculated from an older snapshot price.

A failing check persists a `PAUSED` session with explicit blockers. It never generates a replacement plan or switches to another stock.

## 5. Price policy

The formal policy is `CANARY_TOP_OF_BOOK_LIMIT`:

1. subscribe to the target's `ORDER_BOOK`;
2. read the current best ask and server timestamp;
3. reject a missing, malformed, non-positive, or stale ask;
4. compare it to the plan reference-price band;
5. legalize it upward to the snapshot `price_spread` tick;
6. use the resulting value as a normal BUY limit price.

There is no market-order path and no fallback to `last_price`. The accepted price can never be raised automatically to chase a fill.

The 2026-08-06 read-only preflight observed:

- Best ask: CNY 102.72
- Tick-legal limit: CNY 102.72
- One-lot estimated amount: CNY 10,272.00
- Plan reference price: CNY 100.43
- Allowed band: CNY 90.387 to CNY 110.473
- Maximum cash-buy quantity: 9,700 shares

The preflight correctly ended in `PAUSED`, not ready-to-submit, because both `ORDER_BOOK_STALE` and `QUOTE_STALE` were raised. The diagnostic was performed during the midday market break; the snapshot's last update was 11:30. No freshness threshold was weakened to force a pass.

## 6. Interactive confirmation and submission guard

The terminal prints the CN/SIMULATE, one-order, one-lot warning and the full candidate summary. It then reads the exact phrase from interactive input:

```text
EXECUTE ONE-LOT CANARY
```

The phrase is not accepted as a CLI argument and therefore is not designed to enter shell history. Any mismatch persists `ABORTED_BY_USER`, closes all contexts, and places no order.

Immediately before the one permitted broker call, the session atomically persists:

- `place_attempted=true`;
- `place_call_count=1`;
- request hash;
- `SUBMITTING` state and audit event.

This fail-closed guard prevents a restart from treating an ambiguous placement result as permission to submit again. When a placement result is returned, the full order ID is saved locally before the first status query; ordinary output uses only the masked ID. The broker remark is a short deterministic `QB-CANARY-<suffix>` value.

## 7. Status tracking

The implementation maps broker values conservatively into:

```text
SUBMITTING
SUBMITTED
PARTIALLY_FILLED
FILLED
CANCEL_PENDING
CANCELLED
REJECTED
FAILED
UNKNOWN
```

Polling is bounded to one query every three seconds for at most 30 seconds. Queries are always by the known order ID. A missing record, exception, or unknown status produces `UNKNOWN_REQUIRES_REVIEW`; it never retries placement and never blindly cancels.

## 8. Fill, partial fill, timeout, and cancellation

- Full fill: do not cancel; refresh account state, reconcile the new position, mark `CANARY_FILLED`, set `requires_new_plan=true`, and stop.
- Partial fill: issue at most one cancellation for the confirmed remaining quantity, query the final status again, reconcile actual quantity/cash, mark `CANARY_PARTIALLY_FILLED`, and stop.
- No fill at timeout: issue at most one cancellation, query final status, reconcile, mark `CANARY_CANCELLED_NO_FILL`, and stop.
- Rejected/failed: do not retry; refresh and reconcile.
- Unknown query/cancel outcome: keep the known order ID, mark `UNKNOWN_REQUIRES_REVIEW`, and require manual review.

No path modifies price or quantity. A cancellation request is only possible for a known order ID with a confirmed unfilled remainder. Success of the cancellation request is not treated as final until the order is queried again.

Regardless of a fill, `full_plan_completed` stays `false`. Any non-zero fill requires refreshed market data, signals, account reconciliation, and a newly generated remaining deployment plan. The other four plan orders are never submitted automatically.

## 9. Persistence, idempotency, and recovery

Canary sessions are stored separately as atomic JSON under the ignored directory:

```text
artifacts/execution_sessions/<canary-session-id>.canary.json
```

The deterministic session ID binds the plan, source hash, and masked account. A session containing an order ID or a recorded placement attempt can never place again, even when broker status is unknown.

Read-only recovery commands:

```text
python -m backend.execution.orchestrator canary-status --session-id <session-id>
python -m backend.execution.orchestrator canary-reconcile --session-id <session-id>
```

`canary-status` only queries the known order. `canary-reconcile` reloads the session and its plan, verifies plan identity, queries the known order, refreshes account/funds/positions/orders/quotes, and persists reconciliation. Neither command calls placement or cancellation.

## 10. Code changes

- `backend/execution/canary.py`: selection, prechecks, price policy, state tracking, one-attempt guard, bounded polling, cancellation protection, reconciliation, persistence, and recovery.
- `backend/execution/__init__.py`: documents the package's single explicitly gated canary write boundary.
- `backend/execution/orchestrator.py`: explicit preflight/execute/status/reconcile CLI routes and snapshot tick-size propagation.
- `backend/execution/runtime.py`: preserves SDK `price_spread` in normalized snapshots.
- `backend/futu/models.py`: adds stable ORDER_BOOK top model, snapshot tick size, and optional order remark.
- `backend/futu/quote_service.py`: ORDER_BOOK subscription and best-ask conversion.
- `backend/futu/order_service.py`: forwards the traceable canary remark through the existing protected simulated-order method.
- `backend/tests/test_canary.py`: 33 focused Mock tests.

No `frontend` file was changed by Phase 2D-B1. Pre-existing unrelated frontend working-tree changes were preserved untouched.

## 11. Validation results

- Python compile/syntax check: PASS (`python -m compileall -q backend`)
- Focused Canary tests: 33/33 PASS
- Full backend Mock suite: 108/108 PASS
- Exact confirmation-cancel path: PASS; mismatched input produced `ABORTED_BY_USER` and zero placement calls
- Context lifecycle: PASS; quote/trade clients are context-managed and the real read-only run closed all opened contexts
- Real OpenD read-only Canary Preflight: executed with both write switches false; `PAUSED` on fresh-data blockers
- Generated read-only session: `canary-13032a5809096bef3e00191a`
- Placement calls during implementation/validation: 0
- Cancellation calls during implementation/validation: 0
- Modification calls during implementation/validation: 0

The ignored `artifacts/` namespace contains the local preflight evidence and is excluded from Git.

## 12. Manual operator command — not executed in this phase

Only after reviewing and resolving every preflight blocker may an operator deliberately enable both switches and start the interactive command:

```powershell
$env:FUTU_MARKET='CN'
$env:FUTU_TRD_ENV='SIMULATE'
$env:FUTU_ENABLE_SIMULATED_ORDERS='true'
$env:EXECUTION_ENABLE_CANARY='true'
python -m backend.execution.orchestrator canary-execute --plan-id plan-5a1633963d613a7a30f64f9a
```

The operator must then inspect the displayed order summary and manually type `EXECUTE ONE-LOT CANARY`. This command was intentionally **not run** during Phase 2D-B1.

## 13. Final status

```text
Canary Orchestrator: PASS
Single-order limit: PASS
Single-lot limit: PASS
Dual safety switches: PASS
Second fresh Precheck: PASS
ORDER_BOOK price checks: PASS
Duplicate-submission protection: PASS
Fill/partial-fill handling: PASS
Timeout cancellation: PASS
Recovery and reconciliation: PASS
Mock unit tests: PASS
Order write operations: NOT EXECUTED
CANARY_IMPLEMENTATION_READY: YES
```

`CANARY_IMPLEMENTATION_READY: YES` means the guarded implementation and Mock validation are complete. It does not mean the currently persisted preflight is executable: that concrete preflight is safely paused until fresh quote and ORDER_BOOK checks pass on a later operator-run preflight.
