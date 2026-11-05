# QuantBuddy Phase 3B — Futu Simulated Trading Frontend

Date: 2026-08-09  
Scope: read-only Futu simulated-account monitoring UI

## 1. Frontend audit

The formal application already used the shared App Router shell at `frontend/src/app/(app)/layout.tsx`, with `AppShell` and `PrimaryNav`. The Sidebar already contained a `/paper` navigation item and `/paper` existed as a placeholder route. Phase 3B replaces that placeholder instead of creating a competing route or shell.

The page reuses the existing QuantBuddy visual language from Workspace, Backtest, and Community: shared Sidebar, page width, typography, pale canvas, white cards, borders, rounded corners, purple actions, badges, tables, loading/error treatment, and existing responsive breakpoints.

## 2. Files changed for Phase 3B

- `frontend/src/app/(app)/paper/page.tsx` — replaces the placeholder with the formal simulated-account page.
- `frontend/src/components/paper/paper-trading-page.tsx` — read-only portfolio UI, loading, disconnected, empty, table, and refresh states.
- `frontend/src/components/paper/paper-trading-model.ts` — display formatting, order translations, connection interpretation, and masked-ID defense.
- `frontend/src/components/paper/paper-trading-page.test.tsx` — component and interaction tests.
- `frontend/src/services/futu-service.test.ts` — GET-only service-boundary tests.
- `frontend/src/components/layout/primary-nav.tsx` — retains the existing route order and labels the product entry “我的 Quant Buddy”.
- `frontend/src/app/globals.css` — page styles within the existing `qb-*` visual system.
- `frontend/vitest.config.ts` — includes TSX component tests.
- `frontend/package.json` and `frontend/pnpm-lock.yaml` — Testing Library and jsdom development dependencies only.

Phase 3A's `frontend/src/types/futu.ts` and `frontend/src/services/futu-service.ts` remain the only frontend Futu data boundary. The page component does not call `fetch` directly.

## 3. Route and layout

- Formal route: `/paper`
- Shared App Shell: reused
- Shared Sidebar: reused
- Navigation order: 首页 → 我的策略 → 回测研究 → 模拟盘 → 社区 → 我的 Quant Buddy → 设置
- Desktop-first layout: cards and tables fit within the existing application width; tables scroll inside their own containers on narrow screens rather than overflowing the page.

## 4. Portfolio UI

The page loads `GET /api/futu/portfolio` through `futuService.getPortfolio()` and renders:

- connection badge: 连接正常 / 未连接
- A股 and 模拟账户 badges
- total assets
- cash
- position market value
- current position count
- account type
- market and environment
- account status
- FutuOpenD status
- masked account identifier only

No asset amount is hardcoded. Currency values are formatted as CNY from the API response.

## 5. Positions and orders

The positions table supports stock name, code, quantity, sellable quantity, current price, cost price, market value, P/L, and return percentage. An empty positions response displays the approved “暂无持仓” state instead of an empty table.

The recent-orders table supports stock, side, translated status badge, quantity, order price, dealt quantity, dealt average price, time, and masked order ID. Known statuses are translated for the UI while raw status values remain unchanged in the service data.

The page never supplies demo positions or orders. If the real API returns empty arrays, it displays the corresponding empty state.

## 6. Strategy execution display

The read-only “策略执行” card displays the current QuantBuddy strategy and “已连接模型”. Automatic trading is explicitly marked “未启用”. “查看最新计划” is disabled and accompanied by “交易执行功能将在下一阶段开放”. No execution-plan API or trading HTTP route was added.

## 7. Loading, refresh, and errors

- First entry automatically loads the portfolio once.
- “刷新数据” calls `futuService.getPortfolio()` again.
- Refresh shows a loading state and does not poll automatically.
- Backend errors and disconnected OpenD responses render a stable “富途连接不可用” state with startup guidance and a retry button.
- Exceptions and stack traces are not exposed in the UI.

## 8. Security boundary

- The component imports only the Phase 3A read-only `FutuService` interface.
- The frontend service exposes exactly five `get*` methods.
- All Futu HTTP requests use `GET`.
- No POST, order placement, cancellation, modification, Canary, rebalance, or execution call exists in the page.
- A second UI-side safeguard replaces any identifier that is not already masked with `****`.
- Tests verify that a full account identifier is never rendered.
- `NEXT_PUBLIC_BACKEND_URL` remains centralized in `futu-service.ts`; components contain no backend URL.
- `.env.local` remains ignored and was not modified.

## 9. Automated tests

Phase 3B adds coverage for:

1. successful portfolio load;
2. empty positions;
3. populated positions;
4. historical orders and translated status;
5. backend unavailable;
6. Futu disconnected;
7. refresh requests the service a second time;
8. full account ID is not rendered;
9. the frontend service exposes no write request.

Final frontend suite:

- Test files: 3 passed
- Tests: 20 passed
- Phase 3B component tests: 6 passed
- Phase 3B service tests: 2 passed

## 10. Engineering verification

- TypeScript (`tsc --noEmit`): PASS
- ESLint: PASS
- Frontend tests: PASS, 20/20
- Next.js production build: PASS
- `/paper` production route: generated successfully

## 11. Real read-only full-chain smoke test

With FutuOpenD logged in, the local FastAPI backend and Next.js frontend were started together. Host-level HTTP verification confirmed:

- `/paper`: HTTP 200
- `/api/futu/portfolio`: connected=true
- market: CN
- environment: SIMULATE
- account type: CASH
- masked account ID: confirmed
- total assets and cash: present from the real API
- current positions: returned by the real API (empty at verification time)
- recent orders: returned by the real API (empty at verification time)

The in-app browser runs in an isolated network environment and could not access the Windows host loopback address; Chrome and Edge automation connections were unavailable. Therefore visual browser automation could not be used for the localhost page. This does not affect the host HTTP result, jsdom interaction coverage, or production build, but it is recorded here for audit transparency.

No mock portfolio was used for the real HTTP verification. No order was submitted, modified, or cancelled.

## 12. Final assessment

- 模拟盘 Route：PASS
- Futu Portfolio UI：PASS
- 真实账户资产：PASS
- 持仓 UI：PASS
- 订单 UI：PASS
- 连接状态：PASS
- 错误状态：PASS
- 刷新功能：PASS
- 敏感信息保护：PASS
- TypeScript：PASS
- ESLint：PASS
- Frontend Tests：PASS
- Production Build：PASS
- 真实全链路 Smoke Test：PASS（host HTTP + real Futu API；浏览器自动化环境限制已记录）
- 订单写操作：NOT EXPOSED
- READY_FOR_DEMO：YES

Phase 3B ends here. Canary, order execution, cancellation, modification, automatic rebalancing, and Qlib training remain out of scope and were not run.
