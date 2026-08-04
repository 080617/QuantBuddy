import { STRATEGY_MODULE_TYPE_LABELS } from "@/lib/community-constants";
import { createJsonStorageCodec, readLocalStorage, writeLocalStorage } from "@/lib/storage";
import { communityService } from "@/services/community-service";
import { dataService } from "@/services/data-service";
import type { CommunityPost } from "@/types/community";
import type {
  WorkspaceCompleteStrategy, WorkspaceCompleteStrategyInput, WorkspaceFactor, WorkspaceFactorInput,
  WorkspaceFactorSet, WorkspaceFactorSetInput, WorkspaceSnapshot, WorkspaceStrategyModule,
  WorkspaceStrategyModuleInput, WorkspaceBacktestContext, WorkspaceValidationErrorCode,
} from "@/types/workspace";

const KEYS = {
  strategies: "quantbuddy.workspace.owned-strategies.v1",
  modules: "quantbuddy.workspace.owned-modules.v1",
  factors: "quantbuddy.workspace.owned-factors.v1",
  factorSets: "quantbuddy.workspace.factor-sets.v1",
} as const;

const strategiesCodec = createJsonStorageCodec<WorkspaceCompleteStrategy[]>();
const modulesCodec = createJsonStorageCodec<WorkspaceStrategyModule[]>();
const factorsCodec = createJsonStorageCodec<WorkspaceFactor[]>();
const factorSetsCodec = createJsonStorageCodec<WorkspaceFactorSet[]>();

const FACTOR_TYPE_LABELS: Record<string, string> = {
  momentum: "动量因子", volatility: "波动率因子", volume: "成交量因子", price: "价格因子",
  technical: "技术因子", composite: "复合因子", other: "其他",
};

const BUILTIN_MODULES: WorkspaceStrategyModule[] = [
  { id: "builtin-stock-top5", name: "Top-5 选股模块", origin: "builtin", status: "ready", moduleType: "stock_selection", ruleSummary: "按模型预测分数选择排名前 5 的股票。", ruleExpression: "TopK(model_score, 5)", usageCount: 1, locked: true },
  { id: "builtin-equal-weight", name: "等权分配模块", origin: "builtin", status: "ready", moduleType: "weighting", ruleSummary: "对入选股票进行等权配置。", ruleExpression: "Weight = 1 / SelectedCount", usageCount: 1, locked: true },
  { id: "builtin-daily-rebalance", name: "每日调仓模块", origin: "builtin", status: "ready", moduleType: "rebalance", ruleSummary: "每个交易日根据最新模型信号调仓。", ruleExpression: "Rebalance(every='1d')", usageCount: 1, locked: true },
  { id: "builtin-market-risk", name: "市场趋势降仓模块", origin: "builtin", status: "ready", moduleType: "risk_control", ruleSummary: "市场趋势走弱时降低组合目标仓位。", ruleExpression: "If(IndexClose < MA(IndexClose, 120), PortfolioWeight * 0.5, PortfolioWeight)", usageCount: 1, locked: true },
];

const BUILTIN_FACTORS: WorkspaceFactor[] = [
  { id: "builtin-mom20", assetKind: "factor", name: "20日动量", origin: "builtin", status: "ready", factorType: "momentum", factorTypeLabel: "动量因子", expression: "$close / Ref($close, 20) - 1", verificationStatus: "not_verified", usageCount: 0, locked: true },
  { id: "builtin-mom60", assetKind: "factor", name: "60日动量", origin: "builtin", status: "ready", factorType: "momentum", factorTypeLabel: "动量因子", expression: "$close / Ref($close, 60) - 1", verificationStatus: "not_verified", usageCount: 0, locked: true },
  { id: "builtin-volume-change", assetKind: "factor", name: "成交量变化率", origin: "builtin", status: "ready", factorType: "volume", factorTypeLabel: "成交量因子", expression: "$volume / Ref($volume, 5) - 1", verificationStatus: "not_verified", usageCount: 0, locked: true },
  { id: "builtin-ma-bias", assetKind: "factor", name: "均线偏离度", origin: "builtin", status: "ready", factorType: "technical", factorTypeLabel: "技术因子", expression: "$close / MA($close, 20) - 1", verificationStatus: "not_verified", usageCount: 0, locked: true },
  { id: "builtin-turnover", assetKind: "factor", name: "换手率", origin: "builtin", status: "ready", factorType: "volume", factorTypeLabel: "成交量因子", expression: "$turnover / Ref($cap, 1)", verificationStatus: "not_verified", usageCount: 0, locked: true },
];

