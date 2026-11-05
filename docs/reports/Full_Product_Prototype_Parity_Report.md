# QuantBuddy Full Product Prototype Parity Report

生成日期：2026-08-04  
检查范围：离线视觉源与 `D:\QuantBuddy\frontend` 正式 Next.js 前端的只读对齐检查。

## 1. 最终采用的视觉源

本次使用项目根目录中的正式命名文件，没有使用 `(1)`、`(2)` 等副本，也没有使用历史的 `QuantBuddy_Workspace_Phase1A.html`：

| 模块 | 采用文件 | 用途 |
|---|---|---|
| Onboarding | `D:\QuantBuddy\QuantBuddy_四屏像素复刻.html` | 四屏原 DOM、脚本与交互 |
| Onboarding / Backtest 共享样式 | `D:\QuantBuddy\QuantBuddy_四屏像素复刻.css` | 原 `qb-*` 样式、断点和 App Shell |
| Workspace | `D:\QuantBuddy\QuantBuddy_Workspace_Phase1B.html` | 我的策略与四个创建页面 |
| Backtest | `D:\QuantBuddy\QuantBuddy_回测研究.html` | 最新回测研究、模型信号、历史操作预览 |
| Community 主页面 | `D:\QuantBuddy\QuantBuddy_Community_Phase1.html` | 信息流、右侧栏、筛选和互动 |
| Community 发布页面 | `D:\QuantBuddy\QuantBuddy_Community_Phase2.html` | 四类发布表单与预览弹窗 |

所有上述源文件均以完整字节快照嵌入 Full Prototype；静态 SHA-256 对比结果为一致。宿主没有复用上一版 Full Prototype 的视觉 CSS。

## 2. CSS 与 DOM 隔离

- 每次只挂载一个来源模块，不纵向堆叠页面。
- 每个来源模块放入独立 Shadow Root。
- 来源文件的内联 CSS 原样注入相应 Shadow Root。
- Onboarding 与 Backtest 额外注入原始 `QuantBuddy_四屏像素复刻.css`。
- `:root` 中的原始 CSS 变量仅桥接到 Shadow Root 内部 `html` 元素，变量值没有修改。
- 宿主 CSS 只负责视图容器和未完成路由的轻量占位，不提供 Sidebar、卡片、标题或业务页面布局。
- 未使用 iframe。

## 3. 关键视觉指标静态对比

| 视图 | Sidebar | 主内容与宽度 | H1 | 卡片 / Grid | 响应式 |
|---|---|---|---|---|---|
| Onboarding | 无业务 Sidebar | 原 `--qb-page-max-width: 76rem`，原页面留白 | 知识页 42px；详情介绍 42px；完成页 42px | 知识卡 2 列；欢迎特性 4 列；周期 4 列 | 980px、640px 等原断点 |
| Workspace Phase 1B | 250px | `.main` 原 padding `30px 42px 50px`；`.page` max-width 1400px | 34px | 三统计卡 3 列；配置 4 列；创建页主列 + 300px 侧栏 | 1050px、800px |
| Backtest | 252px | `.qb-app-main` margin-left 252px、padding `34px 42px 46px`；页面 max-width 1380px | 31px | 原配置卡、5 指标、净值图、解释栏、月度收益、信号、操作预览、持仓 | 1240px、1200px、820px、760px、720px、640px |
| Community Phase 1 | 252px | 主区域原 padding `34px 42px 46px`；页面 max-width 1500px | 32px | 信息流 + 286px 右侧栏；原四类卡片 | 1150px、820px |
| Community Phase 2 | 252px | 主区域原 padding `32px 42px 48px`；页面 max-width 1450px | 31px | 表单主列 + 330px 帮助栏；原发布类型切换 | 1100px、820px |

静态 DOM 检查确认：Onboarding 仍包含 23 个模型；Workspace 保留三项一级标签和四个创建入口；Backtest 保留最新模型信号与历史操作预览；Community 主页面保留四类帖子和完整右侧栏；发布页保留四种发布类型与预览弹窗。

## 4. 离线视觉页与正式 Next.js 映射

