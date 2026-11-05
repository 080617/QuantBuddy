# QuantBuddy 前端开发交接文档

> 用途：把本文件发送到另一个 ChatGPT 窗口，用于并行开发 QuantBuddy 第一阶段前端。  
> 原则：前端先使用 Mock Data 独立完成，后端接口完成后再替换数据源。不要等待 Qlib、富途或数据管道全部完成。

---

## 1. 项目定位

QuantBuddy 是一个面向金融初学者的量化模拟投资与策略社区 Demo。

第一阶段包含两个核心模块：

1. **量化模拟投资流程**
   - 用户完成五步设置；
   - 查看历史回测；
   - 查看前向模拟交易账户；
   - 查看模型给出的最新目标组合。

2. **基础策略社区**
   - 浏览策略；
   - 查看策略详情；
   - Star、收藏、评论；
   - 发布策略介绍；
   - 复刻策略配置。

第一版的目标是完成一个清晰、可演示、可接后端的 Web Demo。暂不追求完整交易平台能力。

---

## 2. 已冻结的产品决策

以下内容不要自行修改。

### 2.1 市场与策略

- 市场：A 股
- 股票池：沪深 300
- 实际运行模型：LightGBM
- 特征：Qlib Alpha158
- 历史回测与模型计算：Qlib
- 前向模拟交易：富途 OpenAPI A 股模拟盘
- 方向：仅做多
- 杠杆：不使用
- 组合：Top 5
- 每次调出股票数：`n_drop = 1`
- 初始资金：Demo 默认选择 `¥100,000`
- 允许保留现金
- 历史回测与前向模拟必须分开展示

### 2.2 模型选择页

- 页面显示 23 张模型卡片；
- 每张卡片只显示模型名称和 2–3 个短标签；
- 整张卡片可点击；
- 不设置“选择模型”按钮；
- 只有 LightGBM 可以真正进入结果流程；
- 其他 22 个模型暂时是展示占位；
- 点击未开放模型时，显示轻量提示：`即将开放` 或 `当前 Demo 仅开放 LightGBM`。

### 2.3 Demo 用户

- 第一版只有一个演示用户；
- 不做注册、登录、OAuth、多用户权限；
- 可以在界面中显示 `Demo User`；
- 用户配置先保存在浏览器 `localStorage`；
- 后端准备好后再改为数据库接口。

### 2.4 社区安全边界

- 社区不能上传并执行任意 Python 代码；
- “复刻策略”只复制结构化配置；
- 发布内容只包含文本、标签、指标和配置；
- 第一版不做代码沙箱。

---

## 3. 推荐技术栈

为减少开发时间，使用：

- Next.js
- App Router
- TypeScript
- Tailwind CSS
- Recharts
- Lucide React
- 浏览器 `localStorage`
- Mock JSON / TypeScript 常量
- 后续通过 FastAPI REST API 接入真实数据

不要在第一版加入：

- Redux
- Redis
- WebSocket
- 复杂权限系统
- 微前端
- SSR 数据依赖
- 复杂状态机

页面状态使用 React Context 或轻量自定义 Hook 即可。

---

## 4. 整体用户流程

```text
首页
→ 开始模拟投资
→ 第一步：初始资金
→ 第二步：投资周期
→ 第三步：风险等级
→ 第四步：模型选择
→ 第五步：确认默认策略
→ 生成方案
→ 结果 Dashboard
```

Dashboard 内分为：

```text
历史验证
├── 策略净值
├── 沪深300基准
├── 累计收益
├── 最大回撤
├── Sharpe
└── 历史交易

正在运行
├── 富途模拟账户
├── 总资产
├── 可用现金
├── 当前持仓
├── 最新订单
└── 下一交易日目标组合
```

社区流程：

```text
社区首页
→ 策略列表
→ 策略详情
→ Star / 收藏 / 评论
→ 复刻策略
→ 跳转至配置确认页
```

---

## 5. 建议路由

