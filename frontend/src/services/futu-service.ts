import type {
  FutuAccount,
  FutuConnection,
  FutuOrdersResponse,
  FutuPortfolio,
  FutuPositionsResponse,
} from "@/types/futu";

const backendUrl = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${backendUrl}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Futu read API failed with HTTP ${response.status}.`);
  }

  return (await response.json()) as T;
}

export interface FutuService {
  getStatus(): Promise<FutuConnection>;
  getAccount(): Promise<FutuAccount>;
  getPositions(): Promise<FutuPositionsResponse>;
  getOrders(): Promise<FutuOrdersResponse>;
  getPortfolio(): Promise<FutuPortfolio>;
}

export const futuService: FutuService = {
  getStatus: () => getJson<FutuConnection>("/api/futu/status"),
  getAccount: () => getJson<FutuAccount>("/api/futu/account"),
  getPositions: () => getJson<FutuPositionsResponse>("/api/futu/positions"),
  getOrders: () => getJson<FutuOrdersResponse>("/api/futu/orders"),
  getPortfolio: () => getJson<FutuPortfolio>("/api/futu/portfolio"),
};

