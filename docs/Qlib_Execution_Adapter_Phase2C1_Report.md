# QuantBuddy Qlib Execution Adapter Phase 2C.1 Report

Date: 2026-08-05

Scope: refresh the frozen research data, reuse the trained LightGBM model, resolve T+1, and produce a read-only initial-deployment dry-run plan.
Order guarantee: **NO ORDER SUBMITTED / NO ORDER MODIFIED / NO ORDER CANCELLED**.

## 1. Audit and authoritative inputs

- Existing normalized CSI300 source before refresh: `data/normalized/qlib_csv`, 300 constituents plus benchmark.
- Existing Qlib calendar before refresh: `data/qlib/cn_data/calendars/day.txt`, ending 2026-07-30.
- Reused trained model: `outputs/backtest/v2/trained_model.pkl`.
- Source recorder: `eafb4f0170a14278b354b8088e96e57c`.
- Frozen task: `outputs/backtest/v2/task_config.json`, `LGBModel` + `Alpha158` + `csi300` + `TopkDropoutStrategy(topk=5,n_drop=1,risk_degree=0.95)`.
- Refresh entry: `scripts/12_refresh_qlib_market_data.py`.
- Inference-only entry: `scripts/13_generate_qlib_forward_signal.py`.
- Execution artifact entry: `backend.execution.artifact_loader.export_execution_artifact`.

No model training was performed. The saved LightGBM model was loaded with `pickle` and used only for `model.predict(...)` on the refreshed DatasetH segment.

## 2. Market-data refresh

- Data source: the existing Tencent/AKShare source family used by the project.
- Trusted anchor: the local files had already reached 2026-08-04 when the final atomic refresh started.
- Latest complete cross-section: **2026-08-05**.
- Coverage: **300/300** constituents; required threshold was 270/300.
- Appended on the final pass: 300 stock rows.
- Four STAR-market securities returned no separate `hfqday`; Tencent explicitly returned only `day`. The refresh uses that provider response as the identical adjusted series and does not invent an adjustment.
- Audit manifest: `outputs/market_refresh/2026-08-05/refresh_manifest.json` (ignored runtime artifact).
- Qlib binary features were updated successfully using the existing `scripts/dump_bin.py dump_update` pipeline.

## 3. Frozen trading calendar and execution date

- Calendar source: FutuOpenD read-only `TradeDateMarket.CN` query.
- Export entry: `scripts/14_export_futu_cn_calendar.py`.
- The returned calendar was overlap-checked against the Tencent CSI300 benchmark before extension.
- Signal date: **2026-08-05**.
- Next CN trading session: **2026-08-06**.
- Planned execution date: **2026-08-06**.
- Rule: T close signal -> the next entry in the verified trading calendar. No natural-day addition is used; weekend behavior is covered by tests.

## 4. Latest inference artifact

- Forward output: `outputs/forward/v1/`.
- Model SHA-256: `409e7402c700453b168928fc9b1bf1fd3c3aa27649870bc5f61330aa203a2d7e`.
- Execution artifact: `outputs/execution_artifacts/strategy-hs300-lightgbm-top5_2026-08-05_b4864dd7b4af.json`.
- Source hash: `b4864dd7b4af253ec0baaa06c4d90b2130a402924e958aa73dd61fd6aff1d9ac`.
- `is_mock=false`, `inference_only=true`, `retrained=false`, `data_as_of=2026-08-05`.
- Top-5: SZ000988, SZ002837, SH600460, SH600176, SZ000657.
- Verified target weight: **19% each**, total deployment 95%, cash reserve 5%.

The 19% weights are not an arbitrary equal-weight assumption. They are derived from the frozen Qlib TopkDropout initial-entry semantics: the empty portfolio buys five names and allocates `cash * risk_degree` across the five newly bought names (`0.95 / 5`). The artifact persists and validates the weights.

## 5. INITIAL_DEPLOYMENT versus REBALANCE

`backend/execution/order_planner.py` now selects `INITIAL_DEPLOYMENT` only when all required conditions hold: no strategy/account holdings, no unfinished orders, CN + SIMULATE + ACTIVE account, positive cash, allow-listed strategy, and a valid non-stale artifact. Otherwise the plan uses `REBALANCE`.

