import { dataService } from "@/services/data-service";
import type { LatestSignals, OperationPreview } from "@/types/dashboard";
import type { WorkspaceBacktestContext } from "@/types/workspace";

export type BacktestInsightSection<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string };

export interface BacktestInsightsState {
  signals: BacktestInsightSection<LatestSignals>;
  operationPreview: BacktestInsightSection<OperationPreview>;
}

export interface BacktestInsightsDataSource {
  getLatestSignals(): Promise<LatestSignals>;
  getOperationPreview(): Promise<OperationPreview>;
}

export const INITIAL_BACKTEST_INSIGHTS_STATE: BacktestInsightsState = {
  signals: { status: "loading" },
  operationPreview: { status: "loading" },
};

export function hasHistoricalSignals(signals: LatestSignals): boolean {
  return signals.signals.length > 0;
}

export function hasOperationPreviewData(preview: OperationPreview): boolean {
  return Boolean(
    preview.type ||
      preview.label ||
      preview.buyCandidate ||
      preview.sellCandidate ||
      preview.note,
  );
}

function settleSection<T>(result: PromiseSettledResult<T>): BacktestInsightSection<T> {
  if (result.status === "fulfilled") return { status: "ready", data: result.value };
  return {
    status: "error",
    message: result.reason instanceof Error ? result.reason.message : "数据加载失败",
  };
}

export async function loadBacktestInsightsForContext(
  context: WorkspaceBacktestContext,
  source: BacktestInsightsDataSource = dataService,
): Promise<BacktestInsightsState | null> {
  if (context.status !== "ready") return null;

  const [signals, operationPreview] = await Promise.allSettled([
    source.getLatestSignals(),
    source.getOperationPreview(),
  ]);

  return {
    signals: settleSection(signals),
    operationPreview: settleSection(operationPreview),
  };
}
