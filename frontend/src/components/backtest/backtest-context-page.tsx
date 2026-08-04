"use client";

import { ArrowLeft, PencilLine } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BacktestResearch } from "@/components/backtest/backtest-research";
import { workspaceService } from "@/services/workspace-service";
import type { BacktestMetrics, HistoricalHoldings, MonthlyReturn, NavPoint, StrategyConfig } from "@/types/dashboard";
import type { WorkspaceBacktestContext } from "@/types/workspace";

interface BacktestData {
  strategy: StrategyConfig | null;
  metrics: BacktestMetrics | null;
  navCurve: readonly NavPoint[];
  monthlyReturns: readonly MonthlyReturn[];
  holdings: HistoricalHoldings | null;
}

export function BacktestContextPage({ strategyId, data }: { strategyId?: string; data: BacktestData }) {
  const [context, setContext] = useState<WorkspaceBacktestContext | null>(null);

  useEffect(() => {
    let active = true;
    void workspaceService.resolveBacktestContext(strategyId).then((value) => { if (active) setContext(value); });
    return () => { active = false; };
  }, [strategyId]);

  if (!context) return <div className="qb-backtest-context-state"><p>正在解析回测上下文…</p></div>;
  if (context.status === "ready") return <BacktestResearch {...data} />;

  const missing = context.status === "not_found";
  const editHref = missing ? "/strategy/create/complete" : `/strategy/create/complete?id=${context.strategy.id}`;
  return <section className="qb-backtest-context-state" role="status">
    <h1>{missing ? "未找到对应策略" : "该策略尚未在当前工作区完成回测"}</h1>
    <p>{missing ? "请返回我的策略确认该资产是否仍然存在。" : "草稿、Community Fork、待重新回测或没有有效回测引用的策略不会显示基准收益。"}</p>
    <div>
      <Link href="/strategy"><ArrowLeft />返回我的策略</Link>
      <Link className="is-primary" href={editHref}><PencilLine />继续编辑</Link>
    </div>
  </section>;
}
