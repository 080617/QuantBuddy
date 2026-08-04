# QuantBuddy 全面前端完成度与整合审计

## 1. 审计结论

审计日期：2026-08-04  
项目根目录：`D:\QuantBuddy`  
正式前端目录：`D:\QuantBuddy\frontend`  
审计方式：正式 Next.js 源码、路由、Service、类型、持久化、production build 与 HTTP Smoke Test；根目录离线 HTML 仅用于原型映射，不作为正式功能完成证据。

| 模块 | 结论 | 核心原因 |
|---|---|---|
| 我的策略 | **PARTIAL** | 正式页面、四个创建页、Workspace Service、CRUD 与持久化已存在；但“用于完整策略”的预选参数未被创建页消费，非基准策略的“查看回测”仍显示唯一基准回测，发布入口也未按 Workspace 资产选择。 |
| 回测研究 | **PARTIAL** | 正式页面真实读取 Qlib 预生成 JSON，主要图表与指标已实现；但页面忽略策略 `id`，且未展示已有的最新信号和操作预览数据。 |
| 社区 | **PARTIAL** | 信息流、详情、Star、Comment、可逆 Fork、四类发布和 localStorage 已实现；但 Workspace 发布参数未接通，草稿刷新后没有恢复/管理入口，完整策略发布只支持唯一基准策略。 |
| 工程检查 | **PASS** | TypeScript、ESLint、production build 均通过；主要正式路由 HTTP 检查通过。 |

**READY_FOR_NEXT_PHASE：NO**

当前工程可以稳定构建和演示三个模块的主要流程，但三个模块之间仍存在会造成错误上下文或丢失入口状态的整合断点。在进入富途、模拟盘、首页或 AI Agent 阶段前，应先完成第 8 节列出的阻塞项。

---

## 2. 审计边界与证据限制

- 本轮未修改任何业务源码、配置、Mock 数据或离线 HTML。
- 本轮未生成截图。
- 唯一新增项目文件为本报告。
- `git -C D:\QuantBuddy status --short` 显示 `frontend/` 及项目其他内容全部为未跟踪文件；仓库没有可用于比较的已跟踪基线。因此无法通过 `git diff` 证明历史变更范围，本报告以当前文件内容、构建输出和运行响应为准。
- HTTP Smoke Test 证明路由能够由 production server 响应，不等同于浏览器端全部交互已经通过端到端自动化测试。项目当前未配置单元测试或 E2E 测试脚本，见 `D:\QuantBuddy\frontend\package.json`。

---

## 3. 技术栈与工程结构

### 3.1 技术栈

证据：`D:\QuantBuddy\frontend\package.json`

- Next.js `16.2.12`
- React / React DOM `19.2.4`
- TypeScript `5.x`，严格模式与 `noEmit`
- App Router：`D:\QuantBuddy\frontend\src\app`
- Tailwind CSS `4.x`
- Recharts `3.10.1`
- Lucide React `1.27.0`
- ESLint `9.x` + `eslint-config-next`
- 包管理器：pnpm
- 状态/持久化：React 本地状态 + Service 封装的 `localStorage`
- 无 Redux、Redis、WebSocket、数据库、FastAPI 或真实交易调用

`.env.local` 当前设置 `NEXT_PUBLIC_USE_MOCK_DATA=true`。`D:\QuantBuddy\frontend\src\services\data-service.ts` 只让辅助接口在 Mock/API 之间切换；Dashboard/Qlib 数据由 `dashboardService` 覆盖注入。未来 API 实现 `D:\QuantBuddy\frontend\src\services\api-service.ts` 仍全部抛出 `Not implemented in Phase 1`，辅助 Mock Service 当前返回空数组。

### 3.2 App Shell 与导航

正式业务路由统一经过：

- `D:\QuantBuddy\frontend\src\app\(app)\layout.tsx`
- `D:\QuantBuddy\frontend\src\components\layout\app-shell.tsx`
- `D:\QuantBuddy\frontend\src\components\layout\primary-nav.tsx`

我的策略、回测研究、社区及其子路由共享同一 App Shell、Sidebar、页面容器、原始 `public/quantbuddy-logo.png` 产品 Logo；左下角用户头像与产品 Logo 分离。Onboarding 使用独立 route group，属于合理的流程隔离。

发现的路由职责问题：

