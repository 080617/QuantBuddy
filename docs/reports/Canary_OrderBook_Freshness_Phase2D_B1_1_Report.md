# QuantBuddy Phase 2D-B1.1 — Canary ORDER_BOOK Freshness Acquisition

Date: 2026-08-06

## 1. Scope and outcome

This hotfix repairs the read-only acquisition of a fresh ORDER_BOOK best ask for the existing controlled simulated Canary flow. It does not alter the 15-second freshness requirement, use a snapshot/last-price fallback, enable order writes, modify the frontend, or execute the Canary.

Final result:

```text
Session: canary-13032a5809096bef3e00191a
State: PREFLIGHT_READY
Blockers: []
place_attempted: false
place_call_count: 0
cancel_call_count: 0
order_id: null
```

`PREFLIGHT_READY` is the existing Canary state enum corresponding to a successful read-only preflight.

## 2. Confirmed root cause

The previous implementation in `backend/futu/quote_service.py` performed exactly this sequence:

```text
subscribe ORDER_BOOK once
immediately call get_order_book once
return that first cached payload
```

There was no wait for the subscription cache to receive a timestamped push and no second read. The existing Canary validator correctly rejected a missing or older-than-15-seconds `svr_recv_time_ask` as `ORDER_BOOK_STALE`.

The cause was confirmed against the SDK rather than inferred. At 2026-08-06 13:58:38 Asia/Shanghai, a read-only subscribe followed by an immediate read returned:

```text
subscribe_rc: 0
book_rc: 0
Ask present: true
best ask: 102.20
svr_recv_time_ask: ""
```

Therefore the price itself was valid while the first cached payload had no server ask timestamp. The previous single-read flow had no safe way to establish freshness and correctly paused.

## 3. Bounded freshness acquisition

`QuoteService.acquire_fresh_order_book_top` now:

1. validates the Futu code;
2. subscribes to ORDER_BOOK exactly once;
3. keeps the same Quote Context open;
4. reads at most 10 times;
5. waits one second between unsuccessful reads;
6. stops within the configured 10-second acquisition window;
7. interprets naive Futu server timestamps as Asia/Shanghai;
8. accepts a result only when Ask is present, best ask is positive, timestamp exists and parses, and absolute age is no more than 15 seconds;
9. returns no order book if the bounded acquisition cannot prove freshness.

The method performs no high-frequency loop and has no infinite retry path. It never calls `get_snapshot`, reads `last_price`, or uses snapshot ask data as a fallback.

## 4. Diagnostics

The persisted Canary Session now includes the requested safe fields:

- `subscription_succeeded`
- `order_book_attempt_count`
- `first_order_book_ask_time`
- `final_order_book_ask_time`
- `final_order_book_age_seconds`
- `best_ask`
- `freshness_threshold_seconds`
- `acquisition_timeout_seconds`

When the first result has no timestamp or more than one attempt is needed, the session records an `ORDER_BOOK_FRESHNESS_ACQUISITION` diagnostic event. No account identifier is added to this diagnostic.

Old Canary Session JSON remains loadable because the new diagnostic object is optional during deserialization.

## 5. Context lifecycle

- The bounded loop reuses the Quote Context supplied to one `QuoteService` instance.
- One symbol is subscribed exactly once.
- No retry creates another Quote Context.
- The surrounding `with FutuClient()` remains open through acquisition and the best-ask-based maximum-buy refresh.
- Quote and Trade Contexts close after success or timeout.
- The Trade Context safety behavior is unchanged.

## 6. Strict failure behavior

If all attempts lack a timestamp or remain older than 15 seconds:

- no fresh `OrderBookTop` is returned;
- the safe diagnostic retains the final SDK observations;
- Canary Preflight emits `ORDER_BOOK_STALE` when a positive ask exists but freshness is unproven;
- state remains `PAUSED`;
- no alternate symbol or price source is selected;
- no order operation occurs.

An empty Ask or non-positive best ask emits `BEST_ASK_MISSING`; it is never replaced with a snapshot price.

## 7. Mock tests

New focused tests cover all requested scenarios:

1. first timestamp missing, second fresh: PASS;
2. first timestamp stale, later fresh: PASS;
3. all 10 attempts without a timestamp: PASS;
4. empty Ask cannot pass: PASS;
5. invalid best ask cannot pass: PASS;
6. 16-second-old ask cannot pass the 15-second threshold: PASS;
7. no snapshot/last-price fallback: PASS;
8. waiting reuses one Quote Context: PASS;
9. ORDER_BOOK subscription occurs once: PASS;
10. timeout closes the Context: PASS;
11. no `place_order`: PASS;
12. no cancel or `modify_order`: PASS.

The Canary suite also verifies that diagnostics persist in session JSON and create the safe acquisition event.

Validation totals:

- Python compilation/syntax check: PASS
- ORDER_BOOK freshness tests: 12/12 PASS
- Canary tests: 35/35 PASS
- Full backend suite: 122/122 PASS

## 8. Final read-only Preflight

Command executed with `FUTU_ENABLE_SIMULATED_ORDERS` and `EXECUTION_ENABLE_CANARY` absent from the process environment:

```text
D:\QuantBuddy\.venv-futu\Scripts\python.exe -m backend.execution.orchestrator canary-preflight --plan-id plan-5a1633963d613a7a30f64f9a
```

Observed acquisition:

```json
{
  "subscription_succeeded": true,
  "order_book_attempt_count": 3,
  "first_order_book_ask_time": null,
  "final_order_book_ask_time": "2026-08-06 14:17:33.356",
  "final_order_book_age_seconds": 1.69216,
  "best_ask": 101.33,
  "freshness_threshold_seconds": 15,
  "acquisition_timeout_seconds": 10
}
```

Additional read-only result:

- code: `SZ000988`;
- canary quantity: 100 shares / one current lot;
- maximum cash-buy quantity at the best ask: 9,800 shares;
- estimated one-lot amount: CNY 10,133.00;
- blockers: none;
- state: `PREFLIGHT_READY`;
- all opened Futu contexts closed normally.

## 9. Modified files

- `backend/futu/models.py`
- `backend/futu/quote_service.py`
- `backend/execution/canary.py`
- `backend/tests/test_canary.py`
- `backend/tests/test_order_book_freshness.py`
- `docs/Canary_OrderBook_Freshness_Phase2D_B1_1_Report.md`

No frontend file was modified in Phase 2D-B1.1.

## 10. Final status

```text
ORDER_BOOK subscription: PASS
Bounded wait: PASS
Strict 15-second threshold: PASS
No silent price fallback: PASS
Context management: PASS
Mock unit tests: PASS
Read-only Preflight: PASS
Order write operations: NOT EXECUTED
CANARY_PREFLIGHT_READY: YES
```

No `canary-execute` command was run. No order was submitted, modified, or cancelled.
