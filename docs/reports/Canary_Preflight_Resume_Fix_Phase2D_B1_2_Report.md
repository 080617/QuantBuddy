# QuantBuddy Phase 2D-B1.2 — Canary Read-Only Preflight Resume Fix

Date: 2026-08-06

## 1. Scope and result

This fix changes only the recovery semantics for repeated **read-only** Canary Preflight runs. It does not weaken post-submission idempotency, add a force/retry option, clear existing session data, execute the Canary, or modify the frontend.

The existing session was reused successfully:

```text
Plan ID: plan-5a1633963d613a7a30f64f9a
Session ID: canary-13032a5809096bef3e00191a
```

No second session or order intent was created.

## 2. Confirmed cause

The old condition was:

```python
if existing and (
    existing.order_id
    or existing.place_attempted
    or existing.state not in {
        ABORTED_BY_USER,
        PAUSED,
        FAILED,
    }
):
    raise PlanningError("Existing canary session cannot create another order attempt.")
```

At audit time the persisted artifact was actually in the legacy pre-order state `PREFLIGHT_READY`, with:

```text
place_attempted=false
place_call_count=0
cancel_call_count=0
order_id=null
submitted_at=null
initial_status=null
final_status=null
```

The exception was triggered solely because `PREFLIGHT_READY` was absent from the old three-state allow-list. A read-only refresh was therefore incorrectly classified as a potential new order attempt. A `PAUSED` artifact with the same empty order-history fields was already allowed by that exact expression; the defect affected other valid pre-order states, especially the successful `PREFLIGHT_READY` state.

## 3. New pre-order resume rule

The code now treats session identity, order history, and lifecycle state as separate checks.

A saved Session may resume read-only Preflight only when:

- `session.plan_id` equals the requested plan;
- `plan_digest` is unchanged;
- `plan_source_hash` is unchanged and equals the authoritative artifact source hash;
- `order_id is None`;
- `place_attempted is false`;
- `place_call_count == 0`;
- `submitted_at is None`;
- `initial_status is None`;
- `final_status is None`;
- state is one of the explicit pre-order states:
  - `CREATED`
  - `PRECHECKING`
  - `READY`
  - legacy `PREFLIGHT_READY`
  - `PAUSED`
  - `ABORTED_BY_USER`

`PREFLIGHT_READY` remains readable for backward compatibility, while successful new runs finish in the requested `READY` state. A failed market/account check finishes in `PAUSED`.

## 4. Event and state behavior

For an eligible existing Session:

1. reuse the same `session_id`;
2. set state to `PRECHECKING`;
3. append `PREFLIGHT_STARTED` and persist before external reads;
4. refresh funds, positions, orders, snapshots, ORDER_BOOK, maximum quantity, candidate, blockers, and safe diagnostics;
5. append `PREFLIGHT_COMPLETED`;
6. set `READY` when checks pass or `PAUSED` when blockers remain;
7. atomically persist the same Session.

All prior events remain unchanged in content and order at the start of the event list. Event sequence numbers continue monotonically. No order-history field is reset or rewritten.

## 5. Strong post-order blocking

Repeated Preflight remains forbidden when any of the following is present:

- non-empty `order_id`;
- `place_attempted=true`;
- `place_call_count > 0`;
- non-empty `submitted_at`;
- non-empty `initial_status`;
- non-empty `final_status`;
- a submission, tracking, reconciliation, fill, partial-fill, cancellation, rejection, failure, unknown-review, or completed state;
- changed plan digest or source hash.

Such sessions are directed to `canary-status` or `canary-reconcile`. There is no `--force`, `--retry-order`, `--ignore-session`, or counter/ID reset path.

## 6. Tests

The Canary test suite now contains 50 tests. Added recovery coverage verifies:

1. never-submitted `PAUSED` session can rerun Preflight;
2. same `session_id` is reused;
3. event history is retained and new start/completion events append;
4. no placement call;
5. no cancellation or modify call;
6. `place_call_count` remains zero;
7. no second candidate/session artifact is created;
8. successful recheck becomes `READY`;
9. failed recheck remains `PAUSED`;
10. existing order ID blocks;
11. `place_attempted=true` blocks;
12. positive placement count blocks;
13. changed source hash blocks;
14. completed session blocks;
15. submitted time, initial status, or final status blocks.

The ORDER_BOOK freshness Context lifecycle tests continue to verify one Context, one subscription, correct close on timeout, and no place/cancel/modify call.

Validation results:

```text
Python compile/syntax check: PASS
Canary focused tests: 50/50 PASS
Full backend tests: 137/137 PASS
```

## 7. Read-only integration verification

The requested command was run with both write-switch environment variables removed:

```text
D:\QuantBuddy\.venv-futu\Scripts\python.exe -m backend.execution.orchestrator canary-preflight --plan-id plan-5a1633963d613a7a30f64f9a
```

The command ran at 15:14 Asia/Shanghai, after the continuous auction session. It safely completed the repeated read-only Preflight without the former `Existing canary session cannot create another order attempt` exception.

Because the market was closed, all 10 bounded ORDER_BOOK reads lacked a valid Ask/timestamp and the Session correctly remained:

```text
state=PAUSED
blocker=BEST_ASK_MISSING
```

The same Session retained events 1–5 and appended:

```text
6 PREFLIGHT_STARTED
7 ORDER_BOOK_FRESHNESS_ACQUISITION
8 PREFLIGHT_COMPLETED
```

Order safety evidence after verification:

```text
place_attempted=false
place_call_count=0
cancel_call_count=0
order_id=null
order_id_masked=null
submitted_at=null
initial_status=null
final_status=null
NO ORDER SUBMITTED
NO ORDER MODIFIED
NO ORDER CANCELLED
```

All opened Futu Contexts closed normally.

## 8. Modified files

- `backend/execution/canary.py`
- `backend/tests/test_canary.py`
- `docs/Canary_Preflight_Resume_Fix_Phase2D_B1_2_Report.md`

Phase 2D-B1.1 ORDER_BOOK freshness changes remain in the working tree and were included in the full regression, but this B1.2 fix did not modify frontend files.

## 9. Final status

```text
Repeated read-only Preflight: PASS
Session reuse: PASS
Event history preservation: PASS
Order idempotency protection: PASS
Order write interfaces not called: PASS
Mock unit tests: PASS
Full backend tests: PASS
Read-only Preflight: PAUSED
Order write operations: NOT EXECUTED
CANARY_PREFLIGHT_RESUME_FIXED: YES
```

The final `PAUSED` result is solely the expected post-market ORDER_BOOK blocker. The session-resume defect is fixed.