```text
/                         首页
/setup                    五步设置
/dashboard                结果 Dashboard
/community                社区策略列表
/community/[id]           策略详情
/community/publish        发布策略
/my-strategies            我的策略
/about                    项目说明
```

五步设置都放在 `/setup` 一个页面，通过内部步骤切换实现，不拆成五个路由。

---

## 6. 全局布局

### 6.1 顶部导航

左侧：`QuantBuddy`

右侧：

```text
模拟投资
策略社区
我的策略
关于项目
Demo User
```

移动端使用折叠菜单。

### 6.2 视觉方向

关键词：

- 可信
- 简洁
- 年轻
- 金融科技
- 避免传统券商软件的密集感
- 避免过度游戏化

建议：

- 大量留白；
- 卡片圆角；
- 清晰层级；
- 收益上涨和下跌使用一致的金融颜色规范；
- 不要使用过多渐变；
- 图表优先可读性；
- 所有模拟或回测数据必须加来源标签。

### 6.3 固定风险提示

Dashboard 底部显示：

> 本平台展示的是历史回测和模拟交易结果，仅用于学习与研究，不构成任何投资建议。历史表现不代表未来收益。

---

## 7. 首页设计

### 7.1 Hero 区域

主标题示例：

```text
从第一笔模拟投资开始，
理解量化策略如何工作
```

副标题示例：

```text
选择资金、周期、风险和模型，查看策略的历史表现，并在模拟账户中持续观察它的真实运行过程。
```

主按钮：`开始模拟投资`

次按钮：`浏览策略社区`

### 7.2 三个核心价值卡片

```text
零代码体验
不需要编程，也能完成一次量化投资流程

历史验证
用回测理解收益、风险和回撤

持续观察
通过模拟账户观察策略如何形成持仓
```

### 7.3 工作流程展示

```text
完成设置 → 模型分析 → 历史回测 → 模拟运行
```

### 7.4 社区预览

显示 3 张热门策略卡片和“查看全部”。

---

## 8. 五步设置页面

页面顶部显示：`第 X 步 / 共 5 步`。

使用进度条，不使用复杂动画。

所有选择写入统一对象：

```ts
export interface OnboardingConfig {
  initialCapital: 10000 | 30000 | 50000 | 100000;
  investmentPeriod: "1m" | "3m" | "6m" | "12m";
  riskLevel: "conservative" | "steady" | "balanced" | "aggressive";
  modelId: string;
  strategyId: "csi300-long-top5";
}
```

### 8.1 第一步：初始资金

标题：`你准备从多少模拟资金开始？`

选项：

- ¥10,000
- ¥30,000
- ¥50,000
- ¥100,000

Demo 默认：`¥100,000`

交互：

- 点击卡片选中；
- 选中卡片显示边框和勾选状态；
- 页面底部有“下一步”；
- 未选择时“下一步”禁用。

### 8.2 第二步：投资周期

标题：`你希望观察多长时间？`

选项：

- 1 个月
- 3 个月
- 6 个月
- 1 年

这里只代表用户希望观察模拟策略的周期，不改变历史回测区间。

### 8.3 第三步：风险等级

标题：`你更在意收益机会，还是资金波动？`

| 等级 | 描述 |
|---|---|
| 保守 | 更重视资金稳定 |
| 稳健 | 接受有限波动 |
| 平衡 | 在收益与风险之间平衡 |
| 积极 | 接受较大波动以争取收益 |

Demo 默认：`平衡`

第一版后端暂时不会因为风险等级切换模型参数。前端保存该选择，并在结果页展示为用户偏好。

### 8.4 第四步：模型选择

标题：`选择一个量化模型`

说明：

```text
不同模型会用不同方式从历史数据中识别规律。当前 Demo 已开放 LightGBM。
```

#### 23 张模型卡片

