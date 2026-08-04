# QuantBuddy Frontend Integration Repair Phase 1C Completion Report

## 1. 阶段结论

项目根目录：`D:\QuantBuddy`  
正式前端：`D:\QuantBuddy\frontend`  
完成日期：2026-08-04

Integration Repair Phase 1C 已完成。审计确认的跨模块断点均已修复，离线 HTML、Onboarding、首页、Dashboard、模拟盘、AI Agent、Qlib JSON 和数据生成链均未修改。

最终重新判定：

```text
我的策略：COMPLETE
回测研究：PARTIAL
社区：COMPLETE
工程检查：PASS
自动化测试：PASS
READY_FOR_NEXT_PHASE：NO
```

`回测研究` 仍判定为 PARTIAL 的原因不是 Phase 1C 失败，而是前次全面审计已经确认 `latest_signals.json` 和 `operation_preview.json` 尚未进入正式回测页面；本阶段明确只修复整合断点且禁止重做回测页面，因此没有越界增加这两块 UI。当前已完成的是策略 ID 与回测上下文的可靠整合。

---

## 2. 修改文件

### 工程与测试

- `D:\QuantBuddy\frontend\package.json`
  - 增加 `pnpm test`。
  - 增加最小测试依赖 Vitest。
- `D:\QuantBuddy\frontend\pnpm-lock.yaml`
  - 记录 Vitest 依赖解析结果。
- `D:\QuantBuddy\frontend\pnpm-workspace.yaml`
  - 仅允许项目实际使用的 `esbuild`、`sharp`、`unrs-resolver` 安装脚本。
- `D:\QuantBuddy\frontend\vitest.config.ts`
  - 配置 Node 测试环境与 `@` 路径别名。
- `D:\QuantBuddy\frontend\src\services\integration-repair.test.ts`
  - Phase 1C 的 7 项聚焦自动化测试。

### Workspace 与回测

- `src/types/workspace.ts`
- `src/services/workspace-service.ts`
- `src/services/workspace-integration.ts`（新增）
- `src/app/(app)/backtest/page.tsx`
- `src/components/backtest/backtest-context-page.tsx`（新增）
- `src/app/(app)/strategy/create/complete/page.tsx`
- `src/components/strategy/workspace-create-page.tsx`
- `src/components/strategy/strategy-board.tsx`
- `src/app/globals.css`

### Community

- `src/types/community.ts`
- `src/services/community-service.ts`
- `src/components/community/community-publish-form.tsx`
- `src/components/community/community-publish.module.css`
- `src/components/community/community-post-detail.tsx`
- `src/app/(app)/community/publish/factor/page.tsx`
- `src/app/(app)/community/publish/module/page.tsx`
- `src/app/(app)/community/publish/strategy/page.tsx`
- `src/app/(app)/community/publish/question/page.tsx`

未修改任何 `D:\QuantBuddy\*.html` 文件。

---

## 3. Backtest ID 解析

### 实现

`WorkspaceCompleteStrategy` 增加显式：

```ts
backtestRef?: "dashboard_v1"
```

`workspaceService.resolveBacktestContext(id)` 返回严格的联合状态：

```text
ready
not_backtested
not_found
```

解析规则：

- 基准策略 `strategy-hs300-lightgbm-top5` 被明确绑定到 `dashboard_v1`。
- 只有 `status === "backtested"`、`requiresRebacktest === false` 且 `backtestRef === "dashboard_v1"` 的策略返回 `ready`。
- 草稿、Community Fork、待重新回测策略或缺少回测引用的旧资产返回 `not_backtested`。
- 不存在的 ID 返回 `not_found`。
- 未提供 ID 时继续解析默认基准策略，兼容原有 `/backtest` 入口。
- 解析过程不根据策略名称猜测回测数据。

`/backtest` 现在读取 Next.js 16 的异步 `searchParams`，再由客户端 `BacktestContextPage` 读取当前设备的 Workspace Service/localStorage 状态。这样服务端页面不会把浏览器中不存在的 Workspace 策略误判为基准策略。

### 空状态

`not_backtested` 显示：

```text
该策略尚未在当前工作区完成回测
```

`not_found` 显示：

```text
未找到对应策略
```

两种状态均提供：

