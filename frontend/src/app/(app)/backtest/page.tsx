import type { Metadata } from "next";
import { BacktestContextPage } from "@/components/backtest/backtest-context-page";
import { dataService } from "@/services/data-service";

export const metadata: Metadata = { title: "回测研究" };

function valueOr<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === "fulfilled" ? result.value : fallback;
}

export default async function BacktestPage({ searchParams }: { searchParams: Promise<{ id?: string | string[] }> }) {
  const query = await searchParams;
  const strategyId = Array.isArray(query.id) ? query.id[0] : query.id;
  const [strategy, metrics, navCurve, monthlyReturns, holdings] = await Promise.allSettled([
    dataService.getStrategySummary(),
    dataService.getBacktestMetrics(),
    dataService.getNavCurve(),
    dataService.getMonthlyReturns(),
    dataService.getCurrentHoldings(),
  ]);

  return (
    <BacktestContextPage
      strategyId={strategyId}
      data={{ strategy: valueOr(strategy, null), metrics: valueOr(metrics, null), navCurve: valueOr(navCurve, []), monthlyReturns: valueOr(monthlyReturns, []), holdings: valueOr(holdings, null) }}
    />
  );
}
