import type { StrategyModuleType } from "@/types/community";

export type WorkspaceOrigin = "owned" | "community_fork" | "builtin";
export type WorkspaceAssetStatus = "draft" | "ready";

export interface WorkspaceModuleSelections {
  stock_selection?: string;
  weighting?: string;
  rebalance?: string;
  risk_control?: string;
}

export interface WorkspaceCompleteStrategy {
  id: string;
  name: string;
  description?: string;
  origin: "owned" | "community_fork";
  status: "backtested" | "draft";
  requiresRebacktest: boolean;
  sourcePostId?: string;
  sourceAuthorName?: string;
  universe?: string;
  factorAssetIds?: string[];
  moduleSelections?: WorkspaceModuleSelections;
  modelId?: string;
  featureSetName?: string;
  modelName?: string;
  portfolioRule?: string;
  totalReturn?: number;
  cagr?: number;
  sharpe?: number;
  maxDrawdown?: number;
  backtestRef?: "dashboard_v1";
  updatedAt?: string;
  locked?: boolean;
}

export type WorkspaceBacktestContext =
  | { status: "ready"; strategy: WorkspaceCompleteStrategy; backtestRef: "dashboard_v1" }
  | { status: "not_backtested"; strategy: WorkspaceCompleteStrategy }
  | { status: "not_found"; strategy: null };

export type WorkspaceValidationErrorCode =
  | "FACTOR_SET_TOO_SMALL"
  | "FACTOR_SET_REFERENCE_NOT_FOUND"
  | "FACTOR_SET_NESTING_NOT_ALLOWED";

export interface WorkspaceStrategyModule {
  id: string;
  name: string;
  description?: string;
  origin: WorkspaceOrigin;
  status: WorkspaceAssetStatus;
  moduleType: StrategyModuleType;
  ruleSummary: string;
  ruleExpression: string;
  sourcePostId?: string;
  sourceAuthorName?: string;
  usageCount?: number;
  locked?: boolean;
}

export type WorkspaceFactorType = "momentum" | "volatility" | "volume" | "price" | "technical" | "composite" | "other";

export interface WorkspaceFactor {
  id: string;
  assetKind: "factor";
  name: string;
  description?: string;
  origin: WorkspaceOrigin;
  status: WorkspaceAssetStatus;
  factorType: WorkspaceFactorType;
  factorTypeLabel: string;
  expression: string;
  verificationStatus: "not_verified" | "pending" | "demo_verified" | "verified";
  sourcePostId?: string;
  sourceAuthorName?: string;
  usageCount?: number;
  locked?: boolean;
}

export interface WorkspaceFactorSet {
  id: string;
  assetKind: "factor_set";
  name: string;
  origin: "owned" | "builtin";
  status: WorkspaceAssetStatus;
  description?: string;
  factorIds: string[];
  factorCount: number;
  usageCount?: number;
  locked?: boolean;
}

export interface WorkspaceCompleteStrategyInput {
  name: string;
  description?: string;
  universe: "沪深300";
  factorAssetIds: string[];
  modelId: string;
  modelName: string;
  moduleSelections: WorkspaceModuleSelections;
  status: "backtested" | "draft";
}

export interface WorkspaceStrategyModuleInput {
  name: string;
  description?: string;
  moduleType: StrategyModuleType;
  ruleSummary: string;
  ruleExpression: string;
  status: WorkspaceAssetStatus;
}

export interface WorkspaceFactorInput {
  name: string;
  description?: string;
  factorType: WorkspaceFactorType;
  factorTypeLabel: string;
  expression: string;
  status: WorkspaceAssetStatus;
}

export interface WorkspaceFactorSetInput {
  name: string;
  description?: string;
  factorIds: string[];
  status: WorkspaceAssetStatus;
}

export interface WorkspaceSnapshot {
  completeStrategies: WorkspaceCompleteStrategy[];
  strategyModules: WorkspaceStrategyModule[];
  factors: WorkspaceFactor[];
  factorSets: WorkspaceFactorSet[];
  counts: { completeStrategies: number; strategyModules: number; factorsAndFactorSets: number };
}