- 返回我的策略
- 继续编辑

草稿和 Fork 不再渲染基准收益、净值曲线或持仓。

---

## 4. 创建完整策略预选参数

`/strategy/create/complete` 现在同时读取：

```text
id
moduleId
factorId
factorSetId
```

公共预选逻辑位于：

```text
src/services/workspace-integration.ts
resolveCompleteStrategyPreselection(...)
```

行为：

- `factorId` 只在 ID 对应单个因子时加入。
- `factorSetId` 只在 ID 对应因子集时加入。
- 因子/因子集 ID 自动去重。
- `moduleId` 根据模块的真实 `moduleType` 进入：
  - `stock_selection`
  - `weighting`
  - `rebalance`
  - `risk_control`
- `cash_management` 和 `execution` 不写入四个核心槽位，并显示非阻断说明。
- 无效或已删除 ID 不写入配置，并显示轻量提示。
- 编辑模式先加载原策略，再合并额外预选，不覆盖已有配置。

---

## 5. Workspace → Community 发布上下文

### 因子

`/community/publish/factor?workspaceId=...`：

- 通过 Workspace Service 验证并读取因子。
- 预填名称、类型、公式和说明。
- 保存 `sourceWorkspaceId`。
- 保持 `verificationStatus: not_verified`，不伪造 IC 或 Rank IC。
- 无效 ID 显示错误，不回退到其他资产。

### 策略模块

`/community/publish/module?workspaceId=...`：

- 通过 Workspace Service 验证并读取模块。
- 预填名称、模块类型、规则摘要、规则表达式和说明。
- 保存 `sourceWorkspaceId`。
- 适用阶段继续由已有映射自动推导。

### 完整策略

`/community/publish/strategy?strategyId=...`：

- 通过 Workspace Service 验证并读取指定完整策略。
- 预填策略名称、说明、股票池、模型、因子/因子集和四类模块摘要。
- 保存 `sourceWorkspaceId` 和发布时配置快照。
- 只有 `resolveBacktestContext()` 返回 `ready` 时才从现有 Dashboard/Qlib Service 附加回测指标。
- 无有效 `backtestRef` 时仍可发布配置说明，但明确显示“当前工作区尚无有效回测结果”。
- 无效 ID 显示错误，不回退到基准资产。
- Community Service 会再次校验：只有 `backtestRef === "dashboard_v1"` 才接受对应回测快照。
- 无回测帖子的详情页会显示无有效结果提示，不再假设 `backtestSnapshot` 一定存在。

Workspace 完整策略卡片现在对草稿和 Fork 也提供“发布到社区”入口；“查看回测”仍只在存在有效回测引用时显示。

---

## 6. Community 草稿恢复

Community Service 新增：

```ts
getDraftsByType(type)
getDraftById(draftId)
deleteDraft(draftId)
```

原有 `create*Post(..., draftId)` 继续承担同 ID 更新和发布转换。

发布页现在包含轻量入口：

```text
未完成草稿（N）
```

草稿列表显示：

- 标题；
- 更新时间；
- 继续编辑；
- 删除。

恢复链接格式：

```text
/community/publish/{type}?draftId={draftId}
```

行为验证：

- 第一次保存创建草稿。
- 再次保存更新同一 ID，不重复创建。
- 刷新或重新进入 URL 后恢复字段、标签、Workspace 来源与策略配置快照。
- 发布时将同一草稿转换为 published，草稿列表立即移除。
- 删除草稿后无法再读取。
- `getPosts()` 仍只返回 published，草稿不会进入公开 Community 信息流。
- 页面组件没有直接访问 localStorage，全部经过 Community Service。

---

## 7. Factor Set Service 引用完整性

校验已从 UI 下沉到 `workspaceService.createFactorSet/updateFactorSet`。

新增结构化错误：

```ts
WorkspaceValidationError
```

错误码：

```text
FACTOR_SET_TOO_SMALL
FACTOR_SET_REFERENCE_NOT_FOUND
FACTOR_SET_NESTING_NOT_ALLOWED
```

Service 现在保证：

- ID 去重后至少两个；
- 每个 ID 必须存在；
- 每个 ID 必须指向 `WorkspaceFactor`；
- `factor_set` 不能嵌套；
- 已删除/不存在的资产不能保存；
- 校验失败抛出包含 `code` 和 `field` 的结构化错误，不静默写入。

