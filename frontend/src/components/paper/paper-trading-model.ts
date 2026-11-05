import type { FutuPortfolio } from "@/types/futu";

export const ORDER_STATUS_LABELS: Readonly<Record<string, string>> = {
  CANCELLED_ALL: "已撤销",
  FILLED: "已成交",
  SUBMITTED: "已提交",
  SUBMITTING: "提交中",
  PARTIALLY_FILLED: "部分成交",
  REJECTED: "已拒绝",
};

export function orderStatusLabel(status: string): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}

export function orderSideLabel(side: string): string {
  const normalized = side.toUpperCase();
  if (normalized.endsWith("BUY")) return "买入";
  if (normalized.endsWith("SELL")) return "卖出";
  return side;
}

export function safeMaskedIdentifier(value: string): string {
  return /^\*+[^*]{1,4}$/.test(value) ? value : "****";
}

export function formatCurrency(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNumber(value: number | null, digits = 2): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "--";
  return `${value >= 0 ? "+" : ""}${formatNumber(value)}%`;
}

export function isPortfolioConnected(portfolio: FutuPortfolio): boolean {
  return portfolio.connection.connected && portfolio.connection.openD;
}