1. LightGBM — `训练快速` `树模型` `Demo 推荐`
2. XGBoost — `梯度提升` `经典模型` `即将开放`
3. CatBoost — `梯度提升` `稳健训练` `即将开放`
4. Linear — `线性基线` `易解释` `即将开放`
5. MLP — `神经网络` `非线性` `即将开放`
6. DNN — `深度学习` `多层结构` `即将开放`
7. LSTM — `时间序列` `长期依赖` `即将开放`
8. GRU — `时间序列` `轻量循环网络` `即将开放`
9. ALSTM — `注意力机制` `时间序列` `即将开放`
10. TCN — `卷积序列` `并行训练` `即将开放`
11. Transformer — `注意力机制` `序列建模` `即将开放`
12. Localformer — `局部注意力` `序列模型` `即将开放`
13. TFT — `时序融合` `多变量` `即将开放`
14. TabNet — `表格数据` `特征选择` `即将开放`
15. SFM — `频率建模` `时间序列` `即将开放`
16. GATs — `图注意力` `股票关系` `即将开放`
17. HIST — `行业关系` `图模型` `即将开放`
18. IGMTF — `动态图结构` `多股票关系` `即将开放`
19. MASTER — `市场信息` `深度模型` `即将开放`
20. TRA — `市场状态` `动态路由` `即将开放`
21. DoubleEnsemble — `集成学习` `稳健组合` `即将开放`
22. ADD — `域适应` `市场变化` `即将开放`
23. ADARNN — `自适应时序` `域适应` `即将开放`

卡片规则：

- LightGBM 默认置顶；
- LightGBM 显示“已开放”；
- 其他模型降低一点视觉强调；
- 点击其他模型显示 Toast；
- 点击 LightGBM 后允许进入下一步；
- 卡片中不要出现独立按钮；
- 不显示模型复杂参数。

### 8.5 第五步：确认默认策略

标题：`确认你的模拟策略`

展示只读策略摘要：

```text
市场：A股
股票池：沪深300
模型：LightGBM
特征：Alpha158
方向：仅做多
组合规模：5只股票
再平衡：每日评估
杠杆：不使用
现金：允许保留
```

页面必须明确：

```text
当前 Demo 使用默认策略配置，暂不支持修改。
```

按钮：`生成我的模拟方案`

点击后：

1. 保存配置到 `localStorage`；
2. 显示 1–2 秒加载状态；
3. 跳转 `/dashboard`。

加载文案可以依次显示：

```text
正在读取模型结果
正在准备历史回测
正在同步模拟账户
```

前端阶段全部使用 Mock Data，因此不要真的等待接口。

---

## 9. Dashboard 详细设计

Dashboard 顶部显示用户方案摘要：

```text
¥100,000 · 1年 · 平衡型 · LightGBM
```

右侧显示状态：`模拟运行中`

### 9.1 页面 Tab

```text
总览
历史验证
模拟账户
交易记录
```

也可以在单页纵向展示，但必须让“历史验证”和“正在运行”视觉上明显分开。

### 9.2 总览

第一排指标卡：

- 历史累计收益
- 历史最大回撤
- 历史 Sharpe
- 模拟账户总资产

第二排：

- 策略净值与沪深300曲线；
- 当前持仓概览。

每个指标必须标注数据类型：`历史回测` 或 `前向模拟`。

### 9.3 历史验证区

标题：`历史验证`

副说明：

```text
以下结果来自 2024 年至最新完整交易日的样本外回测。
```

内容：

1. 策略净值曲线；
2. 沪深300基准曲线；
3. 累计收益；
4. 年化收益；
5. 最大回撤；
6. Sharpe；
7. 换手率；
8. 历史交易表。

图表数据结构：

```ts
export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number;
}
```

历史交易表：

```ts
export interface BacktestTrade {
  date: string;
  symbol: string;
  name: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  amount: number;
}
```

### 9.4 前向模拟账户区

标题：`正在运行`

副说明：

```text
以下数据来自富途 A 股模拟账户。
```

指标：

- 总资产；
- 可用现金；
- 持仓市值；
- 今日收益；
- 累计收益；
- 最新同步时间。

持仓表：

```ts
export interface PaperPosition {
  symbol: string;
  name: string;
  quantity: number;
  availableQuantity: number;
  averageCost: number;
  currentPrice: number;
  marketValue: number;
  pnl: number;
  pnlRate: number;
  weight: number;
}
```

