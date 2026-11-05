// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FutuService } from "@/services/futu-service";
import type { FutuPortfolio } from "@/types/futu";
import { PaperTradingPage } from "./paper-trading-page";

const EMPTY_PORTFOLIO: FutuPortfolio = {
  connection: {
    connected: true,
    openD: true,
    market: "CN",
    environment: "SIMULATE",
    accountStatus: "ACTIVE",
    reason: null,
  },
  account: {
    accountIdMasked: "******2058",
    market: "CN",
    environment: "SIMULATE",
    accountType: "CASH",
    status: "ACTIVE",
    totalAssets: 1_000_000,
    cash: 1_000_000,
    marketValue: 0,
  },
  positions: [],
  orders: [],
};

function makeService(result: FutuPortfolio | Error): FutuService & { getPortfolio: ReturnType<typeof vi.fn> } {
  const getPortfolio = result instanceof Error
    ? vi.fn().mockRejectedValue(result)
    : vi.fn().mockResolvedValue(result);
  return {
    getStatus: vi.fn(),
    getAccount: vi.fn(),
    getPositions: vi.fn(),
    getOrders: vi.fn(),
    getPortfolio,
  };
}

afterEach(() => cleanup());

describe("PaperTradingPage", () => {
  it("loads a real portfolio shape and renders the empty-position state", async () => {
    render(<PaperTradingPage service={makeService(EMPTY_PORTFOLIO)} />);
    expect(screen.getByText("正在读取富途模拟账户")).toBeTruthy();
    expect(await screen.findByText("暂无持仓")).toBeTruthy();
    expect(screen.getByText("连接正常")).toBeTruthy();
    expect(screen.getAllByText(/1,000,000\.00/).length).toBeGreaterThan(0);
  });

  it("renders positions and historical orders returned by the service", async () => {
    const portfolio: FutuPortfolio = {
      ...EMPTY_PORTFOLIO,
      account: { ...EMPTY_PORTFOLIO.account, cash: 998_937, marketValue: 1_063 },
      positions: [{
        code: "SZ.000001",
        name: "平安银行",
        quantity: 100,
        canSellQuantity: 100,
        price: 10.63,
        costPrice: 10.5,
        marketValue: 1063,
        profitLoss: 13,
        profitLossPercent: 1.24,
      }],
      orders: [{
        orderIdMasked: "******8842",
        code: "SZ.000001",
        name: "平安银行",
        side: "BUY",
        status: "CANCELLED_ALL",
        quantity: 100,
        price: 10.63,
        dealtQuantity: 0,
        dealtAveragePrice: null,
        createdAt: "2026-08-06 10:01:00",
      }],
    };
    render(<PaperTradingPage service={makeService(portfolio)} />);
    expect((await screen.findAllByText("平安银行")).length).toBeGreaterThan(0);
    expect(screen.getByText("买入")).toBeTruthy();
    expect(screen.getByText("已撤销")).toBeTruthy();
    expect(screen.getByText("******8842")).toBeTruthy();
  });

  it("shows a recoverable state when the backend is unavailable", async () => {
    render(<PaperTradingPage service={makeService(new Error("offline"))} />);
    expect(await screen.findByText("富途连接不可用")).toBeTruthy();
    expect(screen.getByRole("button", { name: "重新连接 / 重试" })).toBeTruthy();
  });

  it("shows disconnected when FutuOpenD reports no connection", async () => {
    const disconnected: FutuPortfolio = {
      ...EMPTY_PORTFOLIO,
      connection: { ...EMPTY_PORTFOLIO.connection, connected: false, openD: false },
    };
    render(<PaperTradingPage service={makeService(disconnected)} />);
    expect(await screen.findByText("富途连接不可用")).toBeTruthy();
    expect(screen.getByText("未连接")).toBeTruthy();
  });

  it("refresh button requests the portfolio again", async () => {
    const service = makeService(EMPTY_PORTFOLIO);
    render(<PaperTradingPage service={service} />);
    await screen.findByText("暂无持仓");
    expect(service.getPortfolio).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "刷新数据" }));
    await waitFor(() => expect(service.getPortfolio).toHaveBeenCalledTimes(2));
  });

  it("never renders an unmasked account identifier", async () => {
    const unsafe: FutuPortfolio = {
      ...EMPTY_PORTFOLIO,
      account: { ...EMPTY_PORTFOLIO.account, accountIdMasked: "1234562058" },
    };
    const { container } = render(<PaperTradingPage service={makeService(unsafe)} />);
    await screen.findByText("暂无持仓");
    expect(container.textContent).not.toContain("1234562058");
    expect(screen.getByText("****")).toBeTruthy();
  });
});

