import { afterEach, describe, expect, it, vi } from "vitest";
import { futuService } from "@/services/futu-service";
import type { FutuPortfolio } from "@/types/futu";

afterEach(() => vi.unstubAllGlobals());

describe("futuService read-only boundary", () => {
  it("loads portfolio with one GET request", async () => {
    const portfolio = {
      connection: { connected: true, openD: true, market: "CN", environment: "SIMULATE", accountStatus: "ACTIVE", reason: null },
      account: { accountIdMasked: "****2058", market: "CN", environment: "SIMULATE", accountType: "CASH", status: "ACTIVE", totalAssets: 1, cash: 1, marketValue: 0 },
      positions: [],
      orders: [],
    } satisfies FutuPortfolio;
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => portfolio });
    vi.stubGlobal("fetch", fetchMock);

    await expect(futuService.getPortfolio()).resolves.toEqual(portfolio);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/futu\/portfolio$/);
    expect(init).toMatchObject({ method: "GET" });
  });

  it("exposes no order write request", () => {
    expect(Object.keys(futuService).sort()).toEqual([
      "getAccount",
      "getOrders",
      "getPortfolio",
      "getPositions",
      "getStatus",
    ]);
  });
});

