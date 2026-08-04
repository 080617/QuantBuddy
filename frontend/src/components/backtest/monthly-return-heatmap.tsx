import type { MonthlyReturn } from "@/types/dashboard";

const MONTHS = Array.from({ length: 12 }, (_, index) => index + 1);

function cellColor(value: number) {
  const strength = Math.min(Math.abs(value) / 0.2, 1);
  return value >= 0
    ? `rgba(46, 178, 92, ${0.1 + strength * 0.35})`
    : `rgba(232, 70, 91, ${0.1 + strength * 0.33})`;
}

export function MonthlyReturnHeatmap({ returns }: { returns: readonly MonthlyReturn[] }) {
  const byMonth = new Map(returns.map((item) => [item.month, item.strategyReturn]));
  const years = [...new Set(returns.map((item) => item.month.slice(0, 4)))].sort();
  return (
    <section className="qb-backtest-panel qb-heatmap-panel">
      <h2>月度收益</h2>
      {years.length ? (
        <div className="qb-heatmap-scroll">
          <div className="qb-heatmap-grid">
            <strong>年份</strong>{MONTHS.map((month) => <strong key={month}>{month}月</strong>)}
            {years.flatMap((year) => [
              <strong key={`${year}-label`}>{year}</strong>,
              ...MONTHS.map((month) => {
                const key = `${year}-${String(month).padStart(2, "0")}`;
                const value = byMonth.get(key);
                return value === undefined ? (
                  <span key={key} className="is-empty">-</span>
                ) : (
                  <span key={key} style={{ background: cellColor(value) }} title={`${key}：${(value * 100).toFixed(2)}%`}>
                    {(value * 100).toFixed(1)}%
                  </span>
                );
              }),
            ])}
          </div>
          <div className="qb-heatmap-legend"><span>-20%</span><i /><span>0%</span><i /><span>20%</span></div>
        </div>
      ) : <p className="qb-section-unavailable">月度收益数据暂不可用</p>}
    </section>
  );
}