- `/my-strategies` 以 307 跳转 `/strategy`，这是兼容入口，不是第二套页面。
- `/` 与 `/dashboard` 都是“功能开发中”占位页，首页/Dashboard 职责尚未冻结到唯一正式入口。
- `/strategy/create` 与 `/strategy/edit` 仍是旧占位路由；当前正式创建/编辑实际使用 `/strategy/create/{kind}` 及 `?id=`。
- `D:\QuantBuddy\frontend\src\lib\constants.ts` 仍保留一套未使用且指向 `/my-strategies` 的旧导航常量，属于清理项，但当前 Sidebar 不使用它。

### 3.3 正式路由清单与判定

| 路由 | 判定 | 说明 |
|---|---|---|
| `/` | PLACEHOLDER | 首页“功能开发中”。 |
| `/dashboard` | PLACEHOLDER | Dashboard 占位，与 `/` 存在职责重叠。 |
| `/strategy` | PARTIAL | Workspace 主页面已实现，但整合断点见第 5 节。 |
| `/my-strategies` | DUPLICATE/REDIRECT | 307 跳转 `/strategy`。 |
| `/strategy/create/complete` | IMPLEMENTED_WITH_GAPS | 创建/编辑、保存、Demo 回测门槛已实现；预选参数未接通。 |
| `/strategy/create/module` | IMPLEMENTED | 单一模块类型、自动阶段映射、保存/编辑已实现。 |
| `/strategy/create/factor` | IMPLEMENTED | 直接公式输入、保存/编辑已实现。 |
| `/strategy/create/factor-set` | IMPLEMENTED_WITH_GAPS | UI 限制至少两个单因子且不嵌套；Service 缺少独立的引用完整性校验。 |
| `/strategy/create` | PLACEHOLDER/LEGACY | 旧入口。 |
| `/strategy/edit` | PLACEHOLDER/LEGACY | 旧入口。 |
| `/backtest` | PARTIAL | 唯一基准策略的正式回测页；不识别策略 ID。 |
| `/community` | PARTIAL | 主信息流与交互已实现。 |
| `/community/[postId]` | IMPLEMENTED_WITH_GAPS | 详情、评论、互动已实现；依赖客户端 Service 加载。 |
| `/community/publish/factor` | PARTIAL | 发布/草稿可写入；Workspace 预填参数未接通。 |
| `/community/publish/module` | PARTIAL | 发布/草稿可写入；Workspace 预填参数未接通。 |
| `/community/publish/strategy` | PARTIAL | 只读取唯一 Dashboard/Qlib 基准策略。 |
| `/community/publish/question` | IMPLEMENTED_WITH_GAPS | 发布可用；草稿没有恢复入口。 |
| `/paper`、`/quantbuddy`、`/settings`、`/about` | PLACEHOLDER | 不在本轮正式模块范围。 |
| `/onboarding`、`/setup` | IMPLEMENTED | 独立 Onboarding 流程；不计入三个模块完成结论。 |

---

## 4. 数据来源与分层追踪

### 4.1 Dashboard / Qlib 回测数据