订单表：

```ts
export interface PaperOrder {
  orderId: string;
  createdAt: string;
  symbol: string;
  name: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  filledQuantity: number;
  averageFillPrice: number | null;
  status:
    | "SUBMITTED"
    | "PARTIALLY_FILLED"
    | "FILLED"
    | "CANCELLED"
    | "FAILED";
}
```

### 9.5 下一交易日目标组合

单独使用卡片展示：

```text
信号日期
计划执行日期
模型
目标股票
目标权重
当前权重
预计交易动作
```

数据结构：

```ts
export interface TargetPosition {
  symbol: string;
  name: string;
  score: number;
  targetWeight: number;
  currentWeight: number;
  action: "BUY" | "HOLD" | "REDUCE" | "SELL";
}
```

必须注明：

```text
该组合是模型输出的模拟目标，不构成投资建议。
```

---

## 10. 社区页面

### 10.1 社区列表页

顶部：

- 页面标题；
- 搜索框；
- 标签筛选；
- 排序：热门、最新、Star 数。

策略卡片显示：

- 策略名称；
- 作者；
- 一句话简介；
- 模型标签；
- 市场标签；
- 风险标签；
- 历史收益；
- 最大回撤；
- Star；
- 评论数；
- 更新时间。

### 10.2 策略详情页

内容：

- 策略名称；
- 作者；
- 简介；
- 模型；
- 股票池；
- 组合规则；
- 风险等级；
- 回测指标；
- 净值图；
- 风险提示；
- 评论区。

操作：`Star`、`收藏`、`复刻策略`。

### 10.3 复刻策略

点击“复刻策略”后：

1. 复制该策略的结构化配置；
2. 保存到 `localStorage`；
3. 跳转 `/setup` 第五步或策略确认页；
4. 用户确认后加入“我的策略”。

不能执行社区作者代码。

### 10.4 发布策略

第一版表单：

- 策略名称；
- 简介；
- 模型；
- 股票池；
- 风险标签；
- 组合规模；
- 回测累计收益；
- 最大回撤；
- Sharpe；
- 策略说明。

不提供 Python 文件上传。

---

## 11. Mock Data 设计

建立：

```text
src/mocks/
├── models.ts
├── backtest.ts
├── paper-account.ts
├── positions.ts
├── orders.ts
├── targets.ts
└── community.ts
```

所有页面先从 Mock Service 读取数据：

```ts
export const dataService = {
  getModels,
  getBacktest,
  getPaperAccount,
  getPositions,
  getOrders,
  getTargets,
  getCommunityStrategies,
};
```

后端准备好后，只修改 Service 层，不修改页面组件。

---

## 12. 未来 FastAPI 接口契约

前端先按以下接口形状开发。

### 模型

```http
GET /api/models
```

### 保存五步设置

```http
POST /api/onboarding
```

Request：

```json
{
  "initial_capital": 100000,
  "investment_period": "12m",
  "risk_level": "balanced",
  "model_id": "lightgbm",
  "strategy_id": "csi300-long-top5"
}
```

### 历史回测

```http
GET /api/backtest/latest
```

### 最新信号

```http
GET /api/signals/latest
```

### 模拟账户

```http
GET /api/paper/account
GET /api/paper/positions
GET /api/paper/orders
```

### 社区

```http
GET  /api/community/strategies
GET  /api/community/strategies/{id}
POST /api/community/strategies
POST /api/community/strategies/{id}/star
POST /api/community/strategies/{id}/favorite
POST /api/community/strategies/{id}/comments
POST /api/community/strategies/{id}/fork
```

前端通过环境变量读取后端地址：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
NEXT_PUBLIC_USE_MOCK_DATA=true
```

实现规则：

```ts
if (process.env.NEXT_PUBLIC_USE_MOCK_DATA === "true") {
  return mockData;
}

