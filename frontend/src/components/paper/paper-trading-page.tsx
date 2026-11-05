"use client";

import {
  BadgeCheck,
  Banknote,
  BriefcaseBusiness,
  ChartPie,
  CircleDollarSign,
  DatabaseZap,
  RefreshCw,
  ShieldCheck,
  WalletCards,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { futuService, type FutuService } from "@/services/futu-service";
import type { FutuPortfolio } from "@/types/futu";
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  isPortfolioConnected,
  orderSideLabel,
  orderStatusLabel,
  safeMaskedIdentifier,
} from "./paper-trading-model";

interface PaperTradingPageProps {
  service?: FutuService;
}

type LoadState =
  | { status: "loading"; portfolio: FutuPortfolio | null }
  | { status: "ready"; portfolio: FutuPortfolio }
  | { status: "error"; portfolio: null };

export async function loadPaperPortfolio(service: FutuService): Promise<FutuPortfolio> {
  return service.getPortfolio();
}

export function PaperTradingPage({ service = futuService }: PaperTradingPageProps) {
  const [state, setState] = useState<LoadState>({ status: "loading", portfolio: null });

  const refresh = useCallback(async () => {
    setState((current) => ({ status: "loading", portfolio: current.portfolio }));
    try {
      const portfolio = await loadPaperPortfolio(service);
      setState({ status: "ready", portfolio });
    } catch {
      setState({ status: "error", portfolio: null });
    }
  }, [service]);

  useEffect(() => {
    let active = true;
    void loadPaperPortfolio(service)
      .then((portfolio) => {
        if (active) setState({ status: "ready", portfolio });
      })
      .catch(() => {
        if (active) setState({ status: "error", portfolio: null });
      });
    return () => {
      active = false;
    };
  }, [service]);

  const portfolio = state.portfolio;
  const connected = portfolio ? isPortfolioConnected(portfolio) : false;

  return (
    <section className="qb-paper-page">
      <header className="qb-paper-header">
        <div>
          <h1>模拟盘</h1>
          <p>通过富途模拟账户查看策略持仓与交易状态</p>
        </div>
        <div className="qb-paper-header-actions">
          <div className="qb-paper-badges" aria-label="账户连接状态">
            <span className={connected ? "is-connected" : "is-disconnected"}>
              {connected ? <Wifi aria-hidden="true" /> : <WifiOff aria-hidden="true" />}
              {connected ? "连接正常" : "未连接"}
            </span>
            <span>A股</span>
            <span>模拟账户</span>
          </div>
          <button type="button" onClick={() => void refresh()} disabled={state.status === "loading"}>
            <RefreshCw className={state.status === "loading" ? "is-spinning" : ""} aria-hidden="true" />
            {state.status === "loading" ? "正在刷新" : "刷新数据"}
          </button>
        </div>
      </header>

      {state.status === "loading" && !portfolio ? <PaperLoadingState /> : null}
      {state.status === "error" || (portfolio && !connected) ? <PaperConnectionError onRetry={refresh} /> : null}
      {portfolio && connected ? <PaperPortfolioContent portfolio={portfolio} /> : null}
    </section>
  );
}

function PaperLoadingState() {
  return (
    <div className="qb-paper-loading" role="status" aria-live="polite">
      <RefreshCw className="is-spinning" aria-hidden="true" />
      <strong>正在读取富途模拟账户</strong>
      <span>账户、持仓和订单数据正在加载中</span>
    </div>
  );
}

function PaperConnectionError({ onRetry }: { onRetry: () => Promise<void> }) {
  return (
    <div className="qb-paper-connection-error" role="alert">
      <span><WifiOff aria-hidden="true" /></span>
      <h2>富途连接不可用</h2>
      <p>请确认：</p>
      <ol>
        <li>FutuOpenD 已启动并登录</li>
        <li>QuantBuddy Backend 已启动</li>
      </ol>
      <button type="button" onClick={() => void onRetry()}>
        <RefreshCw aria-hidden="true" />重新连接 / 重试
      </button>
    </div>
  );
}

