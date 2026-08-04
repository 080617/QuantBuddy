"use client";

export default function BacktestError({ reset }: { reset(): void }) {
  return <div className="qb-backtest-error"><h1>回测数据加载失败</h1><p>请稍后重试。</p><button type="button" onClick={reset}>重新加载</button></div>;
}