All existing constraints remain: long-only, no margin, no short sale, valid positive quotes, no suspension, board lots, maximum cash-buy quantity, cash reserve, maximum positions, unfinished-order blocking, and dry-run-only enforcement.

## 6. Safety-limit layering

The previous plan `plan-0220c57a32e2234120507fae` attempted to deploy approximately 93.87% of a 1,000,000 CNY empty account while applying routine rebalance caps:

- 100,000 CNY single-order cap, while each initial target is approximately 190,000 CNY;
- 500,000 CNY daily cap, while total target deployment is 950,000 CNY;
- 50% turnover cap, while initial deployment is approximately 95% before board-lot rounding.

For a verified initial deployment, the applied limits are derived from the artifact and account assets:

- single-name limit: `1,000,000 * max(target_weight)` = **190,000 CNY**;
- total plan limit: `1,000,000 * sum(target_weights)` = **950,000 CNY**;
- turnover limit: `sum(target_weights)` = **0.95**;
- cash reserve: `1 - risk_degree` = **5% / 50,000 CNY**;
- maximum positions: **5**.

Routine `REBALANCE` limits remain unchanged: 100,000 CNY per order, 500,000 CNY per day, and 0.50 turnover.

## 7. Actual read-only Futu plan

- Plan ID: `plan-5a1633963d613a7a30f64f9a`.
- Mode: `INITIAL_DEPLOYMENT`.
- Account: CN / SIMULATE / ACTIVE; masked identifier only.
- Cash / assets before: 1,000,000 CNY / 1,000,000 CNY.
- Current holdings: empty.
- Unfinished orders: none.
- Planned buys after board-lot rounding:
  - SZ000988: target 19% / 190,000; 1,800 shares; 100-share lot; estimated 180,774 CNY.
  - SZ002837: target 19% / 190,000; 3,600 shares; 100-share lot; estimated 188,388 CNY.
  - SH600460: target 19% / 190,000; 6,200 shares; 100-share lot; estimated 189,844 CNY.
  - SH600176: target 19% / 190,000; 4,800 shares; 100-share lot; estimated 188,544 CNY.
  - SZ000657: target 19% / 190,000; 3,300 shares; 100-share lot; estimated 189,519 CNY.
- Estimated buy value: 937,069 CNY before fees.
- Estimated turnover: 0.937069.
- Reserved cash: 50,000 CNY.
- Estimated cash after fees: 62,462.4655 CNY.
- Warnings: only the existing backtest-close/reference-price semantic warning.
- Blockers: `[]`.
- `dry_run=true`; `executable=true`.

Runtime files are under `artifacts/execution_plans/` and remain ignored by Git.

## 8. Verification

- Python syntax/bytecode check: PASS.
- Mock/unit tests: **48 passed**.
- Tests cover initial/rebalance classification, unfinished-order rejection, stale signals, exact next trading session, weekend handling, derived deployment limits, unchanged rebalance limits, single-name limit, board lots, cash reserve, deterministic plan IDs, and the existing runtime guarantee that no order-write method is referenced.
- Futu read-only integration plan: PASS.
- OpenD contexts were closed normally.
- `FUTU_ENABLE_SIMULATED_ORDERS=false` during calendar and planning runs.

## 9. Modified source files

- `backend/execution/artifact_loader.py`
- `backend/execution/models.py`
- `backend/execution/order_planner.py`
- `backend/execution/signal_validator.py`
- `backend/tests/execution_test_helpers.py`
- `backend/tests/test_order_planner.py`
- `backend/tests/test_signal_validator.py`
- `scripts/12_refresh_qlib_market_data.py`
- `scripts/13_generate_qlib_forward_signal.py`
- `scripts/14_export_futu_cn_calendar.py`

No file under `frontend/` was modified by Phase 2C.1.

## 10. Final decision

- 行情数据刷新：PASS
- 最新信号生成：PASS
- 冻结交易日历：PASS
- 执行日期解析：PASS
- 初始建仓模式：PASS
- 安全阈值分层：PASS
- Dry-Run Plan：PASS
- Plan executable：TRUE
- Mock 单元测试：PASS
- Futu 只读测试：PASS
- 订单写操作：NOT EXECUTED
- READY_FOR_SIMULATED_EXECUTION_ORCHESTRATOR：YES

This report does not authorize order execution. Phase 2C.1 stops at the executable dry-run plan.
