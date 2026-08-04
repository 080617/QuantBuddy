import type { Strategy } from "@/types/strategy";

export const STRATEGY_DATA: readonly Strategy[] = [
  {
    id: "strategy-hs300-lightgbm-top5",
    name: "沪深300 LightGBM Top-5",
    status: "backtest-completed",
    updatedAt: "2026年7月31日",
    model: "LightGBM",
    featureSet: "Alpha158",
    stockPool: "沪深300",
    portfolioRule: "Top-5",
    backtestMetrics: {
      totalReturn: "--",
      annualizedReturn: "--",
      sharpe: "--",
      maxDrawdown: "--",
    },
  },
  {
    id: "strategy-new-draft",
    name: "我的新策略",
    status: "draft",
    updatedAt: "2026年7月31日",
    configurationProgress: 40,
    stockPool: "沪深300",
  },
];
