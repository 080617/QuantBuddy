import type { CommunityContentType, CommunityFilterValue, CommunitySortValue, StrategyModuleType, StrategyStage } from "@/types/community";

export const STRATEGY_MODULE_TYPE_LABELS: Record<StrategyModuleType, string> = {
  stock_selection: "选股模块", weighting: "权重分配模块", rebalance: "调仓模块", risk_control: "风险控制模块", cash_management: "现金管理模块", execution: "交易执行模块",
};
export const STRATEGY_MODULE_STAGE_MAP: Record<StrategyModuleType, StrategyStage> = {
  stock_selection: "stock_selection_stage", weighting: "portfolio_construction_stage", rebalance: "rebalance_stage", risk_control: "risk_control_stage", cash_management: "portfolio_construction_stage", execution: "trade_execution_stage",
};
export const COMMUNITY_TYPE_LABELS: Record<CommunityContentType, string> = { factor: "因子", strategy_module: "策略模块", complete_strategy: "完整策略", question: "提问" };
export const COMMUNITY_FILTERS: readonly { value: CommunityFilterValue; label: string }[] = [
  { value: "recommended", label: "推荐" }, { value: "factor", label: "因子" }, { value: "complete_strategy", label: "完整策略" }, { value: "strategy_module", label: "策略模块" }, { value: "question", label: "提问" }, { value: "following", label: "我关注的" },
];
export const COMMUNITY_SORTS: readonly { value: CommunitySortValue; label: string }[] = [
  { value: "recommended", label: "推荐" }, { value: "latest", label: "最新" }, { value: "weekly_popular", label: "本周热门" }, { value: "most_copied", label: "最多复制" },
];
export const COMMUNITY_STORAGE_KEYS = {
  posts: "quantbuddy.community.posts.v1", answers: "quantbuddy.community.answers.v1", engagement: "quantbuddy.community.engagement.v1", following: "quantbuddy.community.following.v1", factors: "quantbuddy.workspace.factors.v1", modules: "quantbuddy.workspace.modules.v1", forkedStrategies: "quantbuddy.workspace.forked-strategies.v1",
} as const;
export const DEMO_BACKTEST_ID = "qlib-demo-backtest-v1";
