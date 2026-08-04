export type CommunityContentType = "factor" | "strategy_module" | "complete_strategy" | "question";

export interface CommunityAuthor {
  id: string;
  displayName: string;
  handle?: string;
  avatarUrl?: string;
  bio?: string;
  followerCount: number;
  following: boolean;
}

export interface CommunityEngagement {
  starCount: number;
  answerCount: number;
  bookmarkCount: number;
  forkCount?: number;
  useCount?: number;
  starred: boolean;
  bookmarked: boolean;
}

export interface CommunityPostBase {
  id: string;
  type: CommunityContentType;
  author: CommunityAuthor;
  title: string;
  summary?: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  engagement: CommunityEngagement;
  status: "draft" | "published";
  sourceWorkspaceId?: string;
}

export interface FactorVerificationSummary {
  ic?: number;
  rankIc?: number;
  verifiedAt?: string;
  verificationStatus: "not_verified" | "pending" | "demo_verified" | "verified";
}

export interface FactorPost extends CommunityPostBase {
  type: "factor";
  factorName: string;
  factorType: string;
  factorTypeCode?: string;
  expression: string;
  description?: string;
  requiredFields?: string[];
  verification?: FactorVerificationSummary;
}

export type StrategyModuleType = "stock_selection" | "weighting" | "rebalance" | "risk_control" | "cash_management" | "execution";
export type StrategyStage = "stock_selection_stage" | "portfolio_construction_stage" | "rebalance_stage" | "risk_control_stage" | "trade_execution_stage";

export interface StrategyModulePost extends CommunityPostBase {
  type: "strategy_module";
  moduleName: string;
  moduleType: StrategyModuleType;
  applicableStage: StrategyStage;
  ruleSummary: string;
  ruleExpression: string;
  description?: string;
}

export interface StrategyConfigurationSnapshot {
  strategyId: string;
  strategyName: string;
  universe: string;
  featureSet?: { id?: string; name: string; featureCount?: number };
  model?: string;
  stockSelectionModule?: string;
  weightingModule?: string;
  rebalanceModule?: string;
  riskControlModule?: string;
}

export interface BacktestSummarySnapshot {
  backtestId: string;
  version: string;
  dateFrom: string;
  dateTo: string;
  totalReturn: number;
  cagr: number;
  sharpe: number;
  maxDrawdown: number;
}

export interface CompleteStrategyPost extends CommunityPostBase {
  type: "complete_strategy";
  sourceStrategyId: string;
  communityTitle: string;
  oneLineIntroduction: string;
  detailedDescription?: string;
  configurationSnapshot: StrategyConfigurationSnapshot;
  backtestSnapshot?: BacktestSummarySnapshot;
  backtestRef?: "dashboard_v1";
}

export interface QuestionPost extends CommunityPostBase { type: "question"; content: string; }
export type CommunityPost = FactorPost | StrategyModulePost | CompleteStrategyPost | QuestionPost;

export interface CommunityAnswer {
  id: string;
  postId: string;
  author: CommunityAuthor;
  content: string;
  createdAt: string;
  starCount: number;
  starred: boolean;
}

export interface SavedFactor {
  id: string;
  sourcePostId: string;
  sourceAuthorId: string;
  factorName: string;
  factorType: string;
  expression: string;
  description?: string;
  tags: string[];
  status: "unused";
  savedAt: string;
}

export interface SavedStrategyModule {
  id: string;
  sourcePostId: string;
  sourceAuthorId: string;
  moduleName: string;
  moduleType: StrategyModuleType;
  applicableStage: StrategyStage;
  ruleSummary: string;
  ruleExpression: string;
  description?: string;
  status: "unused";
  savedAt: string;
}

export interface ForkedCompleteStrategy {
  id: string;
  sourcePostId: string;
  sourceStrategyId: string;
  sourceAuthorId: string;
  name: string;
  configurationSnapshot: StrategyConfigurationSnapshot;
  sourceBacktestSnapshot?: BacktestSummarySnapshot;
  status: "draft";
  requiresRebacktest: true;
  forkedAt: string;
}

export interface CommunityWorkspaceState {
  factorPostIds: string[];
  modulePostIds: string[];
  forkedStrategyPostIds: string[];
}

export type CommunityFilterValue = "recommended" | CommunityContentType | "following";
export type CommunitySortValue = "recommended" | "latest" | "weekly_popular" | "most_copied";
export interface CommunityPostFilters { type?: CommunityContentType; followingOnly?: boolean; sort?: CommunitySortValue; }

export interface CreateFactorPostInput { factorName: string; factorType: string; factorTypeCode?: string; expression: string; description?: string; tags?: string[]; status?: "draft" | "published"; draftId?: string; sourceWorkspaceId?: string; }
export interface CreateStrategyModulePostInput { moduleName: string; moduleType: StrategyModuleType; ruleSummary: string; ruleExpression: string; description?: string; tags?: string[]; status?: "draft" | "published"; draftId?: string; sourceWorkspaceId?: string; }
export interface CreateCompleteStrategyPostInput { sourceStrategyId: string; sourceWorkspaceId: string; configurationSnapshot: StrategyConfigurationSnapshot; backtestSnapshot?: BacktestSummarySnapshot; backtestRef?: "dashboard_v1"; communityTitle: string; oneLineIntroduction: string; detailedDescription?: string; tags?: string[]; status?: "draft" | "published"; draftId?: string; }
export interface CreateQuestionPostInput { title: string; content?: string; tags?: string[]; status?: "draft" | "published"; draftId?: string; }

export interface WorkspaceFactorPublishPrefill {
  sourceWorkspaceId: string;
  factorName: string;
  factorType: string;
  factorTypeCode: string;
  expression: string;
  description: string;
}

export interface WorkspaceModulePublishPrefill {
  sourceWorkspaceId: string;
  moduleName: string;
  moduleType: StrategyModuleType;
  ruleSummary: string;
  ruleExpression: string;
  description: string;
}

export interface WorkspaceStrategyPublishPrefill {
  sourceWorkspaceId: string;
  strategyId: string;
  strategyName: string;
  description: string;
  configurationSnapshot: StrategyConfigurationSnapshot;
  backtest?: BacktestSummarySnapshot;
  backtestRef?: "dashboard_v1";
}

/** Legacy auxiliary-service shape retained for compatibility with existing pages. */
export interface CommunityStrategySummary {
  id: string;
  name: string;
  author: string;
  description: string;
  tags: string[];
}
