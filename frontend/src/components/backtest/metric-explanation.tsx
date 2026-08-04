import { ChartNoAxesCombined, Clock3, ShieldCheck, Sparkles } from "lucide-react";

const EXPLANATIONS = [
  { title: "年化收益（CAGR）", text: "把回测期间的收益换算成年化收益率，便于不同周期比较。", icon: Clock3, tone: "green" },
  { title: "Sharpe", text: "衡量单位风险所获得的超额收益，通常越高越好。", icon: ShieldCheck, tone: "orange" },
  { title: "最大回撤", text: "从最高净值回落到最低净值的最大幅度，衡量策略的风险。", icon: ChartNoAxesCombined, tone: "red" },
  { title: "IC（信息系数）", text: "模型预测值与未来收益的相关性，越接近 1 越好。", icon: Sparkles, tone: "purple" },
] as const;

export function MetricExplanation() {
  return (
    <section className="qb-backtest-panel qb-explanation-panel">
      <h2>这些指标是什么意思？</h2>
      <div>
        {EXPLANATIONS.map(({ title, text, icon: Icon, tone }) => (
          <article key={title}>
            <span className={`is-${tone}`}><Icon aria-hidden="true" /></span>
            <span><strong>{title}</strong><small>{text}</small></span>
          </article>
        ))}
      </div>
    </section>
  );
}
