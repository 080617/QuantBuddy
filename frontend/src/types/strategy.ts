export type StrategyStatus = "backtest-completed" | "draft";

export interface StrategyCardMetrics {
  totalReturn: string;
  annualizedReturn: string;
  sharpe: string;
  maxDrawdown: string;
}

export interface Strategy {
  id: string;
  name: string;
  status: StrategyStatus;
  updatedAt: string;
  model?: string;
  featureSet?: string;
  stockPool: string;
  portfolioRule?: string;
  configurationProgress?: number;
  backtestMetrics?: StrategyCardMetrics;
}