const ALPHA158: WorkspaceFactorSet = {
  id: "qlib-alpha158", assetKind: "factor_set", name: "Qlib Alpha158", origin: "builtin", status: "ready",
  description: "Qlib 内置的 158 个技术特征，作为因子集/特征集使用。",
  factorIds: Array.from({ length: 158 }, (_, index) => `qlib-alpha158-${index + 1}`), factorCount: 158,
  usageCount: 1, locked: true,
};

function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return `${prefix}-${crypto.randomUUID()}`;
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
function authorName(postMap: Map<string, CommunityPost>, postId: string) { return postMap.get(postId)?.author.displayName ?? "Anna Zhang"; }
function localStrategies() { return readLocalStorage(KEYS.strategies, [], strategiesCodec); }
function localModules() { return readLocalStorage(KEYS.modules, [], modulesCodec); }
function localFactors() { return readLocalStorage(KEYS.factors, [], factorsCodec); }
function localFactorSets() { return readLocalStorage(KEYS.factorSets, [], factorSetsCodec); }
function replaceById<T extends { id: string }>(items: T[], value: T) { return items.some((item) => item.id === value.id) ? items.map((item) => item.id === value.id ? value : item) : [...items, value]; }

function demoCompatible(input: WorkspaceCompleteStrategyInput) {
  return input.universe === "沪深300" && input.modelId === "lightgbm" && input.factorAssetIds.includes("qlib-alpha158")
    && input.moduleSelections.stock_selection === "builtin-stock-top5"
    && input.moduleSelections.weighting === "builtin-equal-weight"
    && input.moduleSelections.rebalance === "builtin-daily-rebalance"
    && input.moduleSelections.risk_control === "builtin-market-risk";
}

export class WorkspaceValidationError extends Error {
  constructor(public readonly code: WorkspaceValidationErrorCode, message: string, public readonly field = "factorIds") {
    super(message);
    this.name = "WorkspaceValidationError";
  }
}

export interface WorkspaceService {
  getSnapshot(): Promise<WorkspaceSnapshot>;
  getCompleteStrategy(id: string): Promise<WorkspaceCompleteStrategy | null>;
  getStrategyModule(id: string): Promise<WorkspaceStrategyModule | null>;
  getFactor(id: string): Promise<WorkspaceFactor | null>;
  getFactorSet(id: string): Promise<WorkspaceFactorSet | null>;
  resolveBacktestContext(id?: string): Promise<WorkspaceBacktestContext>;
  canRunDemoBacktest(input: WorkspaceCompleteStrategyInput): boolean;
  createCompleteStrategy(input: WorkspaceCompleteStrategyInput): Promise<WorkspaceCompleteStrategy>;
  updateCompleteStrategy(id: string, input: WorkspaceCompleteStrategyInput): Promise<WorkspaceCompleteStrategy>;
  createStrategyModule(input: WorkspaceStrategyModuleInput): Promise<WorkspaceStrategyModule>;
  updateStrategyModule(id: string, input: WorkspaceStrategyModuleInput): Promise<WorkspaceStrategyModule>;
  createFactor(input: WorkspaceFactorInput): Promise<WorkspaceFactor>;
  updateFactor(id: string, input: WorkspaceFactorInput): Promise<WorkspaceFactor>;
  createFactorSet(input: WorkspaceFactorSetInput): Promise<WorkspaceFactorSet>;
  updateFactorSet(id: string, input: WorkspaceFactorSetInput): Promise<WorkspaceFactorSet>;
  removeCompleteStrategy(id: string): Promise<boolean>;
  removeStrategyModule(id: string): Promise<boolean>;
  removeFactor(id: string): Promise<boolean>;
  removeFactorSet(id: string): Promise<boolean>;
  removeCommunityStrategy(sourcePostId: string): Promise<boolean>;
  removeCommunityModule(sourcePostId: string): Promise<boolean>;
  removeCommunityFactor(sourcePostId: string): Promise<boolean>;
}

