import { ArrowRight, History, ListOrdered, ShieldAlert } from "lucide-react";
import {
  hasHistoricalSignals,
  hasOperationPreviewData,
  type BacktestInsightsState,
  type BacktestInsightSection,
} from "@/services/backtest-insights-service";
import type { LatestSignals, OperationCandidate, OperationPreview } from "@/types/dashboard";

const percent = new Intl.NumberFormat("zh-CN", {
  style: "percent",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function SectionState({ kind, state }: { kind: "signals" | "operation"; state: "loading" | "empty" | "error" }) {
  const copy = {
    signals: {
      loading: "正在加载历史模型信号…",
      empty: "暂无可展示的历史模型信号。",
      error: "历史模型信号加载失败，请稍后重试。",
    },
    operation: {
      loading: "正在加载历史操作预览…",
      empty: "暂无可展示的历史操作预览。",
      error: "历史操作预览加载失败，请稍后重试。",
    },
  }[kind][state];

  return <div className={`qb-insight-state is-${state}`} role={state === "error" ? "alert" : "status"}>{copy}</div>;
}

function LatestSignalsPanel({ state }: { state: BacktestInsightSection<LatestSignals> }) {
  return (
    <section className="qb-backtest-panel qb-research-panel" aria-labelledby="latest-signals-title">
      <header className="qb-research-panel-heading">
        <div><h2 id="latest-signals-title">最新模型信号</h2><p>模型在最后一个信号日输出的 Top-5 股票排名，仅用于历史研究展示。</p></div>
        <div className="qb-history-badges"><span className="qb-history-badge"><History aria-hidden="true" />历史模型输出</span></div>
      </header>
      {state.status === "loading" ? <SectionState kind="signals" state="loading" /> : null}
      {state.status === "error" ? <SectionState kind="signals" state="error" /> : null}
      {state.status === "ready" && !hasHistoricalSignals(state.data) ? <SectionState kind="signals" state="empty" /> : null}
      {state.status === "ready" && hasHistoricalSignals(state.data) ? <>
        <div className="qb-signal-meta"><span>信号日期<strong>{state.data.date}</strong></span><span>数据状态<strong>历史模型输出</strong></span></div>
        <div className="qb-signal-table-scroll"><table className="qb-signal-table">
          <thead><tr><th>排名</th><th>股票</th><th>模型分数</th><th>分数百分位</th><th>当前是否持有</th></tr></thead>
          <tbody>{state.data.signals.map((signal) => <tr key={`${signal.rank}-${signal.stock}`}>
            <td><span className="qb-rank-chip">{signal.rank}</span></td>
            <td className="qb-stock-cell"><strong>{signal.stockName}</strong><span>{signal.stock}</span></td>
            <td>{signal.score.toFixed(6)}</td>
            <td>{percent.format(signal.scorePercentile)}</td>
            <td><span className={`qb-holding-state${signal.currentlyHeld ? " is-held" : ""}`}>{signal.currentlyHeld ? "当前持有" : "当前未持有"}</span></td>
          </tr>)}</tbody>
        </table></div>
      </> : null}
    </section>
  );
}

function CandidateCard({ kind, candidate }: { kind: "sell" | "buy"; candidate: OperationCandidate | null }) {
  const buy = kind === "buy";
  return <article className={`qb-operation-candidate${buy ? " is-buy" : ""}`}>
    <div className="qb-operation-candidate-label"><strong>{buy ? "买入候选" : "卖出候选"}</strong><span>{buy ? "历史模型信号" : "历史回测持仓"}</span></div>
    {candidate ? <>
      <div className="qb-operation-stock">{candidate.stockName || "未命名股票"}<span>{candidate.stock || "--"}</span></div>
      <div className="qb-operation-details">
        <span>{buy ? "Top" : "模型排名"} {candidate.rank ?? "--"}</span>
        <span>模型分数 {candidate.score === null ? "--" : candidate.score.toFixed(6)}</span>
      </div>
    </> : <div className="qb-operation-candidate-empty">无{buy ? "买入" : "卖出"}候选</div>}
  </article>;
}

function OperationPreviewPanel({ state }: { state: BacktestInsightSection<OperationPreview> }) {
  return (
    <section className="qb-backtest-panel qb-research-panel" aria-labelledby="operation-preview-title">
      <header className="qb-research-panel-heading">
        <div><h2 id="operation-preview-title">历史操作预览</h2><p>根据最后一次历史回测持仓与模型信号生成的研究预览，不是真实交易指令。</p></div>
        <div className="qb-history-badges"><span className="qb-history-badge is-warning"><ListOrdered aria-hidden="true" />历史预览</span><span className="qb-history-badge is-warning"><ShieldAlert aria-hidden="true" />非真实订单</span></div>
      </header>
      {state.status === "loading" ? <SectionState kind="operation" state="loading" /> : null}
      {state.status === "error" ? <SectionState kind="operation" state="error" /> : null}
      {state.status === "ready" && !hasOperationPreviewData(state.data) ? <SectionState kind="operation" state="empty" /> : null}
      {state.status === "ready" && hasOperationPreviewData(state.data) ? <>
        <div className="qb-operation-meta"><span>操作类型<strong>{state.data.type || "--"}</strong></span><span>操作标签<strong>{state.data.label || "--"}</strong></span><span>预览状态<strong>{state.data.previewOnly ? "previewOnly = true · 非真实订单" : "previewOnly = false"}</strong></span></div>
        <div className="qb-operation-route"><CandidateCard kind="sell" candidate={state.data.sellCandidate} /><div className="qb-operation-arrow" aria-hidden="true"><ArrowRight /></div><CandidateCard kind="buy" candidate={state.data.buyCandidate} /></div>
        <p className="qb-operation-note"><strong>原始说明：</strong>{state.data.note || "未提供原始说明。"}</p>
      </> : null}
    </section>
  );
}

export function BacktestResearchInsights({ state }: { state: BacktestInsightsState }) {
  return <><LatestSignalsPanel state={state.signals} /><OperationPreviewPanel state={state.operationPreview} /></>;
}
