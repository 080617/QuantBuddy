import {
  ChartNoAxesCombined,
  ChartSpline,
  CirclePercent,
  Grid3X3,
  PieChart,
  ShieldCheck,
  Sparkles,
  SquareMenu,
} from "lucide-react";
import { BacktestDisclosure } from "@/components/backtest/backtest-disclosure";
import { BacktestHeader } from "@/components/backtest/backtest-header";
import { BacktestHoldingsTable } from "@/components/backtest/backtest-holdings-table";
import { EquityCurveChart } from "@/components/backtest/equity-curve-chart";
import { MetricCard } from "@/components/backtest/metric-card";
import { MetricExplanation } from "@/components/backtest/metric-explanation";
import { MonthlyReturnHeatmap } from "@/components/backtest/monthly-return-heatmap";
import type { BacktestMetrics, HistoricalHoldings, MonthlyReturn, NavPoint, StrategyConfig } from "@/types/dashboard";

const percent = new Intl.NumberFormat("zh-CN", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });

function ConfigItem({ label, value, icon: Icon }: { label: string; value: string; icon: typeof PieChart }) {
  return <div className="qb-backtest-config-item"><span><Icon aria-hidden="true" /></span><span><small>{label}</small><strong>{value}</strong></span></div>;
}

export function BacktestResearch({
  strategy,
  metrics,
  navCurve,
  monthlyReturns,
  holdings,
}: {
  strategy: StrategyConfig | null;
  metrics: BacktestMetrics | null;
  navCurve: readonly NavPoint[];
  monthlyReturns: readonly MonthlyReturn[];
  holdings: HistoricalHoldings | null;
}) {
  return (
    <div className="qb-backtest-page">
      <BacktestHeader />

      {strategy ? (
        <section className="qb-backtest-config-card">
          <div className="qb-backtest-strategy-name">
            <span><ChartNoAxesCombined aria-hidden="true" /></span>
            <span><span><h2>{strategy.strategyName}</h2><i>历史模拟回测</i></span><small>回测区间：{strategy.backtestPeriod[0]} ~ {strategy.backtestPeriod[1]}</small></span>
          </div>
          <div className="qb-backtest-config-grid">
            <ConfigItem label="预测模型" value={strategy.model} icon={CirclePercent} />
            <ConfigItem label="特征集" value={strategy.featureSet} icon={Grid3X3} />
            <ConfigItem label="股票池" value="当前沪深300固定股票池" icon={PieChart} />
            <ConfigItem label="组合规则" value={`${strategy.portfolioRule.name} · Top-${strategy.portfolioRule.topK}`} icon={SquareMenu} />
          </div>
        </section>
      ) : <p className="qb-section-unavailable qb-top-unavailable">策略配置暂不可用</p>}

      {metrics ? (
        <section className="qb-metrics-row" aria-label="回测指标">
          <MetricCard label="累计收益" value={percent.format(metrics.totalReturn)} tone="purple" icon={ChartSpline} />
          <MetricCard label="年化收益" value={percent.format(metrics.cagr)} tone="green" icon={CirclePercent} />
          <MetricCard label="Sharpe" value={metrics.sharpe.toFixed(2)} tone="orange" icon={ShieldCheck} />
          <MetricCard label="最大回撤" value={percent.format(metrics.maxDrawdown)} tone="red" icon={ChartNoAxesCombined} />
          <article className="qb-signal-metrics">
            <span><Sparkles aria-hidden="true" /><span><small>IC</small><strong>{metrics.ic.toFixed(4)}</strong></span></span>
            <span><Sparkles aria-hidden="true" /><span><small>Rank IC</small><strong>{metrics.rankIc.toFixed(4)}</strong></span></span>
          </article>
        </section>
      ) : <p className="qb-section-unavailable">回测指标暂不可用</p>}

      <div className="qb-backtest-middle-grid">
        <EquityCurveChart points={navCurve} />
        <MetricExplanation />
      </div>
      <div className="qb-backtest-bottom-grid">
        <MonthlyReturnHeatmap returns={monthlyReturns} />
        <BacktestHoldingsTable data={holdings} />
      </div>
      <BacktestDisclosure />
    </div>
  );
}