export const workspaceService: WorkspaceService = {
  async getSnapshot() {
    const [strategy, metrics, strategies, posts, forks, savedModules, savedFactors] = await Promise.all([
      dataService.getStrategySummary(), dataService.getBacktestMetrics(), dataService.getStrategies(), communityService.getPosts(),
      communityService.getForkedStrategies(), communityService.getSavedModules(), communityService.getSavedFactors(),
    ]);
    const postMap = new Map(posts.map((post) => [post.id, post]));
    const locals = localStrategies();
    const baselineStored = locals.find((item) => item.id === strategy.strategyId);
    const ownedCard = strategies.find((item) => item.id === strategy.strategyId) ?? strategies[0];
    const baselineBase: WorkspaceCompleteStrategy = baselineStored ?? {
      id: strategy.strategyId, name: strategy.strategyName, origin: "owned", status: "backtested", requiresRebacktest: false,
      universe: strategy.universe, factorAssetIds: ["qlib-alpha158"], modelId: "lightgbm", featureSetName: strategy.featureSet,
      modelName: strategy.model, portfolioRule: `Top-${strategy.portfolioRule.topK}`,
      moduleSelections: { stock_selection: "builtin-stock-top5", weighting: "builtin-equal-weight", rebalance: "builtin-daily-rebalance", risk_control: "builtin-market-risk" },
      totalReturn: metrics.totalReturn, cagr: metrics.cagr, sharpe: metrics.sharpe, maxDrawdown: metrics.maxDrawdown,
      updatedAt: ownedCard?.updatedAt, locked: true,
    };
    const baseline: WorkspaceCompleteStrategy = {
      ...baselineBase,
      id: strategy.strategyId,
      status: "backtested",
      requiresRebacktest: false,
      backtestRef: "dashboard_v1",
      totalReturn: metrics.totalReturn,
      cagr: metrics.cagr,
      sharpe: metrics.sharpe,
      maxDrawdown: metrics.maxDrawdown,
      locked: true,
    };
    const localMap = new Map(locals.map((item) => [item.id, item]));
    const communityStrategies = forks.map((item) => localMap.get(item.id) ?? ({
      id: item.id, name: item.name, origin: "community_fork", status: "draft", requiresRebacktest: true,
      sourcePostId: item.sourcePostId, sourceAuthorName: authorName(postMap, item.sourcePostId), universe: item.configurationSnapshot.universe,
      factorAssetIds: item.configurationSnapshot.featureSet?.name === "Qlib Alpha158" ? ["qlib-alpha158"] : [],
      featureSetName: item.configurationSnapshot.featureSet?.name, modelId: item.configurationSnapshot.model?.toLowerCase(),
      modelName: item.configurationSnapshot.model, portfolioRule: item.configurationSnapshot.stockSelectionModule, updatedAt: item.forkedAt,
    } satisfies WorkspaceCompleteStrategy));
    const ownedLocalStrategies = locals.filter((item) => item.id !== strategy.strategyId && item.origin === "owned");

    const localModuleMap = new Map(localModules().map((item) => [item.id, item]));
    const communityModules: WorkspaceStrategyModule[] = savedModules.map((item) => localModuleMap.get(item.id) ?? ({
      id: item.id, name: item.moduleName, origin: "community_fork", status: "ready", moduleType: item.moduleType,
      ruleSummary: item.ruleSummary, ruleExpression: item.ruleExpression, description: item.description,
      sourcePostId: item.sourcePostId, sourceAuthorName: authorName(postMap, item.sourcePostId), usageCount: 0,
    }));
    const ownedModules = localModules().filter((item) => item.origin === "owned");

    const localFactorMap = new Map(localFactors().map((item) => [item.id, item]));
    const communityFactors: WorkspaceFactor[] = savedFactors.map((item) => localFactorMap.get(item.id) ?? ({
      id: item.id, assetKind: "factor", name: item.factorName, origin: "community_fork", status: "ready",
      factorType: "other", factorTypeLabel: item.factorType, expression: item.expression, description: item.description,
      verificationStatus: "not_verified", sourcePostId: item.sourcePostId, sourceAuthorName: authorName(postMap, item.sourcePostId), usageCount: 0,
    }));
    const ownedFactors = localFactors().filter((item) => item.origin === "owned");
    const completeStrategies = [baseline, ...ownedLocalStrategies, ...communityStrategies];
    const strategyModules = [...BUILTIN_MODULES, ...ownedModules, ...communityModules];
    const factors = [...BUILTIN_FACTORS, ...ownedFactors, ...communityFactors];
    const factorSets = [ALPHA158, ...localFactorSets()];
    return { completeStrategies, strategyModules, factors, factorSets, counts: { completeStrategies: completeStrategies.length, strategyModules: strategyModules.length, factorsAndFactorSets: factors.length + factorSets.length } };
  },
  async getCompleteStrategy(id) { return (await this.getSnapshot()).completeStrategies.find((item) => item.id === id) ?? null; },
  async getStrategyModule(id) { return (await this.getSnapshot()).strategyModules.find((item) => item.id === id) ?? null; },
  async getFactor(id) { return (await this.getSnapshot()).factors.find((item) => item.id === id) ?? null; },
  async getFactorSet(id) { return (await this.getSnapshot()).factorSets.find((item) => item.id === id) ?? null; },
  async resolveBacktestContext(id) {
    const snapshot = await this.getSnapshot();
    const strategy = id
      ? snapshot.completeStrategies.find((item) => item.id === id)
      : snapshot.completeStrategies.find((item) => item.backtestRef === "dashboard_v1");
    if (!strategy) return { status: "not_found", strategy: null };
    if (strategy.status === "backtested" && !strategy.requiresRebacktest && strategy.backtestRef === "dashboard_v1") {
      return { status: "ready", strategy, backtestRef: "dashboard_v1" };
    }
    return { status: "not_backtested", strategy };
  },
  canRunDemoBacktest: demoCompatible,
  async createCompleteStrategy(input) { return this.updateCompleteStrategy(createId("strategy"), input); },
  async updateCompleteStrategy(id, input) {
    if (!input.name.trim()) throw new Error("请填写策略名称");
    if (input.status === "backtested" && !demoCompatible(input)) throw new Error("当前配置不支持真实 Demo 回测");
    const previous = await this.getCompleteStrategy(id);
    const snapshot = await this.getSnapshot();
    const factorNames = [...snapshot.factors, ...snapshot.factorSets].filter((item) => input.factorAssetIds.includes(item.id)).map((item) => item.name);
    const stockModule = snapshot.strategyModules.find((item) => item.id === input.moduleSelections.stock_selection);
    const metrics = input.status === "backtested" ? await dataService.getBacktestMetrics() : null;
    const value: WorkspaceCompleteStrategy = {
      id, name: input.name.trim(), description: input.description?.trim(), origin: previous?.origin ?? "owned",
      status: input.status, requiresRebacktest: input.status !== "backtested", sourcePostId: previous?.sourcePostId,
      sourceAuthorName: previous?.sourceAuthorName, universe: input.universe, factorAssetIds: input.factorAssetIds,
      moduleSelections: input.moduleSelections, modelId: input.modelId, modelName: input.modelName,
      featureSetName: factorNames.join(" + "), portfolioRule: stockModule?.name,
      totalReturn: metrics?.totalReturn, cagr: metrics?.cagr, sharpe: metrics?.sharpe, maxDrawdown: metrics?.maxDrawdown,
      backtestRef: input.status === "backtested" ? "dashboard_v1" : undefined,
      updatedAt: new Date().toISOString().slice(0, 10), locked: previous?.locked,
    };
    writeLocalStorage(KEYS.strategies, replaceById(localStrategies(), value), strategiesCodec); return value;
  },
  async createStrategyModule(input) { return this.updateStrategyModule(createId("module"), input); },
  async updateStrategyModule(id, input) {
    if (!input.name.trim() || !input.ruleExpression.trim()) throw new Error("请填写模块名称和模块规则");
    const previous = await this.getStrategyModule(id);
    if (previous?.locked) throw new Error("平台内置模块不可修改");
    const value: WorkspaceStrategyModule = { id, name: input.name.trim(), description: input.description?.trim(), origin: previous?.origin ?? "owned", status: input.status, moduleType: input.moduleType, ruleSummary: input.ruleSummary.trim() || input.description?.trim() || STRATEGY_MODULE_TYPE_LABELS[input.moduleType], ruleExpression: input.ruleExpression.trim(), sourcePostId: previous?.sourcePostId, sourceAuthorName: previous?.sourceAuthorName, usageCount: previous?.usageCount ?? 0 };
    writeLocalStorage(KEYS.modules, replaceById(localModules(), value), modulesCodec); return value;
  },
  async createFactor(input) { return this.updateFactor(createId("factor"), input); },
  async updateFactor(id, input) {
    if (!input.name.trim() || !input.expression.trim()) throw new Error("请填写因子名称和因子公式");
    const previous = await this.getFactor(id); if (previous?.locked) throw new Error("平台内置因子不可修改");
    const value: WorkspaceFactor = { id, assetKind: "factor", name: input.name.trim(), description: input.description?.trim(), origin: previous?.origin ?? "owned", status: input.status, factorType: input.factorType, factorTypeLabel: input.factorTypeLabel || FACTOR_TYPE_LABELS[input.factorType] || "其他", expression: input.expression.trim(), verificationStatus: previous?.verificationStatus ?? "not_verified", sourcePostId: previous?.sourcePostId, sourceAuthorName: previous?.sourceAuthorName, usageCount: previous?.usageCount ?? 0 };
    writeLocalStorage(KEYS.factors, replaceById(localFactors(), value), factorsCodec); return value;
  },
  async createFactorSet(input) { return this.updateFactorSet(createId("factor-set"), input); },
  async updateFactorSet(id, input) {
    if (!input.name.trim()) throw new Error("请填写因子集名称");
    const previous = await this.getFactorSet(id); if (previous?.locked) throw new Error("平台内置因子集不可修改");
    const factorIds = [...new Set(input.factorIds)];
    if (factorIds.length < 2) throw new WorkspaceValidationError("FACTOR_SET_TOO_SMALL", "因子集至少选择两个不同的单个因子");
    const snapshot = await this.getSnapshot();
    for (const factorId of factorIds) {
      if (snapshot.factorSets.some((item) => item.id === factorId)) {
        throw new WorkspaceValidationError("FACTOR_SET_NESTING_NOT_ALLOWED", "因子集不能引用另一个因子集");
      }
      if (!snapshot.factors.some((item) => item.id === factorId)) {
        throw new WorkspaceValidationError("FACTOR_SET_REFERENCE_NOT_FOUND", `因子 ${factorId} 不存在或已被删除`);
      }
    }
    const value: WorkspaceFactorSet = { id, assetKind: "factor_set", name: input.name.trim(), description: input.description?.trim(), origin: "owned", status: input.status, factorIds, factorCount: factorIds.length, usageCount: previous?.usageCount ?? 0 };
    writeLocalStorage(KEYS.factorSets, replaceById(localFactorSets(), value), factorSetsCodec); return value;
  },
  async removeCompleteStrategy(id) {
    const item = await this.getCompleteStrategy(id); if (!item || item.locked) return false;
    writeLocalStorage(KEYS.strategies, localStrategies().filter((value) => value.id !== id), strategiesCodec);
    return item.origin === "community_fork" && item.sourcePostId ? communityService.removeForkedStrategyFromWorkspace(item.sourcePostId) : true;
  },
  async removeStrategyModule(id) {
    const item = await this.getStrategyModule(id); if (!item || item.locked) return false;
    writeLocalStorage(KEYS.modules, localModules().filter((value) => value.id !== id), modulesCodec);
    return item.origin === "community_fork" && item.sourcePostId ? communityService.removeModuleFromWorkspace(item.sourcePostId) : true;
  },
  async removeFactor(id) {
    const item = await this.getFactor(id); if (!item || item.locked) return false;
    writeLocalStorage(KEYS.factors, localFactors().filter((value) => value.id !== id), factorsCodec);
    return item.origin === "community_fork" && item.sourcePostId ? communityService.removeFactorFromWorkspace(item.sourcePostId) : true;
  },
  async removeFactorSet(id) { const item = await this.getFactorSet(id); if (!item || item.locked) return false; writeLocalStorage(KEYS.factorSets, localFactorSets().filter((value) => value.id !== id), factorSetsCodec); return true; },
  removeCommunityStrategy: (sourcePostId) => communityService.removeForkedStrategyFromWorkspace(sourcePostId),
  removeCommunityModule: (sourcePostId) => communityService.removeModuleFromWorkspace(sourcePostId),
  removeCommunityFactor: (sourcePostId) => communityService.removeFactorFromWorkspace(sourcePostId),
};
