# QuantBuddy Backtest Phase 1D-B Completion Report

## 1. 阶段结论

- 项目根目录：`D:\QuantBuddy`
- 正式前端：`D:\QuantBuddy\frontend`
- 完成日期：2026-08-04
- 本阶段仅完成正式 `/backtest` 的“最新模型信号”和“历史操作预览”。
- 未修改任何离线 HTML、Qlib JSON、Dashboard 数据生成脚本、Workspace、Community、Onboarding、首页、模拟盘、QuantBuddy AI 或 Sidebar。

## 2. 修改文件

1. `frontend/src/types/dashboard.ts`
   - 沿用既有 `LatestSignals`、`Signal`、`OperationPreview`、`OperationCandidate` 类型。
   - 允许买入/卖出候选为 `null`，并允许候选排名、分数缺失，避免为无操作数据构造交易。
2. `frontend/src/services/dashboard-adapter.ts`
   - 完善操作候选的空值适配。
3. `frontend/src/services/dashboard-service.ts`
   - 正式公开 `getOperationPreview()`；信号继续通过 `getLatestSignals()` 返回。
4. `frontend/src/services/backtest-insights-service.ts`（新增）
   - 组合正式 DataService、独立区块状态和 Workspace 回测上下文保护。
5. `frontend/src/components/backtest/backtest-context-page.tsx`
   - 仅在 `ready` 上下文加载信号和操作预览。
6. `frontend/src/components/backtest/backtest-research.tsx`
   - 按验收顺序插入两个历史研究区块。
7. `frontend/src/components/backtest/backtest-research-insights.tsx`（新增）
   - 实现信号表格、操作候选关系和 loading/empty/error UI。
8. `frontend/src/app/globals.css`
   - 延续现有 `qb-*` 回测视觉语言并增加窄屏布局。
9. `frontend/src/services/integration-repair.test.ts`
   - 在 Phase 1C 测试基础上新增 Phase 1D-B 验收场景。
10. `docs/Backtest_Phase1D_B_Completion_Report.md`（本报告）

## 3. 最新模型信号实现

正式页面展示：

- 实际信号日期；
- Top-5 排名；
- 股票代码与股票名称；
- 模型分数；
- 分数百分位；
- 当前是否持有；
- “历史模型输出”状态标签。

文案明确使用“历史模型信号”和“历史研究展示”，没有使用“实时信号”“今日推荐”或“投资建议”。Top-5 股票未写入 React 组件。

## 4. 历史操作预览实现

正式页面展示：

- 操作类型；
- 操作标签；
- 卖出候选；
- 买入候选；
- 原始说明；
- `previewOnly` 状态；
- “历史预览”和“非真实订单”标签。

卖出候选保持在左、买入候选保持在右；窄屏时上下排列。候选为空时显示“无卖出候选”或“无买入候选”，不会构造虚假交易。

## 5. 正式数据流

```text
frontend/public/data/dashboard_v1/latest_signals.json
frontend/public/data/dashboard_v1/operation_preview.json
  -> dashboard-adapter
  -> dashboardService
  -> dataService
  -> backtest-insights-service
  -> BacktestContextPage（仅 ready）
  -> BacktestResearchInsights
  -> /backtest
```

页面组件没有直接导入或读取 JSON，也没有建立第二套信号/操作领域类型。

## 6. 策略 ID 上下文保护

保留 Phase 1C 的三种状态：

- `ready`：渲染回测数据，并通过正式 DataService 加载信号与操作预览；
- `not_backtested`：不调用信号或操作预览 Service，不显示基准研究数据；
- `not_found`：不调用信号或操作预览 Service，不显示基准研究数据。

`/backtest` 未带 ID 时继续解析绑定 `dashboard_v1` 的默认基准策略。草稿、Community Fork、待重新回测策略不会继承基准信号或基准操作预览。

## 7. Loading、Empty 与 Error

两个区块分别支持：

- `loading`：显示正在加载对应历史研究数据；
- `empty`：空信号数组或完全无操作内容时显示真实空状态；
- `error`：单个 Service 失败时只显示对应区块错误，不伪造回退数据；
- `ready`：展示正式适配后的数据。

路由级 `loading.tsx` 和 `error.tsx` 继续保留，用于整个回测路由的加载与异常边界。

## 8. 自动化测试

执行：`pnpm test`

结果：

```text
Test Files  1 passed (1)
Tests       12 passed (12)
```

新增测试覆盖：

1. 信号数据由正式 Dashboard Service 返回；
2. Top-5 股票代码未硬编码到 React 组件；
3. 操作预览正确返回 `previewOnly: true`；
4. `ready` 策略可读取信号与操作预览；
5. `not_backtested` 不调用基准信号 Service；
6. `not_found` 不调用基准操作预览 Service；
7. 空信号与无操作内容可进入空状态。

原 Phase 1C 的 7 项测试继续通过。

自动化测试：**PASS**

## 9. 工程检查

执行目录：`D:\QuantBuddy\frontend`

| 命令 | 结果 |
|---|---|
| `pnpm exec tsc --noEmit` | PASS，退出码 0 |
| `pnpm lint` | PASS，退出码 0，无 error/warning |
| `pnpm test` | PASS，12/12 |
| `pnpm build` | PASS，Next.js 16.2.12 production build 成功，24 个路由生成完成 |

工程检查：**PASS**

## 10. HTTP Smoke Test

使用临时 production server 执行，完成后已停止。

| 路由 | HTTP | 响应字节 |
|---|---:|---:|
| `/backtest` | 200 | 102969 |
| `/backtest?id=strategy-hs300-lightgbm-top5` | 200 | 103101 |
| `/backtest?id=missing-strategy` | 200 | 103053 |
| `/strategy` | 200 | 18362 |
| `/community` | 200 | 17589 |

Workspace/localStorage 的分支行为由 Vitest 内存 Storage 场景验证。

## 11. 最终判定

### 我的策略：COMPLETE

Phase 1C 已完成 Workspace CRUD、回测引用、Community 双向联动、创建预选和因子集完整性校验；本阶段未修改该模块。

### 回测研究：COMPLETE

正式回测页现在具备策略上下文保护、Qlib 历史回测数据、最新历史模型信号、历史操作预览、持仓和风险披露。数据仍是当前阶段冻结的 `dashboard_v1` 预生成历史 Demo，不代表实时系统或真实交易。

### 社区：COMPLETE

Phase 1C 已完成信息流、详情、互动、可逆 Fork、四类发布、草稿持久化和 Workspace 联动；本阶段未修改该模块。

```text
我的策略：COMPLETE
回测研究：COMPLETE
社区：COMPLETE
工程检查：PASS
自动化测试：PASS
READY_FOR_NEXT_PHASE：YES
```

本报告不代表已进入或实现富途 OpenAPI 阶段。