正式数据文件：`D:\QuantBuddy\frontend\public\data\dashboard_v1\`

- `dashboard.json`
- `nav_curve.json`
- `monthly_returns.json`
- `current_holdings.json`
- `latest_signals.json`
- `operation_preview.json`

数据通过 `D:\QuantBuddy\frontend\src\services\dashboard-service.ts` 静态导入，再由 `D:\QuantBuddy\frontend\src\services\data-service.ts` 对页面提供统一接口。`dashboard.json` 明确标记：

- `dataMode: historical-demo`
- `generatedFrom: D:\QuantBuddy\outputs\backtest\v2`
- 模型：LightGBM
- 特征集：Qlib Alpha158
- 股票池：当前沪深300固定股票池
- 策略：TopkDropoutStrategy / Top-5
- 回测区间：2024-01-02 至 2026-07-29

结论：该数据属于 **真实 Qlib 流程生成后的静态预生成 JSON（STATIC_PREGENERATED_JSON）**，不是浏览器实时运行 Qlib、不是实时行情、不是后端 API，也不是纯 UI 硬编码。页面中的历史回测披露与数据文件中的 `historical-backtest-position`、`historical-model-output`、`previewOnly` 一致。

### 4.2 Workspace 数据

`D:\QuantBuddy\frontend\src\services\workspace-service.ts` 组合三类来源：

1. Dashboard/Qlib 的唯一基准完整策略；
2. Workspace 自建资产（localStorage）；
3. Community Fork 到工作区的资产（Community Service/localStorage）。

组件不直接读写 localStorage，统一经过 `D:\QuantBuddy\frontend\src\lib\storage.ts`。Qlib Alpha158 在 `workspace-service.ts` 中建模为内置 `factor_set`，不是单个因子。

### 4.3 Community 数据

- 种子内容：`D:\QuantBuddy\frontend\src\mocks\community-data.ts`
- 类型：`D:\QuantBuddy\frontend\src\types\community.ts`
- 统一 Service：`D:\QuantBuddy\frontend\src\services\community-service.ts`
- 持久化 Key：`D:\QuantBuddy\frontend\src\lib\community-constants.ts`

Community 是 **Mock seed + localStorage 的前端 MVP**。Star、Follow、Comment、帖子、草稿与 Fork 状态均经 Community Service 读写；Community 组件本身未直接访问 localStorage。

---

## 5. 模块一：我的策略

### 5.1 已完成

- 正式主页面：`D:\QuantBuddy\frontend\src\app\(app)\strategy\page.tsx`
- 主组件：`D:\QuantBuddy\frontend\src\components\strategy\strategy-board.tsx`
- 创建组件：`D:\QuantBuddy\frontend\src\components\strategy\workspace-create-page.tsx`
- Service：`D:\QuantBuddy\frontend\src\services\workspace-service.ts`
- 类型：`D:\QuantBuddy\frontend\src\types\workspace.ts`

功能证据：

- 只有“完整策略 / 策略模块 / 因子与因子集”三个一级标签，无第二层状态筛选。
- 顶部统计数量来自 `workspaceService.getSnapshot()` 的同一份数组快照，不是 JSX 写死。
- 四个正式创建路由均存在并返回 HTTP 200。
- 创建、按 ID 编辑、删除和刷新持久化均经过 Workspace Service。
- 完整策略从工作区因子/因子集、预测模型与按类型划分的策略模块中选择。
- 23 个模型目录存在；只有精确匹配 LightGBM + Qlib Alpha158 + 内置 Demo 模块组合时允许生成基准 Demo 回测结果。其他配置保存为草稿并提示不生成虚假收益。
- 因子公式和模块规则只作为文本保存，不在浏览器执行。
- 创建策略模块只有一个模块类型，适用阶段由常量映射推导。
- 因子集创建页仅展示 `snapshot.factors`，不展示 `factorSets`，并在 UI 中要求至少两个单因子。
- Community 完整策略/因子/模块 Fork 能进入对应 Workspace 区域；从 Workspace 删除 Community 资产会调用 Community Service 取消对应 Fork。

### 5.2 未完成或不可靠

1. **“用于完整策略”预选链路未接通。**  
   `strategy-board.tsx` 会导航到：
   - `/strategy/create/complete?moduleId=...`
   - `/strategy/create/complete?factorId=...`
   - `/strategy/create/complete?factorSetId=...`
   但四个路由页面只读取 `searchParams.id`，`WorkspaceCreatePage` 也只接收 `editId`。因此点击这些入口不会自动选择用户刚才指定的资产。

2. **回测查看不是按策略 ID 加载。**  
   完整策略卡片链接为 `/backtest?id={item.id}`，但 `/backtest` 页面没有读取 `searchParams`，始终加载 `dataService` 的唯一基准 JSON。除基准策略外，用户可能看到错误的回测上下文。

3. **发布到社区不是按 Workspace 策略加载。**  
   卡片链接带 `strategyId`，但 `/community/publish/strategy` 不读取该参数，仅从 DashboardService 取得唯一基准策略。

4. **Service 对因子集引用缺少独立防线。**  
   UI 阻止因子集嵌套并要求至少两个因子，但 Service 保存时未重新确认所有 ID 均指向单因子。当前 UI 流程正常，未来 API/其他调用方可绕过该约束。

5. **正式页面与离线验收 HTML 存在视觉分叉。**  
   正式 `strategy-board.tsx` 仍渲染右上角“使用小贴士”；此前离线 `QuantBuddy_Workspace_Phase1B.html` 中的删除并未同步到正式 Next.js 源码。该项不影响数据功能，但证明离线 HTML 不能代表正式页面状态。

### 5.3 判定

**我的策略：PARTIAL**

CRUD、持久化与主数据结构已经超过原型，但关键跨页上下文没有可靠传递，不能判定 COMPLETE。

---

## 6. 模块二：回测研究

### 6.1 已完成

- 页面入口：`D:\QuantBuddy\frontend\src\app\(app)\backtest\page.tsx`
- 主组件：`D:\QuantBuddy\frontend\src\components\backtest\backtest-research.tsx`
- 数据适配：`D:\QuantBuddy\frontend\src\services\dashboard-service.ts`、`dashboard-adapter.ts`
- 类型：`D:\QuantBuddy\frontend\src\types\dashboard.ts`

页面通过 `Promise.allSettled` 从 DataService 并行读取策略摘要、指标、净值曲线、月收益和持仓。正式 UI 已展示：

- 模型、特征集、股票池、组合规则和回测区间；
- 累计收益、年化收益、Sharpe、最大回撤、IC、Rank IC；
- Recharts 策略净值与沪深300基准曲线；
- 近 3 月、近 6 月、近 1 年、全部区间切换；
- 月收益热力表；
- 最后一次历史回测持仓；
- 历史模拟回测风险披露。

数据不是第二套手工指标：Workspace 基准策略和 Community 完整策略均通过 Dashboard/DataService 复用同一份指标。

### 6.2 未完成或不可靠

1. **页面不识别策略 ID。**  
   `/backtest?id=...` 的 `id` 被忽略。页面始终显示唯一沪深300 LightGBM Top-5 数据，因此不能称为多策略回测研究页。

2. **已有信号和操作预览数据未进入正式页面。**  
   `latest_signals.json` 与 `operation_preview.json` 已被 DashboardService 导入/暴露，但 `backtest-research.tsx` 没有渲染“最新模型信号”或“操作预览”。这两块不能因 JSON 存在就视为页面功能完成。

3. **没有真实回测执行入口。**  
   当前仅消费静态历史结果；不调用 Qlib、不提交任务、不查询运行状态。该限制在当前阶段是允许的，但“回测研究”完成度应表述为历史 Demo 结果查看，而不是完整研究工作台。

### 6.3 判定

**回测研究：PARTIAL**

单一基准策略的历史回测展示质量较完整，但缺少策略身份联动与已有信号/操作数据展示。

---

## 7. 模块三：社区

### 7.1 已完成

- 主页面：`D:\QuantBuddy\frontend\src\app\(app)\community\page.tsx`
- 详情页：`D:\QuantBuddy\frontend\src\app\(app)\community\[postId]\page.tsx`
- 主交互：`D:\QuantBuddy\frontend\src\components\community\community-hub.tsx`
- 统一卡片：`community-post-card.tsx`
- 互动栏：`community-action-bar.tsx`
- 详情与评论：`community-post-detail.tsx`
- 四类发布：`community-publish-form.tsx` 与四个 publish route
- Service：`D:\QuantBuddy\frontend\src\services\community-service.ts`

实现证据：

- 信息流支持类型筛选、排序和关注筛选。
- 四类帖子使用统一卡片外框、作者区与紧凑互动栏；提问不显示 Fork。
- 点击卡片主体进入 `/community/[postId]`。
- Star 有空心/紫色填充状态，二次点击取消，状态与数量经 Service 持久化。
- Comment 进入详情页；评论输入、提交、列表与数量同步经 Service 持久化。
- 完整策略、因子、策略模块的 Fork 分别调用对应 Service；以 `sourcePostId` 去重，并支持二次点击移除。
- Community Fork 与 Workspace 删除的反向同步逻辑存在。
- 草稿被写入本地帖子存储，但 `getPosts()` 仅返回 `published`，不会进入公开信息流。
- 发布成功会创建真实本地 Community Post，并导航到详情页。
- 完整策略帖子指标通过 DashboardService 取得，没有在 Community 再硬编码一套收益数据。

### 7.2 未完成或不可靠

1. **Workspace → Community 发布上下文未接通。**  
   Workspace 因子和模块卡片传递 `workspaceId`，但 factor/module 发布路由和 `CommunityPublishForm` 不读取该参数，表单不会预填对应资产。

2. **完整策略发布只支持唯一基准策略。**  
   `/community/publish/strategy` 直接调用 `dataService.getStrategySummary/getStrategies/getBacktestMetrics`，不读取 `strategyId`，也不调用 Workspace Service。用户新建并完成 Demo 回测的 Workspace 策略不能被正确选择发布。

3. **草稿持久化是“可写但不可恢复”。**  
   `draftId` 仅保存在发布组件的 React state。刷新或离开页面后，没有草稿列表、恢复参数或 Service 读取流程；同时 `getPostById()` 基于只返回 published 的 `getPosts()`。草稿虽然留在 localStorage，但用户无法继续编辑。

4. **缺少自动化回归测试。**  
   Star、Comment、Fork 和刷新持久化主要由源码路径证明；项目没有单元/E2E 测试对这些可逆操作做持续验证。

### 7.3 判定

**社区：PARTIAL**

社区主信息流、详情与互动已经是正式可运行实现，不是 PROTOTYPE_ONLY；但发布与 Workspace 的核心整合、草稿恢复尚未完成。

---

## 8. 跨模块整合矩阵与阻塞项

| 链路 | 当前状态 | 证据/问题 |
|---|---|---|
| Dashboard/Qlib → Workspace 基准策略 | PASS | `workspace-service.ts` 从 DataService 生成基准资产与真实指标。 |
| Dashboard/Qlib → Backtest | PASS（单一基准） | Backtest 页面读取 DashboardService 的预生成 JSON。 |
| Dashboard/Qlib → Community 完整策略指标 | PASS（单一基准） | Community Service/发布页复用 DashboardService。 |
| Community Fork → Workspace | PASS | 因子、模块、完整策略分别写入对应 workspace key。 |
| Workspace 删除 Community 资产 → Community Fork 取消 | PASS | `removeCompleteStrategy/removeStrategyModule/removeFactor` 调用对应 Community remove 方法。 |
| Workspace 资产 → 创建完整策略预选 | **FAIL** | 链接参数存在，但创建页不读取 `moduleId/factorId/factorSetId`。 |
| Workspace 策略 → Backtest | **FAIL** | 链接携带 `id`，Backtest 页面忽略。 |
| Workspace 资产 → Community 发布 | **FAIL** | 链接携带 `strategyId/workspaceId`，发布页忽略。 |
| Community 草稿 → 刷新后继续编辑 | **FAIL** | 数据持久化但无恢复入口。 |

进入下一阶段前的最低修复顺序：

1. 建立统一的策略 ID → 回测结果解析，确保 `/backtest?id=` 不会展示错误策略。
2. 让完整策略创建页消费 `moduleId/factorId/factorSetId` 并做存在性、类型、锁定状态校验。
3. 让 Community 发布页通过 Workspace Service 加载 `strategyId/workspaceId`，并只发布所选资产。
4. 为 Community 草稿提供 Service 查询和恢复流程。
5. 为 Workspace/Community 可逆联动和持久化增加最少一组自动化测试。

---

## 9. 离线 HTML 与正式源码映射

根目录原型包括：

- `QuantBuddy_四屏像素复刻.html` / `.css` → 正式 `/onboarding`、`/setup`
- `QuantBuddy_我的策略.html`、`QuantBuddy_Workspace_Phase1A.html` → 正式 `/strategy`
- `QuantBuddy_Workspace_Phase1B.html` → 正式 `/strategy` 与四个 `/strategy/create/*` 路由
- `QuantBuddy_回测研究.html` → 正式 `/backtest`
- `QuantBuddy_Community_Phase1.html` → 正式 `/community`、`/community/[postId]`
- `QuantBuddy_Community_Phase2.html` → 正式四个 `/community/publish/*` 路由

这些 HTML 是可双击的离线验收原型，拥有独立脚本和 localStorage 空间。它们不由 Next.js App Router、正式 Service 或正式类型系统驱动，不能证明生产源码已完成。正式策略页仍出现而离线 HTML 已删除的“使用小贴士”，正是两套实现可能分叉的直接证据。

---

## 10. 工程检查与运行证据

执行目录：`D:\QuantBuddy\frontend`

### 10.1 TypeScript

命令：`pnpm exec tsc --noEmit`  
结果：**PASS**，退出码 0，无诊断输出。

### 10.2 ESLint

命令：`pnpm lint`  
结果：**PASS**，退出码 0，无 warning/error。

### 10.3 Production Build

命令：`pnpm build`  
结果：**PASS**，Next.js 16.2.12/Turbopack 编译、TypeScript、24 个页面生成均成功。

### 10.4 HTTP Smoke Test

使用 production server `next start -p 3017`，检查结果：

| 路由 | HTTP |
|---|---:|
| `/` | 200 |
| `/strategy` | 200 |
| `/strategy/create/complete` | 200 |
| `/strategy/create/module` | 200 |
| `/strategy/create/factor` | 200 |
| `/strategy/create/factor-set` | 200 |
| `/backtest` | 200 |
| `/community` | 200 |
| `/community/post-complete-strategy-lightgbm` | 200 |
| `/community/publish/factor` | 200 |
| `/community/publish/module` | 200 |
| `/community/publish/strategy` | 200 |
| `/community/publish/question` | 200 |
| `/dashboard` | 200 |
| `/my-strategies` | 307 → `/strategy` |

Smoke Test 后临时 production server 已停止。

---

## 11. 最终状态

我的策略：**PARTIAL**  
回测研究：**PARTIAL**  
社区：**PARTIAL**  
工程检查：**PASS**  
READY_FOR_NEXT_PHASE：**NO**