---

## 8. 正式页面视觉同步

已从正式：

```text
D:\QuantBuddy\frontend\src\components\strategy\strategy-board.tsx
```

删除右上角“使用小贴士”区域。未重做其他布局，未修改离线 `QuantBuddy_Workspace_Phase1B.html`。

---

## 9. 自动化测试

新增最小测试框架：Vitest `3.2.7`。

命令：

```text
pnpm test
```

结果：

```text
Test Files  1 passed (1)
Tests       7 passed (7)
```

覆盖内容：

1. 基准策略回测上下文为 `ready`。
2. 草稿与 Community Fork 为 `not_backtested`，不存在 ID 为 `not_found`。
3. factorId、factorSetId、moduleId 的预选与无效 ID 忽略。
4. Workspace 因子、模块、策略发布预填。
5. 无回测 Workspace 策略不继承基准指标。
6. Community 草稿创建、同 ID 更新、重新读取、发布转换和删除。
7. 因子集少于两个、重复后不足、嵌套与不存在引用校验。

自动化测试：**PASS**

---

## 10. 工程检查

执行目录：`D:\QuantBuddy\frontend`

| 命令 | 结果 |
|---|---|
| `pnpm exec tsc --noEmit` | PASS，退出码 0 |
| `pnpm lint` | PASS，退出码 0，无 warning/error |
| `pnpm test` | PASS，7/7 |
| `pnpm build` | PASS，Next.js 16.2.12 production build 成功，24 个路由生成完成 |

工程检查：**PASS**

---

## 11. HTTP Smoke Test

使用 production server 临时启动并检查，完成后已停止。

| 路由 | HTTP |
|---|---:|
| `/strategy` | 200 |
| `/strategy/create/complete` | 200 |
| `/strategy/create/complete?factorId=builtin-mom20` | 200 |
| `/backtest` | 200 |
| `/backtest?id=strategy-hs300-lightgbm-top5` | 200 |
| `/backtest?id=missing-strategy` | 200，客户端呈现 not_found 空状态 |
| `/community` | 200 |
| `/community/publish/strategy` | 200 |
| `/community/publish/strategy?strategyId=strategy-hs300-lightgbm-top5` | 200 |
| `/community/publish/module` | 200 |
| `/community/publish/factor` | 200 |
| `/community/publish/question` | 200 |

HTTP 只能证明 production 路由可响应；localStorage 相关分支由 Vitest 的内存 Storage 场景验证。

---

## 12. 剩余问题

1. 正式回测页面尚未展示已有的 `latest_signals.json` 和 `operation_preview.json`。这是全面审计留下的功能缺口，不属于本次只修复整合断点的范围。
2. 当前回测仍是 `dashboard_v1` 的静态 Qlib 历史 Demo 数据，不是实时 Qlib 任务或后端 API；这是当前产品阶段的冻结限制。
3. 自动化测试聚焦 Service 和纯整合逻辑，没有引入大型浏览器/E2E 测试工程，符合 Phase 1C 的最小测试要求。
4. 项目 Git 仓库仍缺少已跟踪基线；本轮无法提供有意义的 `git diff` 历史比较。修改文件以本报告第 2 节为准。

---

## 13. 三模块重新判定

### 我的策略：COMPLETE

当前阶段要求的 Workspace CRUD、真实统计、Community 双向 Fork、完整策略资产选择、参数预选、回测引用控制、发布上下文和因子集 Service 校验均已接通。

### 回测研究：PARTIAL

策略 ID 解析与错误基准数据问题已经修复；基准、草稿/Fork、不存在 ID 的三种上下文可靠。但前次审计确认的信号/操作预览 UI 仍未实现，因此保持 PARTIAL。

### 社区：COMPLETE

当前 Community MVP 范围内，信息流、详情、Star、Comment、可逆 Fork、四类发布、Workspace 预填、无回测策略保护、草稿恢复/更新/删除和持久化均已接通。

### 最终状态

```text
我的策略：COMPLETE
回测研究：PARTIAL
社区：COMPLETE
工程检查：PASS
自动化测试：PASS
READY_FOR_NEXT_PHASE：NO
```

