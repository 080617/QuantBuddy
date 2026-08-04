export interface PortfolioRule {
  name: string;
  topK: number;
  nDrop: number;
  onlyTradable: boolean;
  riskDegree: number;
}

export interface StrategyConfig {
  strategyId: string;
  strategyName: string;
  universe: string;
  model: string;
  featureSet: string;
  backtestPeriod: readonly [string, string];
  portfolioRule: PortfolioRule;
}

export interface BacktestMetrics {
  totalReturn: number;
  cagr: number;
  sharpe: number;
  maxDrawdown: number;
  ic: number;
  rankIc: number;
}

export interface NavPoint {
  date: string;
  strategyNav: number;
  benchmarkNav: number;
  excessNav: number;
  drawdown: number;
}

export interface MonthlyReturn {
  month: string;
  strategyReturn: number;
  benchmarkReturn: number;
}

export interface Holding {
  stock: string;
  stockName: string;
  weight: number;
  marketValue: number;
  amount: number;
  referencePrice: number;
  holdDays: number;
}

export interface HistoricalHoldings {
  date: string;
  status: "historical-backtest-position";
  accountValue: number;
  cash: number;
  cashRatio: number;
  holdingCount: number;
  holdings: readonly Holding[];
}

export interface Signal {
  stock: string;
  stockName: string;
  score: number;
  rank: number;
  scorePercentile: number;
  currentlyHeld: boolean;
}

export interface LatestSignals {
  date: string;
  status: "historical-model-output";
  signals: readonly Signal[];
}

export interface OperationCandidate {
  stock: string;
  stockName: string;
  score: number;
  rank: number;
}

export interface OperationPreview {
  type: string;
  label: string;
  buyCandidate: OperationCandidate;
  sellCandidate: OperationCandidate;
  previewOnly: boolean;
  note: string;
}

export interface DashboardData {
  strategy: StrategyConfig;
  backtest: BacktestMetrics;
  navCurve: readonly NavPoint[];
  monthlyReturns: readonly MonthlyReturn[];
  currentHoldings: HistoricalHoldings;
  latestSignals: LatestSignals;
  operationPreview: OperationPreview;
  holdingDate: string;
  signalDate: string;
}
