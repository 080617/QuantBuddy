export interface EquityPoint {
  date: string;
  strategy: number;
  benchmark: number;
}

export interface BacktestTrade {
  date: string;
  symbol: string;
  name: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  amount: number;
}
