import { TriangleAlert } from "lucide-react";

export function BacktestDisclosure() {
  return (
    <aside className="qb-backtest-disclosure">
      <TriangleAlert aria-hidden="true" />
      <span>历史模拟回测，不代表真实交易结果或未来收益。</span>
    </aside>
  );
}
