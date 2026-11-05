import type {
  BacktestMetrics,
  DashboardData,
  HistoricalHoldings,
  LatestSignals,
  MonthlyReturn,
  NavPoint,
  OperationPreview,
  StrategyConfig,
} from "@/types/dashboard";
import type { Strategy } from "@/types/strategy";

export interface DashboardJsonSource {
  asOf: {
    backtestHoldingDate: string;
    latestSignalDate: string;
  };
  modelSetup: {
    model: string;
    featureSet: string;
    market: string;
    benchmark: string;
    strategy: string;
    topk: number;
    nDrop: number;
    onlyTradable: boolean;
    riskDegree: number;
    backtestPeriod: readonly string[];
  };
  performance: {
    totalReturn: number;
    cagr: number;
    sharpeRf0: number;
    maxDrawdown: number;
  };
  signalQuality: {
    IC: number;
    rankIC: number;
  };
}

export interface NavPointJsonSource {
  date: string;
  strategyNav: number;
  benchmarkNav: number;
  excessNav: number;
  strategyDrawdown: number;
}

export interface MonthlyReturnJsonSource {
  month: string;
  strategyReturn: number;
  benchmarkReturn: number;
}

export interface HoldingsJsonSource {
  date: string;
  status: string;
  accountValue: number;
  cash: number;
  cashRatio: number;
  holdingCount: number;
  holdings: Array<{
    instrument: string;
    name: string;
    weight: number;
    amount: number;
    referencePrice: number;
    marketValue: number;
    holdDays: number;
  }>;
}

export interface SignalsJsonSource {
  date: string;
  status: string;
  top5: Array<{
    rank: number;
    instrument: string;
    name: string;
    score: number;
    scorePercentile: number;
    currentlyHeld: boolean;
  }>;
}

export interface OperationJsonSource {
  type: string;
  label: string;
  buyCandidate?: OperationCandidateJsonSource | null;
  sellCandidate?: OperationCandidateJsonSource | null;
  previewOnly: boolean;
  note: string;
}

interface OperationCandidateJsonSource {
  rank?: number | null;
  instrument?: string | null;
  name?: string | null;
  score?: number | null;
}

function universeName(source: DashboardJsonSource): string {
  return source.modelSetup.benchmark.replace(/（.*$/, "");
}

function formatDate(date: string): string {
  const [year, month, day] = date.split("-");
  return `${year}年${Number(month)}月${Number(day)}日`;
}

