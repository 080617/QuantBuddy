import currentHoldingsJson from "../../public/data/dashboard_v1/current_holdings.json";
import dashboardJson from "../../public/data/dashboard_v1/dashboard.json";
import latestSignalsJson from "../../public/data/dashboard_v1/latest_signals.json";
import monthlyReturnsJson from "../../public/data/dashboard_v1/monthly_returns.json";
import navCurveJson from "../../public/data/dashboard_v1/nav_curve.json";
import operationPreviewJson from "../../public/data/dashboard_v1/operation_preview.json";
import {
  adaptBacktestMetrics,
  adaptDashboardData,
  adaptHistoricalHoldings,
  adaptLatestSignals,
  adaptMonthlyReturns,
  adaptNavCurve,
  adaptOperationPreview,
  adaptStrategyCard,
  adaptStrategyConfig,
  type DashboardJsonSource,
  type HoldingsJsonSource,
  type MonthlyReturnJsonSource,
  type NavPointJsonSource,
  type OperationJsonSource,
  type SignalsJsonSource,
} from "@/services/dashboard-adapter";
import type {
  BacktestMetrics,
  DashboardData,
  HistoricalHoldings,
  LatestSignals,
  MonthlyReturn,
  NavPoint,
  OperationPreview,
  StrategyConfig,
} from "@/types/dashboard";
import type { Strategy } from "@/types/strategy";

const dashboardSource: DashboardJsonSource = dashboardJson;
const navCurveSource: readonly NavPointJsonSource[] = navCurveJson;
const monthlyReturnsSource: readonly MonthlyReturnJsonSource[] = monthlyReturnsJson;
const holdingsSource: HoldingsJsonSource = currentHoldingsJson;
const signalsSource: SignalsJsonSource = latestSignalsJson;
const operationSource: OperationJsonSource = operationPreviewJson;

export interface DashboardService {
  getDashboardData(): Promise<DashboardData>;
  getStrategySummary(): Promise<StrategyConfig>;
  getBacktestMetrics(): Promise<BacktestMetrics>;
  getNavCurve(): Promise<readonly NavPoint[]>;
  getMonthlyReturns(): Promise<readonly MonthlyReturn[]>;
  getCurrentHoldings(): Promise<HistoricalHoldings>;
  getLatestSignals(): Promise<LatestSignals>;
  getOperationPreview(): Promise<OperationPreview>;
  getStrategies(): Promise<readonly Strategy[]>;
}

export const dashboardService: DashboardService = {
  getDashboardData: () =>
    Promise.resolve(
      adaptDashboardData(
        dashboardSource,
        navCurveSource,
        monthlyReturnsSource,
        holdingsSource,
        signalsSource,
        operationSource,
      ),
    ),
  getStrategySummary: () => Promise.resolve(adaptStrategyConfig(dashboardSource)),
  getBacktestMetrics: () => Promise.resolve(adaptBacktestMetrics(dashboardSource)),
  getNavCurve: () => Promise.resolve(adaptNavCurve(navCurveSource)),
  getMonthlyReturns: () => Promise.resolve(adaptMonthlyReturns(monthlyReturnsSource)),
  getCurrentHoldings: () =>
    Promise.resolve(adaptHistoricalHoldings(holdingsSource)),
  getLatestSignals: () => Promise.resolve(adaptLatestSignals(signalsSource)),
  getOperationPreview: () =>
    Promise.resolve(adaptOperationPreview(operationSource)),
  getStrategies: () => Promise.resolve([adaptStrategyCard(dashboardSource)]),
};
