# QuantBuddy Qlib Execution Adapter Phase 2C Report

## 1. Scope and outcome

Phase 2C adds a backend-only Qlib-to-Futu execution adapter that exports and validates a traceable Qlib artifact, reads the existing protected Futu CN SIMULATE service, reconciles holdings, and produces an auditable **Dry-Run Execution Plan**. It contains no order submission, modification, cancellation, REAL environment, frontend, or model-training flow.

The current backend Qlib signal is dated **2026-07-30**. On the validation date **2026-08-05**, it is six calendar days old, exceeds the conservative three-day freshness limit, and the frozen Qlib calendar contains no later session. The live read-only plan is therefore correctly persisted as `executable=false` and is not eligible for orchestration.

## 2. Authoritative Qlib output audit

The authoritative machine-readable source is the backend Qlib recorder export, not `frontend/public/data`:

- `outputs/backtest/v2/predictions.csv`: complete scored and ranked prediction output; latest date 2026-07-30.
- `outputs/backtest/v2/top5_predictions.csv`: Top-5 display/extract evidence.
- `outputs/backtest/v2/task_config.json`: frozen model, feature set, universe, strategy, risk and fee configuration.
- `outputs/backtest/v2/artifact_manifest.json`: recorder identity `eafb4f0170a14278b354b8088e96e57c`.
- `data/qlib/cn_data/calendars/day.txt`: execution calendar.
- `data/qlib/cn_data/instruments/csi300.txt`: dated CSI300 universe membership.

`scripts/11_build_frontend_dashboard_data.py` consumes backend backtest exports to create display JSON under `outputs/frontend/dashboard_v1`, which is then mirrored into `frontend/public/data/dashboard_v1`. The validator explicitly rejects frontend display paths and Mock artifacts as execution sources.

No model was retrained. `backend/execution/artifact_loader.py` normalizes the existing backend outputs into ignored `outputs/execution_artifacts/`, records source paths, generation time, signal date, strategy metadata, recorder ID, configuration hash and aggregate source hash, and refuses a conflicting overwrite.

Validated artifact:

- Schema: `quantbuddy.execution-artifact.v1`
- Strategy: `strategy-hs300-lightgbm-top5`
- Source hash: `02ac5daa74511ed0bfa7e0cc7410292ee6b4ec2c413edf84bfa4fe74f910518f`
- Signal date: `2026-07-30`
- Model / feature set / universe: `LGBModel / Alpha158 / csi300`
- Strategy: `TopkDropoutStrategy`, `topk=5`, `n_drop=1`, `risk_degree=0.95`, `only_tradable=true`

## 3. Frozen strategy and weight semantics

The semantics were derived from `configs/07_lightgbm_alpha158_csi300.yaml`, the exported `task_config.json`, and Qlib 0.9.7 `TopkDropoutStrategy` behavior:

- The signal used for a trade step is the previous Qlib trade-step signal (`shift=1`).
- Membership is Top-5 with at most one dropout/replacement per step (`n_drop=1`).
- Unsold holdings are retained at their existing quantities; the whole portfolio is **not** rebalanced to equal weights.
- Selected exits are full exits, subject to actual sellable quantity.
- Only newly bought names split post-sell cash multiplied by `risk_degree=0.95`.
- The remaining 5% is reserved cash.
- Qlib backtest pricing is next-step `close`; live current snapshots are only planning references and are explicitly warned as different semantics.
- Open/close cost and minimum fee are included conservatively in the Dry-Run cash calculation.

The adapter does not guess equal weights, full-investment weights, or a rank-6 substitution rule.

## 4. Implemented structure

```text
backend/execution/
├── __init__.py              # Package boundary; exposes data models only.
├── exceptions.py            # Artifact and planning domain errors.
├── models.py                # Stable JSON-serializable artifact, account, reconciliation, order and plan models.
├── artifact_loader.py       # Backend Qlib export normalization and traceability hashes.
├── signal_validator.py      # Trust, schema, universe, calendar, freshness and source-integrity validation.
├── target_portfolio.py      # TopkDropout membership transition without invented weights.
├── reconciliation.py        # KEEP / EXIT / ENTER / UNMANAGED classification.
├── safety.py                # Independent CN, SIMULATE, ACTIVE, dry-run and risk-limit gate.
├── order_planner.py         # Sell-first, lot-size, cash, fee and maximum-quantity planning.
├── persistence.py           # Non-overwriting JSON and Markdown plan persistence.
├── runtime.py               # Existing Futu Service read-only orchestration.
└── cli.py                   # audit-artifacts, plan and show commands; no execute command.
```

Added tests:

- `backend/tests/execution_test_helpers.py`
- `backend/tests/test_execution_artifact_loader.py`
- `backend/tests/test_signal_validator.py`
- `backend/tests/test_target_portfolio.py`
- `backend/tests/test_reconciliation.py`
- `backend/tests/test_order_planner.py`
- `backend/tests/test_execution_safety.py`
- `backend/tests/test_execution_runtime.py`

No formal `frontend` file was changed by Phase 2C. Pre-existing uncommitted frontend/Phase 1D-B changes were preserved and left untouched.

## 5. Data flow

```text
backend Qlib recorder exports
  -> artifact_loader (normalize + hash)
  -> signal_validator (source/schema/universe/calendar/freshness)
  -> target_portfolio (TopkDropout membership transition)
  -> existing backend.futu services (CN SIMULATE reads only)
  -> reconciliation
  -> order_planner + independent safety gate
  -> artifacts/execution_plans/<plan_id>.json and .md
```