function PaperPortfolioContent({ portfolio }: { portfolio: FutuPortfolio }) {
  const { account, connection, positions, orders } = portfolio;
  const metrics = [
    { label: "总资产", value: formatCurrency(account.totalAssets), icon: WalletCards, tone: "purple" },
    { label: "现金", value: formatCurrency(account.cash), icon: Banknote, tone: "green" },
    { label: "持仓市值", value: formatCurrency(account.marketValue), icon: ChartPie, tone: "orange" },
    { label: "当前持仓", value: String(positions.length), icon: BriefcaseBusiness, tone: "blue" },
  ] as const;

  return (
    <>
      <div className="qb-paper-metrics">
        {metrics.map(({ label, value, icon: Icon, tone }) => (
          <article key={label} className="qb-paper-card qb-paper-metric">
            <span className={`is-${tone}`}><Icon aria-hidden="true" /></span>
            <div><small>{label}</small><strong>{value}</strong></div>
          </article>
        ))}
      </div>

      <div className="qb-paper-summary-grid">
        <article className="qb-paper-card qb-paper-overview">
          <header><div><h2>账户概览</h2><p>富途 A 股模拟账户的只读状态</p></div><ShieldCheck aria-hidden="true" /></header>
          <dl>
            <div><dt>账户类型</dt><dd>{account.accountType ?? "--"}</dd></div>
            <div><dt>交易市场</dt><dd>A股</dd></div>
            <div><dt>交易环境</dt><dd>模拟</dd></div>
            <div><dt>账户状态</dt><dd><span className="qb-paper-status is-positive">{account.status}</span></dd></div>
            <div><dt>FutuOpenD</dt><dd><span className="qb-paper-status is-positive">已连接</span></dd></div>
            <div><dt>账户 ID</dt><dd>{safeMaskedIdentifier(account.accountIdMasked)}</dd></div>
          </dl>
        </article>

        <article className="qb-paper-card qb-paper-execution">
          <header><div><h2>策略执行</h2><p>当前 QuantBuddy 策略连接状态</p></div><DatabaseZap aria-hidden="true" /></header>
          <div className="qb-paper-strategy-name"><CircleDollarSign aria-hidden="true" /><strong>沪深300 · LightGBM · Alpha158 · Top-5</strong></div>
          <div className="qb-paper-execution-status">
            <span><BadgeCheck aria-hidden="true" />已连接模型</span>
            <span>自动交易<strong>未启用</strong></span>
          </div>
          <button type="button" disabled>查看最新计划</button>
          <p>交易执行功能将在下一阶段开放</p>
        </article>
      </div>

      <PaperPositions positions={positions} />
      <PaperOrders orders={orders} />
      <p className="qb-paper-readonly-note">本页面仅展示历史与当前模拟账户数据，不提供下单、改单或撤单功能。环境：{connection.market} · {connection.environment}</p>
    </>
  );
}

function PaperPositions({ positions }: { positions: FutuPortfolio["positions"] }) {
  return (
    <article className="qb-paper-card qb-paper-table-panel">
      <header><div><h2>当前持仓</h2><p>富途 A 股模拟账户中的持仓快照</p></div><span>{positions.length} 项</span></header>
      {positions.length === 0 ? (
        <div className="qb-paper-empty"><BriefcaseBusiness aria-hidden="true" /><strong>暂无持仓</strong><p>你的富途 A 股模拟账户当前还没有持仓。<br />完成模拟交易后，持仓会自动显示在这里。</p></div>
      ) : (
        <div className="qb-paper-table-scroll">
          <table>
            <thead><tr><th>股票</th><th>代码</th><th>持仓数量</th><th>可卖数量</th><th>现价</th><th>成本价</th><th>市值</th><th>盈亏</th><th>收益率</th></tr></thead>
            <tbody>{positions.map((position) => <tr key={position.code}>
              <td><strong>{position.name || "--"}</strong></td><td>{position.code}</td><td>{formatNumber(position.quantity, 0)}</td><td>{formatNumber(position.canSellQuantity, 0)}</td><td>{formatCurrency(position.price)}</td><td>{formatCurrency(position.costPrice)}</td><td>{formatCurrency(position.marketValue)}</td><td className={(position.profitLoss ?? 0) >= 0 ? "is-profit" : "is-loss"}>{formatCurrency(position.profitLoss)}</td><td className={(position.profitLossPercent ?? 0) >= 0 ? "is-profit" : "is-loss"}>{formatPercent(position.profitLossPercent)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
    </article>
  );
}

function PaperOrders({ orders }: { orders: FutuPortfolio["orders"] }) {
  return (
    <article className="qb-paper-card qb-paper-table-panel">
      <header><div><h2>最近订单</h2><p>近期模拟订单的只读记录</p></div><span>{orders.length} 项</span></header>
      {orders.length === 0 ? (
        <div className="qb-paper-empty is-compact"><CircleDollarSign aria-hidden="true" /><strong>暂无最近订单</strong><p>账户产生模拟订单后，记录会自动显示在这里。</p></div>
      ) : (
        <div className="qb-paper-table-scroll">
          <table>
            <thead><tr><th>股票</th><th>方向</th><th>状态</th><th>数量</th><th>委托价</th><th>成交数量</th><th>成交均价</th><th>时间</th><th>订单 ID</th></tr></thead>
            <tbody>{orders.map((order, index) => <tr key={`${order.orderIdMasked}-${index}`}>
              <td><strong>{order.name || order.code}</strong><small>{order.code}</small></td><td><span className={`qb-paper-side is-${orderSideLabel(order.side) === "买入" ? "buy" : "sell"}`}>{orderSideLabel(order.side)}</span></td><td><span className={`qb-paper-order-status is-${order.status.toLowerCase()}`}>{orderStatusLabel(order.status)}</span></td><td>{formatNumber(order.quantity, 0)}</td><td>{formatCurrency(order.price)}</td><td>{formatNumber(order.dealtQuantity, 0)}</td><td>{formatCurrency(order.dealtAveragePrice)}</td><td>{order.createdAt ?? "--"}</td><td>{safeMaskedIdentifier(order.orderIdMasked)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      )}
    </article>
  );
}