| 离线视觉页 | 正式 Next.js 路由 | 正式源码文件 | 布局是否一致 | 主要差异 |
|---|---|---|---|---|
| 欢迎页 | `/onboarding` | `frontend/src/app/(onboarding)/onboarding/page.tsx`；`components/onboarding/welcome-screen.tsx` | 基本一致 | 正式页由 React 组件生成，离线页为原始 HTML 脚本；视觉 class 与全局 `qb-*` 体系一致。 |
| 金融知识 / 五问 / 完成 | `/setup?step=1..3` | `frontend/src/app/(onboarding)/setup/page.tsx`；`components/onboarding/setup-flow.tsx`、`knowledge-screen.tsx`、`details-screen.tsx`、`complete-screen.tsx` | 基本一致 | 正式页用路由查询参数控制步骤；离线宿主用内部 hash 映射到原 HTML 的 step 参数。 |
| 我的策略 | `/strategy` | `frontend/src/app/(app)/strategy/page.tsx`；`components/strategy/strategy-board.tsx` | 部分一致 | 正式页使用 `AppShell`、Workspace Service、更多操作弹窗和真实联动；Phase 1B HTML 使用自身 250px Sidebar 与预览数据。“使用小贴士”在正式页和本次离线源中均未恢复。 |
| 创建完整策略 | `/strategy/create/complete` | 对应 `page.tsx`；`components/strategy/workspace-create-page.tsx` | 部分一致 | 正式页支持 `id/moduleId/factorId/factorSetId` 预选和编辑；离线页保留 Phase 1B 原交互。 |
| 创建策略模块 | `/strategy/create/module` | 对应 `page.tsx`；`components/strategy/workspace-create-page.tsx` | 部分一致 | 正式页经 Workspace Service 保存，离线页使用隔离的预览存储。 |
| 创建因子 | `/strategy/create/factor` | 对应 `page.tsx`；`components/strategy/workspace-create-page.tsx` | 部分一致 | 正式页包含类型约束和编辑参数；视觉源仍以 Phase 1B HTML 为准。 |
| 创建因子集 | `/strategy/create/factor-set` | 对应 `page.tsx`；`components/strategy/workspace-create-page.tsx` | 部分一致 | 正式页包含引用完整性与编辑逻辑；离线页保留 Phase 1B 原选择界面。 |
| 回测研究 | `/backtest?id=...` | `frontend/src/app/(app)/backtest/page.tsx`；`components/backtest/backtest-context-page.tsx`、`backtest-research.tsx` | 部分一致 | 正式页会解析 Workspace 策略上下文，草稿与 Fork 不显示基准回测；当前正式组件尚未渲染 `latest_signals.json` 与 `operation_preview.json`，而最新版离线 HTML 已展示这两个区域。 |
| Community 首页 | `/community` | `frontend/src/app/(app)/community/page.tsx`；`components/community/community-hub.tsx`、`community-main.module.css` | 高度接近但非逐字一致 | 正式页通过 Community Service 读取数据并保留右侧栏；离线视觉源为 Phase 1 静态交互页。 |
| Community 详情 | `/community/[postId]` | 对应 `page.tsx`；`components/community/community-post-detail.tsx`、`community-detail.module.css` | 无可直接逐页对齐的确认 HTML | `QuantBuddy_Community_Phase1.html` 本身只含详情路由链接，没有独立详情 DOM。Full Prototype 保留原链接并切换 hash，但不能在不重新设计的前提下凭空生成一套详情视觉。正式 Next.js 详情页功能更完整。 |
| 发布完整策略 | `/community/publish/strategy` | 对应 `page.tsx`；`components/community/community-publish-form.tsx`、`community-publish.module.css` | 部分一致 | 正式页支持 Workspace 预填、草稿恢复和 Service 发布；离线页保留 Phase 2 原静态表单与预览。 |
| 发布策略模块 | `/community/publish/module` | 同上 | 部分一致 | 正式页支持 `workspaceId` 预填；离线视觉严格采用 Phase 2。 |
| 发布因子 | `/community/publish/factor` | 同上 | 部分一致 | 正式页支持 Workspace 预填与 Service 持久化；离线视觉严格采用 Phase 2。 |
| 发布问题 | `/community/publish/question` | 同上 | 部分一致 | 正式页经 Community Service 发布；离线页为独立预览存储。 |

## 5. 宿主路由与交互保留

- Hash 路由覆盖 Onboarding、Workspace、Backtest、Community 主页面和四个 Community 发布视图。
- Workspace 自身的 `#workspace/#create-*` 路由被映射为宿主 hash，不改变来源页面的 DOM。
- Onboarding 原 `?step=` 导航被映射到宿主 hash，23 模型选择、输入校验和步骤切换继续使用来源脚本。
- 来源 Sidebar 与页面内链接由捕获层转为宿主 hash；宿主不额外显示全局 Sidebar。
- 每个模块的原 localStorage key 都被放入 `quantbuddy.full-prototype.<module>.*` 独立命名空间。
- Community Phase 1 的 Star、Follow、Fork 和筛选继续使用原脚本；Phase 2 的草稿、表单、类型切换和预览弹窗继续使用原脚本。
- Backtest 的时间范围、Canvas 图表、月度收益、历史持仓、最新模型信号和历史操作预览继续使用最新版来源脚本。

## 6. 已知限制

1. `QuantBuddy_Community_Phase1.html` 不包含独立详情页 DOM，只有指向正式详情路由的链接。为遵守“不得重新设计”，Full Prototype 没有新造详情页面；详情 hash 会挂载并定位原 Community 视觉源。
2. 各模块使用独立预览 namespace，保留了原模块交互；不模拟正式后端，也不承诺所有跨模块数据与 Next.js Service 完全等价。
3. 首页、模拟盘、QuantBuddy、设置仍为后续阶段，宿主只显示轻量占位。
4. 本轮未修改 `frontend`，未修改任何单页 HTML/CSS，未生成截图，也未运行 tsc、lint、test 或 build。

## 7. 结论

- 是否重新设计任何已确认页面：**NO**
- 是否复用当前错误 Full Prototype 的视觉系统：**NO**
- 是否修改正式 frontend：**NO**
- 是否保留各来源 HTML 的原 DOM/CSS：**YES**