return fetchFromApi();
```

---

## 13. 推荐目录结构

```text
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── setup/page.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── community/page.tsx
│   │   ├── community/[id]/page.tsx
│   │   ├── community/publish/page.tsx
│   │   ├── my-strategies/page.tsx
│   │   └── about/page.tsx
│   ├── components/
│   │   ├── layout/
│   │   ├── onboarding/
│   │   ├── dashboard/
│   │   ├── charts/
│   │   ├── community/
│   │   └── ui/
│   ├── contexts/
│   │   └── onboarding-context.tsx
│   ├── hooks/
│   ├── lib/
│   │   ├── format.ts
│   │   ├── storage.ts
│   │   └── constants.ts
│   ├── mocks/
│   ├── services/
│   │   ├── data-service.ts
│   │   ├── mock-service.ts
│   │   └── api-service.ts
│   └── types/
│       ├── onboarding.ts
│       ├── model.ts
│       ├── backtest.ts
│       ├── paper.ts
│       └── community.ts
├── public/
├── .env.local
└── package.json
```

---

## 14. 前端分阶段开发顺序

### Phase 1：初始化项目

任务：

1. 创建 Next.js TypeScript 项目；
2. 配置 Tailwind；
3. 安装 Recharts 和 Lucide React；
4. 建立目录；
5. 创建全局导航和页面容器；
6. 创建 `.env.local`；
7. 创建统一 TypeScript 类型。

验收：

- `/` 可访问；
- 导航可跳转；
- 页面无 TypeScript 报错；
- 移动端基础布局正常。

### Phase 2：首页

任务：

1. Hero；
2. 两个主要按钮；
3. 三个价值卡片；
4. 流程展示；
5. 社区策略预览；
6. 风险提示。

验收：

- “开始模拟投资”跳转 `/setup`；
- “浏览策略社区”跳转 `/community`；
- 页面视觉完整。

### Phase 3：五步设置

任务：

1. 进度条；
2. 初始资金；
3. 投资周期；
4. 风险等级；
5. 23 模型卡片；
6. 默认策略确认；
7. `localStorage`；
8. 跳转 Dashboard。

验收：

- 前进、返回正常；
- 刷新后配置可恢复；
- 未完成选择时无法下一步；
- 只有 LightGBM 可以完成流程；
- 整张模型卡片可点击；
- 第五步不能修改策略参数。

### Phase 4：Dashboard

任务：

1. 总览指标；
2. 回测曲线；
3. 基准曲线；
4. 历史指标；
5. 模拟账户；
6. 持仓表；
7. 订单表；
8. 最新目标组合；
9. 数据来源标签；
10. 风险提示。

验收：

- 历史回测和前向模拟视觉分离；
- 图表响应式；
- 表格在小屏幕可横向滚动；
- 金额、比例和日期格式统一；
- 空数据有占位状态；
- Loading 和 Error 状态存在。

### Phase 5：社区

任务：

1. 社区列表；
2. 搜索和筛选；
3. 策略详情；
4. Star；
5. 收藏；
6. 评论；
7. 发布表单；
8. 复刻策略；
9. 我的策略。

验收：

- 所有交互可在 `localStorage` 中持久化；
- 刷新后 Star、收藏、评论仍保留；
- 复刻后能在“我的策略”看到；
- 不存在代码上传入口。

### Phase 6：后端适配层

任务：

1. 保留 Mock Service；
2. 新建 API Service；
3. 通过环境变量切换；
4. 统一 Loading；
5. 统一 Error；
6. 处理字段命名转换；
7. 保留 Demo 缓存。

验收：

```env
NEXT_PUBLIC_USE_MOCK_DATA=true
```

时完全独立运行。改为 `false` 时能够连接 FastAPI。

### Phase 7：Demo 打磨

任务：

1. 修复响应式；
2. 增加空状态；
3. 增加错误状态；
4. 增加数据更新时间；
5. 添加 Demo 数据标识；
6. 添加免责声明；
7. 准备网络失败时的缓存结果；
8. 检查所有按钮；
9. 检查所有路由；
10. 检查浏览器控制台。

验收：

- 演示时不需要现场训练模型；
- 后端断开时可切换 Mock；
- 不出现空白页；
- 不出现未处理报错；
- 主要流程能在 2–3 分钟内完整展示。

---

## 15. 页面数据状态规范

每个数据模块都需要四种状态：

```text
Loading
Success
Empty
Error
```

示例：

```tsx
if (loading) return <DashboardSkeleton />;
if (error) return <ErrorState message="数据暂时无法加载" />;
if (!data) return <EmptyState message="暂无数据" />;
return <DashboardContent data={data} />;
```

不要只设计成功状态。

---

## 16. 格式规范

### 金额

```text
¥100,000.00
```

### 比例

```text
12.58%
-4.21%
```

### 日期

```text
2026-07-29
```

### 股票代码

前端显示：

```text
600000.SH
000001.SZ
```

富途内部可能使用：

```text
SH.600000
SZ.000001
```

转换逻辑放在 Service 层或后端，页面组件不要到处处理代码格式。

---

## 17. 前端目前不能假设的内容

后端仍在开发，以下数据暂时都没有最终真实值：

- LightGBM 的真实回测收益；
- 最大回撤；
- Sharpe；
- 最新持仓；
- 富途账户总资产；
- 最新订单；
- 每只股票的真实模型评分；
- 完整历史沪深300成分股。

前端必须使用明确标注的 Mock Data，不得把 Mock 数值写成真实结果。

建议所有 Mock 数据旁边显示：`演示数据`。

---

## 18. 与后端的协作边界

### 前端负责

- 页面；
- 交互；
- 状态；
- 图表；
- 表格；
- Mock Data；
- API Service；
- 格式化；
- 响应式；
- 错误状态；
- 缓存展示。

### 后端负责

- BaoStock / AKShare 数据下载；
- 数据清洗；
- 沪深300股票池；
- Qlib 数据转换；
- Alpha158；
- LightGBM；
- 回测；
- 每日预测；
- Top 5 目标组合；
- 富途模拟账户；
- 订单同步；
- FastAPI；
- SQLite。

### 连接点

前端只通过 REST API 连接后端，不直接读取：

- Qlib 文件；
- 本地 CSV；
- 模型文件；
- 富途 OpenD；
- 数据源接口。

---

## 19. 第一版完成定义

以下条件全部满足，前端 V1 才算完成：

- 首页完成；
- 五步设置完成；
- 23 张模型卡片完成；
- LightGBM 可完成选择；
- 默认策略不可编辑；
- Dashboard 完成；
- 历史与前向数据分开；
- 社区列表和详情完成；
- Star、收藏、评论、复刻完成；
- Mock 模式独立可运行；
- API 模式预留完成；
- 移动端基础适配；
- 风险提示完整；
- 无明显控制台错误。

---

# 给另一个 ChatGPT 窗口的执行指令

请把下面这段和本文件一起发送：

```text
你现在负责 QuantBuddy 项目的前端开发。请严格按照附件《QuantBuddy 前端开发交接文档》执行，不要修改已经冻结的产品决策。

开发原则：
1. 先使用 Mock Data 完成全部前端，不等待后端；
2. 使用 Next.js App Router、TypeScript、Tailwind CSS、Recharts；
3. 只有 LightGBM 真正开放，其他 22 个模型只做展示占位；
4. 第五步默认策略只读，不允许用户修改；
5. 历史回测与前向模拟账户必须分开展示；
6. 第一版不做登录，不执行用户代码；
7. 所有真实数据通过 Service 层接 FastAPI；
8. 每完成一个 Phase，先检查并汇报文件变更、运行命令和验收结果，再继续下一 Phase；
9. 不要一次生成整个项目，先从 Phase 1 初始化和目录骨架开始；
10. 遇到文档没有明确规定的地方，优先选择最简单、最稳妥、最容易演示的实现，不擅自扩大范围。

现在先执行 Phase 1。请先给出：
- 将创建的目录和文件；
- 需要运行的命令；
- 完成后的验收方式；
然后再开始写代码。
```
