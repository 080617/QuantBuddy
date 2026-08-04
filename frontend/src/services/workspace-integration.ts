import type {
  BacktestSummarySnapshot,
  WorkspaceFactorPublishPrefill,
  WorkspaceModulePublishPrefill,
  WorkspaceStrategyPublishPrefill,
} from "@/types/community";
import type {
  WorkspaceCompleteStrategy,
  WorkspaceFactor,
  WorkspaceModuleSelections,
  WorkspaceSnapshot,
  WorkspaceStrategyModule,
} from "@/types/workspace";

export interface CompleteStrategyPreselection {
  factorId?: string;
  factorSetId?: string;
  moduleId?: string;
}

export interface CompleteStrategyPreselectionResult {
  factorIds: string[];
  modules: WorkspaceModuleSelections;
  notices: string[];
}

const CORE_MODULE_TYPES = ["stock_selection", "weighting", "rebalance", "risk_control"] as const;

export function resolveCompleteStrategyPreselection(
  snapshot: WorkspaceSnapshot,
  currentFactorIds: readonly string[],
  currentModules: WorkspaceModuleSelections,
  preselection: CompleteStrategyPreselection,
): CompleteStrategyPreselectionResult {
  const factorIds = [...new Set(currentFactorIds)];
  const modules = { ...currentModules };
  const notices: string[] = [];

  if (preselection.factorId) {
    if (snapshot.factors.some((item) => item.id === preselection.factorId)) factorIds.push(preselection.factorId);
    else notices.push("指定的单个因子不存在或已被删除，未自动加入。");
  }
  if (preselection.factorSetId) {
    if (snapshot.factorSets.some((item) => item.id === preselection.factorSetId)) factorIds.push(preselection.factorSetId);
    else notices.push("指定的因子集不存在或已被删除，未自动加入。");
  }
  if (preselection.moduleId) {
    const moduleAsset = snapshot.strategyModules.find((item) => item.id === preselection.moduleId);
    if (!moduleAsset) notices.push("指定的策略模块不存在或已被删除，未自动加入。");
    else if (CORE_MODULE_TYPES.includes(moduleAsset.moduleType as (typeof CORE_MODULE_TYPES)[number])) {
      modules[moduleAsset.moduleType as keyof WorkspaceModuleSelections] = moduleAsset.id;
    } else {
      notices.push("该模块属于现金管理或交易执行阶段，当前完整策略的四个核心槽位暂不支持自动加入。");
    }
  }

  return { factorIds: [...new Set(factorIds)], modules, notices };
}

export function createFactorPublishPrefill(factor: WorkspaceFactor): WorkspaceFactorPublishPrefill {
  return {
    sourceWorkspaceId: factor.id,
    factorName: factor.name,
    factorType: factor.factorTypeLabel,
    factorTypeCode: factor.factorType,
    expression: factor.expression,
    description: factor.description ?? "",
  };
}

export function createModulePublishPrefill(moduleAsset: WorkspaceStrategyModule): WorkspaceModulePublishPrefill {
  return {
    sourceWorkspaceId: moduleAsset.id,
    moduleName: moduleAsset.name,
    moduleType: moduleAsset.moduleType,
    ruleSummary: moduleAsset.ruleSummary,
    ruleExpression: moduleAsset.ruleExpression,
    description: moduleAsset.description ?? "",
  };
}

export function createStrategyPublishPrefill(
  snapshot: WorkspaceSnapshot,
  strategy: WorkspaceCompleteStrategy,
  backtest?: BacktestSummarySnapshot,
): WorkspaceStrategyPublishPrefill {
  const assetNames = [...snapshot.factorSets, ...snapshot.factors]
    .filter((item) => strategy.factorAssetIds?.includes(item.id))
    .map((item) => item.name);
  const moduleName = (id?: string) => snapshot.strategyModules.find((item) => item.id === id)?.name;
  return {
    sourceWorkspaceId: strategy.id,
    strategyId: strategy.id,
    strategyName: strategy.name,
    description: strategy.description ?? "",
    configurationSnapshot: {
      strategyId: strategy.id,
      strategyName: strategy.name,
      universe: strategy.universe ?? "沪深300",
      featureSet: assetNames.length ? { name: assetNames.join(" + ") } : undefined,
      model: strategy.modelName,
      stockSelectionModule: moduleName(strategy.moduleSelections?.stock_selection) ?? strategy.portfolioRule,
      weightingModule: moduleName(strategy.moduleSelections?.weighting),
      rebalanceModule: moduleName(strategy.moduleSelections?.rebalance),
      riskControlModule: moduleName(strategy.moduleSelections?.risk_control),
    },
    backtest,
    backtestRef: backtest ? strategy.backtestRef : undefined,
  };
}
