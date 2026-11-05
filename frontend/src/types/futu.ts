export interface FutuConnection {
  connected: boolean;
  openD: boolean;
  market: "CN";
  environment: "SIMULATE";
  accountStatus: string | null;
  reason: string | null;
}

export interface FutuAccount {
  accountIdMasked: string;
  market: "CN";
  environment: "SIMULATE";
  accountType: string | null;
  status: string;
  totalAssets: number | null;
  cash: number | null;
  marketValue: number | null;
}

export interface FutuPosition {
  code: string;
  name: string;
  quantity: number;
  canSellQuantity: number;
  price: number | null;
  costPrice: number | null;
  marketValue: number | null;
  profitLoss: number | null;
  profitLossPercent: number | null;
}

export interface FutuOrder {
  orderIdMasked: string;
  code: string;
  name: string | null;
  side: string;
  status: string;
  quantity: number;
  price: number;
  dealtQuantity: number;
  dealtAveragePrice: number | null;
  createdAt: string | null;
}

export interface FutuPortfolio {
  connection: FutuConnection;
  account: FutuAccount;
  positions: FutuPosition[];
  orders: FutuOrder[];
}

export interface FutuPositionsResponse {
  positions: FutuPosition[];
  count: number;
}

export interface FutuOrdersResponse {
  orders: FutuOrder[];
  count: number;
}

