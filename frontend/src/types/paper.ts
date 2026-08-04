export interface PaperPosition {
  symbol: string;
  name: string;
  quantity: number;
  availableQuantity: number;
  averageCost: number;
  currentPrice: number;
  marketValue: number;
  pnl: number;
  pnlRate: number;
  weight: number;
}

export interface PaperOrder {
  orderId: string;
  createdAt: string;
  symbol: string;
  name: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  filledQuantity: number;
  averageFillPrice: number | null;
  status:
    | "SUBMITTED"
    | "PARTIALLY_FILLED"
    | "FILLED"
    | "CANCELLED"
    | "FAILED";
}

export interface TargetPosition {
  symbol: string;
  name: string;
  score: number;
  targetWeight: number;
  currentWeight: number;
  action: "BUY" | "HOLD" | "REDUCE" | "SELL";
}