The runtime reuses `backend.futu.FutuClient`, `AccountService`, `QuoteService`, `OrderService`, and the existing strict Qlib/Futu code mapper. It does not create a second Futu client or account-selection implementation.

## 6. Reconciliation and planning constraints

The plan distinguishes managed holdings from unrelated account holdings and classifies KEEP, EXIT, ENTER and UNMANAGED states. Unmanaged positions block execution because strategy capital isolation is unknown. Relevant unfinished orders also block execution.

Planning protections include:

- CN, SIMULATE and ACTIVE account only.
- Explicit strategy allow-list.
- `dry_run=True` required.
- Long-only BUY/SELL transitions; no shorting or financing.
- Sell quantity never exceeds `can_sell_qty`.
- Buy quantities round down to positive board lots.
- Current snapshots must provide positive price and valid lot size.
- Suspended or missing-price securities are blocked; rank 6 is not substituted.
- Dedicated maximum cash-buy quantity is queried for every planned buy.
- Sell proceeds are estimated first, but buys are labeled `BUY_AFTER_SELL_CONFIRMATION`.
- 5% cash reserve, configured fees, maximum single-order value, daily planned value, turnover and position-count limits.
- Conservative defaults: signal age 3 calendar days, CNY 100,000 per order, CNY 500,000 daily planned amount, 50% turnover, five positions.

## 7. Idempotence and auditability

`plan_id` is a SHA-256-derived stable identifier over strategy, signal date, source hash, validated execution context, masked account snapshot, positions, recent orders, quotes, maximum tradable quantities, managed codes and planning configuration. Tests verify identical inputs produce the same `plan_id` and byte-stable serialized meaning.

Plans are saved under ignored `artifacts/execution_plans/` as JSON plus a readable Markdown summary. Existing files are accepted only if identical; a different payload with the same ID is refused. Every summary states:

`DRY RUN / NO ORDER SUBMITTED / NO ORDER MODIFIED / NO ORDER CANCELLED`

## 8. Mock test results

Commands:

```text
.venv-futu\Scripts\python.exe -m compileall -q backend\execution backend\tests
.venv-futu\Scripts\python.exe -m unittest discover -s backend\tests -p "test_*.py"
```

Result: **PASS — 43 tests passed**.

Coverage includes missing artifact fields/sources, frontend/Mock rejection, stale signal, missing next calendar date, duplicate/illegal/out-of-universe codes, invalid strategy semantics, code mapper reuse, TopkDropout transitions, reconciliation, board-lot rounding, below-one-lot, sellable quantity, suspension, missing price, maximum buy, cash/fee behavior, unfinished orders, order/daily/turnover limits, REAL/non-CN/inactive rejection, dry-run enforcement, stable plan IDs, non-overwriting persistence, stable JSON, context closure, and a runtime mock that exposes only read methods.

## 9. Futu read-only plan test

The live integration command used the running local FutuOpenD with `FUTU_ENABLE_SIMULATED_ORDERS=false`. It read the unique masked ACTIVE CN SIMULATE account, funds, positions, recent orders, Top-5 snapshots, lot sizes and maximum cash-buy quantities. Both quote and trade contexts reported `CallClose` after completion.

Observed final plan characteristics (sensitive identifiers remain masked):

- Market / environment: `CN / SIMULATE`
- Account: masked only
- Cash: CNY 1,000,000; positions: none
- Candidate transition: five buys, zero sells
- Dry run: `true`
- Executable: `false`
- Planned execution date: unresolved because the frozen calendar has no session after 2026-07-30
- Required blockers: `STALE_SIGNAL`, `EXECUTION_DATE_NOT_IN_CALENDAR`
- Additional conservative blockers: five `SINGLE_ORDER_LIMIT_EXCEEDED`, `DAILY_PLAN_LIMIT_EXCEEDED`, `TURNOVER_LIMIT_EXCEEDED`

The additional blockers are expected: an empty CNY 1,000,000 account combined with Qlib's 95% risk degree would otherwise produce roughly 19% allocations for each of five new names, exceeding the conservative Phase 2C risk caps. The planner reports these candidates for audit but never submits them.

Static inspection of `backend/execution` found no call to Futu order placement or cancellation/modification methods. The CLI has no `--execute` option.

## 10. Deliberate blockers and next-phase readiness

The adapter foundation is complete, but current live data is not safe for an execution orchestrator:

1. The authoritative signal is stale as of 2026-08-05.
2. There is no frozen Qlib calendar session after the signal date, so the adapter leaves `planned_execution_date` unresolved rather than inventing a date.
3. The candidate plan exceeds conservative order, daily amount and turnover caps.
4. Phase 2C intentionally has no order state machine, confirmation workflow, or write path.

A future phase must first generate a fresh, authoritative forward artifact with a valid next trading session and explicitly resolve approved risk caps. This does not require changing the verified TopkDropout semantics.

## 11. Final assessment

- Qlib 权威输出识别：**PASS**
- 策略权重语义：**PASS**
- Execution Artifact：**PASS**
- 持仓对账：**PASS**
- 整手与现金约束：**PASS**
- 安全保护：**PASS**
- 幂等计划：**PASS**
- Mock 单元测试：**PASS**
- Futu 只读计划测试：**PASS**
- 订单写操作：**NOT EXECUTED**
- READY_FOR_SIMULATED_EXECUTION_ORCHESTRATOR：**NO**
