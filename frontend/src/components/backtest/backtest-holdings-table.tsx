import { CalendarDays } from "lucide-react";
import type { HistoricalHoldings } from "@/types/dashboard";

const percent = new Intl.NumberFormat("zh-CN", { style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function BacktestHoldingsTable({ data }: { data: HistoricalHoldings | null }) {
  if (!data) {
    return <section className="qb-backtest-panel qb-holdings-panel"><h2>最后一次回测持仓</h2><p className="qb-section-unavailable">持仓数据暂不可用</p></section>;
  }
  const invested = data.holdings.reduce((sum, holding) => sum + holding.marketValue, 0);
  return (
    <section className="qb-backtest-panel qb-holdings-panel">
      <header><h2>最后一次回测持仓</h2><span><CalendarDays aria-hidden="true" />截至 {data.date}</span></header>
      <div className="qb-holdings-scroll">
        <table>
          <thead><tr><th>股票名称</th><th>权重</th><th>持有天数</th><th>市值占比</th></tr></thead>
          <tbody>
            {data.holdings.map((holding) => (
              <tr key={holding.stock}><td><strong>{holding.stockName}</strong><small>{holding.stock}</small></td><td>{percent.format(holding.weight)}</td><td>{holding.holdDays}</td><td>{percent.format(holding.marketValue / invested)}</td></tr>
            ))}
          </tbody>
          <tfoot><tr><td>合计</td><td>{percent.format(data.holdings.reduce((sum, item) => sum + item.weight, 0))}</td><td>--</td><td>{percent.format(1)}</td></tr></tfoot>
        </table>
      </div>
    </section>
  );
}