function formatPercent(value: number): string {
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function adaptStrategyConfig(source: DashboardJsonSource): StrategyConfig {
  const universe = universeName(source);
  const { model, featureSet, strategy, topk, nDrop, onlyTradable, riskDegree, backtestPeriod } =
    source.modelSetup;

  return {
    strategyId: "strategy-hs300-lightgbm-top5",
    strategyName: `${universe} ${model} Top-${topk}`,
    universe,
    model,
    featureSet,
    backtestPeriod: [backtestPeriod[0], backtestPeriod[1]],
    portfolioRule: {
      name: strategy,
      topK: topk,
      nDrop,
      onlyTradable,
      riskDegree,
    },
  };
}

export function adaptBacktestMetrics(source: DashboardJsonSource): BacktestMetrics {
  return {
    totalReturn: source.performance.totalReturn,
    cagr: source.performance.cagr,
    sharpe: source.performance.sharpeRf0,
    maxDrawdown: source.performance.maxDrawdown,
    ic: source.signalQuality.IC,
    rankIc: source.signalQuality.rankIC,
  };
}

export function adaptNavCurve(
  source: readonly NavPointJsonSource[],
): readonly NavPoint[] {
  return source.map((point) => ({
    date: point.date,
    strategyNav: point.strategyNav,
    benchmarkNav: point.benchmarkNav,
    excessNav: point.excessNav,
    drawdown: point.strategyDrawdown,
  }));
}

export function adaptMonthlyReturns(
  source: readonly MonthlyReturnJsonSource[],
): readonly MonthlyReturn[] {
  return source.map((item) => ({ ...item }));
}

export function adaptHistoricalHoldings(
  source: HoldingsJsonSource,
): HistoricalHoldings {
  if (source.status !== "historical-backtest-position") {
    throw new Error(`Unsupported holdings status: ${source.status}`);
  }

  return {
    date: source.date,
    status: "historical-backtest-position",
    accountValue: source.accountValue,
    cash: source.cash,
    cashRatio: source.cashRatio,
    holdingCount: source.holdingCount,
    holdings: source.holdings.map((holding) => ({
      stock: holding.instrument,
      stockName: holding.name,
      weight: holding.weight,
      marketValue: holding.marketValue,
      amount: holding.amount,
      referencePrice: holding.referencePrice,
      holdDays: holding.holdDays,
    })),
  };
}

export function adaptLatestSignals(source: SignalsJsonSource): LatestSignals {
  if (source.status !== "historical-model-output") {
    throw new Error(`Unsupported signal status: ${source.status}`);
  }

  return {
    date: source.date,
    status: "historical-model-output",
    signals: source.top5.map((signal) => ({
      stock: signal.instrument,
      stockName: signal.name,
      score: signal.score,
      rank: signal.rank,
      scorePercentile: signal.scorePercentile,
      currentlyHeld: signal.currentlyHeld,
    })),
  };
}

export function adaptOperationPreview(
  source: OperationJsonSource,
): OperationPreview {
  const adaptCandidate = (
    candidate: OperationCandidateJsonSource | null | undefined,
  ): OperationPreview["buyCandidate"] => {
    if (!candidate || (!candidate.instrument && !candidate.name)) return null;
    return {
      stock: candidate.instrument ?? "",
      stockName: candidate.name ?? "",
      score: candidate.score ?? null,
      rank: candidate.rank ?? null,
    };
  };

  return {
    type: source.type,
    label: source.label,
    buyCandidate: adaptCandidate(source.buyCandidate),
    sellCandidate: adaptCandidate(source.sellCandidate),
    previewOnly: source.previewOnly,
    note: source.note,
  };
}

export function adaptStrategyCard(source: DashboardJsonSource): Strategy {
  const strategy = adaptStrategyConfig(source);
  const metrics = adaptBacktestMetrics(source);

  return {
    id: strategy.strategyId,
    name: strategy.strategyName,
    status: "backtest-completed",
    updatedAt: formatDate(source.asOf.latestSignalDate),
    model: strategy.model,
    featureSet: strategy.featureSet,
    stockPool: strategy.universe,
    portfolioRule: `${strategy.portfolioRule.name} · Top-${strategy.portfolioRule.topK}`,
    backtestMetrics: {
      totalReturn: formatPercent(metrics.totalReturn),
      annualizedReturn: formatPercent(metrics.cagr),
      sharpe: metrics.sharpe.toFixed(2),
      maxDrawdown: formatPercent(metrics.maxDrawdown),
    },
  };
}

export function adaptDashboardData(
  dashboard: DashboardJsonSource,
  navCurve: readonly NavPointJsonSource[],
  monthlyReturns: readonly MonthlyReturnJsonSource[],
  holdings: HoldingsJsonSource,
  signals: SignalsJsonSource,
  operation: OperationJsonSource,
): DashboardData {
  return {
    strategy: adaptStrategyConfig(dashboard),
    backtest: adaptBacktestMetrics(dashboard),
    navCurve: adaptNavCurve(navCurve),
    monthlyReturns: adaptMonthlyReturns(monthlyReturns),
    currentHoldings: adaptHistoricalHoldings(holdings),
    latestSignals: adaptLatestSignals(signals),
    operationPreview: adaptOperationPreview(operation),
    holdingDate: dashboard.asOf.backtestHoldingDate,
    signalDate: dashboard.asOf.latestSignalDate,
  };
}
