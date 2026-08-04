"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { NavPoint } from "@/types/dashboard";

type Period = "3m" | "6m" | "1y" | "all";

const PERIODS: readonly { label: string; value: Period; months?: number }[] = [
  { label: "近3月", value: "3m", months: 3 },
  { label: "近6月", value: "6m", months: 6 },
  { label: "近1年", value: "1y", months: 12 },
  { label: "全部", value: "all" },
];

function shortDate(date: string) {
  return date.slice(0, 7);
}

export function EquityCurveChart({ points }: { points: readonly NavPoint[] }) {
  const [period, setPeriod] = useState<Period>("all");
  const visiblePoints = useMemo(() => {
    const selected = PERIODS.find((item) => item.value === period);
    if (!selected?.months || points.length === 0) return points;
    const lastDate = new Date(`${points.at(-1)?.date}T00:00:00`);
    lastDate.setMonth(lastDate.getMonth() - selected.months);
    return points.filter((point) => new Date(`${point.date}T00:00:00`) >= lastDate);
  }, [period, points]);
  const chartData = visiblePoints.map((point) => ({
    date: point.date,
    strategy: (point.strategyNav - 1) * 100,
    benchmark: (point.benchmarkNav - 1) * 100,
  }));

  return (
    <section className="qb-backtest-panel qb-equity-panel">
      <header>
        <h2>策略净值 vs 沪深300</h2>
        <div className="qb-chart-periods" role="group" aria-label="图表时间范围">
          {PERIODS.map((item) => (
            <button
              key={item.value}
              type="button"
              aria-pressed={period === item.value}
              className={period === item.value ? "is-active" : ""}
              onClick={() => setPeriod(item.value)}
            >{item.label}</button>
          ))}
        </div>
      </header>
      {chartData.length ? (
        <div className="qb-equity-chart" data-period={period}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 12, left: -8, bottom: 0 }}>
              <CartesianGrid stroke="#e9ebf3" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fill: "#69738e", fontSize: 11 }} minTickGap={45} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={(value) => `${value.toFixed(0)}%`} tick={{ fill: "#69738e", fontSize: 11 }} axisLine={false} tickLine={false} width={48} />
              <Tooltip formatter={(value, name) => [`${Number(value).toFixed(2)}%`, name === "strategy" ? "策略净值" : "沪深300"]} labelFormatter={(label) => `日期：${label}`} />
              <Legend formatter={(value) => value === "strategy" ? "策略净值" : "沪深300"} iconType="plainline" align="left" verticalAlign="top" />
              <Line type="monotone" dataKey="strategy" stroke="#5141f5" strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
              <Line type="monotone" dataKey="benchmark" stroke="#9aa5ba" strokeWidth={1.8} dot={false} activeDot={{ r: 3 }} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : <p className="qb-section-unavailable">净值数据暂不可用</p>}
    </section>
  );
}
