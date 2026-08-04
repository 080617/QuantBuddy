"use client";

import { Check, ChevronDown, CircleHelp, Code2, Info, Send, Sparkles, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { PublishBackButton } from "@/components/community/publish-back-button";
import { DEMO_BACKTEST_ID, STRATEGY_MODULE_STAGE_MAP, STRATEGY_MODULE_TYPE_LABELS } from "@/lib/community-constants";
import { communityService } from "@/services/community-service";
import { dataService } from "@/services/data-service";
import { createFactorPublishPrefill, createModulePublishPrefill, createStrategyPublishPrefill } from "@/services/workspace-integration";
import { workspaceService } from "@/services/workspace-service";
import type { CommunityContentType, CommunityPost, StrategyModuleType, WorkspaceStrategyPublishPrefill } from "@/types/community";
import styles from "./community-publish.module.css";

export type CommunityPublishKind = "factor" | "module" | "strategy" | "question";
type PublishStrategyOption = WorkspaceStrategyPublishPrefill;

const PAGE_COPY: Record<CommunityPublishKind, { title: string; subtitle: string; breadcrumb: string }> = {
  factor: { title: "发布因子", subtitle: "把一个量化想法整理成可计算、可验证的因子", breadcrumb: "发布因子" },
  module: { title: "发布策略模块", subtitle: "把一个可复用的选股、组合或风控规则整理成策略模块", breadcrumb: "发布策略模块" },
  strategy: { title: "发布完整策略", subtitle: "选择并分享你在“我的策略”中的完整策略", breadcrumb: "发布完整策略" },
  question: { title: "发布提问", subtitle: "在社区里提问、交流想法，和大家一起讨论量化问题", breadcrumb: "发布提问" },
};

const CONTENT_TYPE: Record<CommunityPublishKind, CommunityContentType> = {
  factor: "factor", module: "strategy_module", strategy: "complete_strategy", question: "question",
};
const PUBLISH_ROUTE: Record<CommunityPublishKind, string> = {
  factor: "/community/publish/factor", module: "/community/publish/module", strategy: "/community/publish/strategy", question: "/community/publish/question",
};
const FACTOR_TYPES = [
  ["momentum", "动量因子"], ["volatility", "波动率因子"], ["volume", "成交量因子"], ["price", "价格因子"], ["technical", "技术因子"], ["composite", "复合因子"], ["other", "其他"],
] as const;
const STRATEGY_TAGS = ["量化选股", "机器学习", "沪深300", "中高换手"];
const QUESTION_TAGS = ["新手提问", "回测问题", "因子讨论", "模型讨论", "策略交流", "产品建议", "随便聊聊"];
const STAGE_LABELS: Record<string, string> = { stock_selection_stage: "选股环节", portfolio_construction_stage: "组合构建环节", rebalance_stage: "调仓环节", risk_control_stage: "风险控制环节", trade_execution_stage: "交易执行环节" };

type Values = {
  factorName: string; factorType: string; expression: string; factorDescription: string;
  moduleName: string; moduleType: StrategyModuleType; ruleSummary: string; ruleExpression: string; moduleDescription: string;
  strategyTitle: string; oneLineIntroduction: string; detailedDescription: string;
  questionTitle: string; questionContent: string;
};
const INITIAL: Values = { factorName: "", factorType: "", expression: "", factorDescription: "", moduleName: "", moduleType: "risk_control", ruleSummary: "", ruleExpression: "", moduleDescription: "", strategyTitle: "", oneLineIntroduction: "", detailedDescription: "", questionTitle: "", questionContent: "" };

function Field({ label, required, error, hint, children }: { label: string; required?: boolean; error?: string; hint?: ReactNode; children: ReactNode }) {
  return <label className={styles.field}><span>{label}{required ? <b> *</b> : null}</span>{children}{hint ? <small className={styles.hint}>{hint}</small> : null}{error ? <small className={styles.error}>{error}</small> : null}</label>;
}

function FormulaEditor({ value, onChange, placeholder, maxLength, label }: { value: string; onChange: (value: string) => void; placeholder: string; maxLength: number; label: string }) {
  return <div className={styles.codeEditor}><span aria-hidden="true">1</span><textarea aria-label={label} value={value} maxLength={maxLength} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} /><Code2 aria-hidden="true" /></div>;
}

function TagSelector({ options, selected, onChange }: { options: string[]; selected: string[]; onChange: (tags: string[]) => void }) {
  function toggle(tag: string) { onChange(selected.includes(tag) ? selected.filter((item) => item !== tag) : [...selected, tag]); }
  return <div className={styles.tagSelector}>{options.map((tag) => <button key={tag} type="button" aria-pressed={selected.includes(tag)} onClick={() => toggle(tag)}>{selected.includes(tag) ? <Check /> : null}{tag}</button>)}</div>;
}

function HelpCard({ title, children }: { title: string; children: ReactNode }) { return <section className={styles.helpCard}><h2>{title}</h2>{children}</section>; }

function StatusCard({ saved, ready }: { saved: boolean; ready: boolean }) {
  const label = saved ? "草稿已保存" : ready ? "准备发布" : "草稿未保存";
  return <section className={`${styles.helpCard} ${styles.statusCard}`}><h2>当前状态</h2><strong>{label}</strong><p>{saved ? "当前内容已安全保存为私人草稿，不会出现在社区信息流。" : ready ? "必填信息已经完整，可以预览并发布到社区。" : "填写内容后可保存私人草稿，或补全必填项后发布。"}</p></section>;
}

function PreviewModal({ kind, values, tags, strategy, onClose, onConfirm, busy }: { kind: Exclude<CommunityPublishKind,"question">; values: Values; tags: string[]; strategy?: PublishStrategyOption; onClose: () => void; onConfirm: () => void; busy: boolean }) {
  const title = kind === "factor" ? values.factorName : kind === "module" ? values.moduleName : values.strategyTitle;
  return <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className={styles.previewModal} role="dialog" aria-modal="true" aria-labelledby="preview-title"><header><div><small>COMMUNITY PREVIEW</small><h2 id="preview-title">发布预览</h2></div><button type="button" aria-label="关闭预览" onClick={onClose}><X /></button></header><div className={styles.previewCard}><div className={styles.previewAuthor}><span>AZ</span><strong>Anna Zhang</strong><em>{kind === "factor" ? "因子" : kind === "module" ? "策略模块" : "完整策略"}</em></div><h3>{title}</h3><p>{kind === "factor" ? values.factorDescription || values.expression : kind === "module" ? values.ruleSummary : values.oneLineIntroduction}</p>{kind === "strategy" && strategy?.backtest ? <div className={styles.previewMetrics}><span><small>年化收益</small><strong>{(strategy.backtest.cagr * 100).toFixed(2)}%</strong></span><span><small>Sharpe</small><strong>{strategy.backtest.sharpe.toFixed(2)}</strong></span><span><small>最大回撤</small><strong>{(strategy.backtest.maxDrawdown * 100).toFixed(2)}%</strong></span></div> : null}{kind === "strategy" && strategy && !strategy.backtest ? <p className={styles.noBacktest}>当前工作区尚无有效回测结果</p> : null}{kind === "factor" ? <code>{values.expression}</code> : null}{tags.length ? <div className={styles.previewTags}>{tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}</div><footer><button type="button" onClick={onClose}>继续编辑</button><button type="button" disabled={busy} onClick={onConfirm}><Send />{busy ? "发布中…" : "确认发布"}</button></footer></section></div>;
}

function draftValues(post: CommunityPost): Values {
  if (post.type === "factor") return { ...INITIAL, factorName: post.factorName, factorType: post.factorTypeCode ?? FACTOR_TYPES.find(([, label]) => label === post.factorType)?.[0] ?? "other", expression: post.expression, factorDescription: post.description ?? "" };
  if (post.type === "strategy_module") return { ...INITIAL, moduleName: post.moduleName, moduleType: post.moduleType, ruleSummary: post.ruleSummary, ruleExpression: post.ruleExpression, moduleDescription: post.description ?? "" };
  if (post.type === "complete_strategy") return { ...INITIAL, strategyTitle: post.communityTitle, oneLineIntroduction: post.oneLineIntroduction, detailedDescription: post.detailedDescription ?? "" };
  return { ...INITIAL, questionTitle: post.title, questionContent: post.content };
}

function draftTitle(post: CommunityPost) {
  if (post.type === "factor") return post.factorName || "未命名因子草稿";
  if (post.type === "strategy_module") return post.moduleName || "未命名策略模块草稿";
  if (post.type === "complete_strategy") return post.communityTitle || "未命名完整策略草稿";
  return post.title || "未命名提问草稿";
}

export function CommunityPublishForm({ kind, workspaceId, strategyId, draftQueryId }: { kind: CommunityPublishKind; workspaceId?: string; strategyId?: string; draftQueryId?: string }) {
  const router = useRouter();
  const [values, setValues] = useState<Values>(INITIAL);
  const [selectedTags, setSelectedTags] = useState<string[]>(kind === "strategy" ? [...STRATEGY_TAGS] : []);
  const [sourceWorkspaceId, setSourceWorkspaceId] = useState<string>();
  const [strategyOption, setStrategyOption] = useState<PublishStrategyOption>();
  const [errors, setErrors] = useState<Record<string,string>>({});
  const [busy, setBusy] = useState(false);
  const [draftId, setDraftId] = useState<string | undefined>(draftQueryId);
  const [drafts, setDrafts] = useState<CommunityPost[]>([]);
  const [draftsOpen, setDraftsOpen] = useState(false);
  const [draftSaved, setDraftSaved] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [contextError, setContextError] = useState("");
  const [loadingContext, setLoadingContext] = useState(true);
  const copy = PAGE_COPY[kind];

  const refreshDrafts = useCallback(async () => {
    setDrafts(await communityService.getDraftsByType(CONTENT_TYPE[kind]));
  }, [kind]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await refreshDrafts();
        if (draftQueryId) {
          const draft = await communityService.getDraftById(draftQueryId);
          if (!draft || draft.type !== CONTENT_TYPE[kind]) throw new Error("未找到对应草稿");
          if (!active) return;
          setValues(draftValues(draft)); setSelectedTags(draft.tags); setDraftId(draft.id); setDraftSaved(true); setSourceWorkspaceId(draft.sourceWorkspaceId);
          if (draft.type === "complete_strategy") {
            setStrategyOption({ sourceWorkspaceId: draft.sourceWorkspaceId ?? draft.sourceStrategyId, strategyId: draft.sourceStrategyId, strategyName: draft.configurationSnapshot.strategyName, description: draft.detailedDescription ?? "", configurationSnapshot: draft.configurationSnapshot, backtest: draft.backtestSnapshot, backtestRef: draft.backtestRef });
          }
          return;
        }
        if (kind === "factor" && workspaceId) {
          const factor = await workspaceService.getFactor(workspaceId);
          if (!factor) throw new Error("未找到对应 Workspace 因子");
          const prefill = createFactorPublishPrefill(factor);
          if (!active) return;
          setSourceWorkspaceId(prefill.sourceWorkspaceId);
          setValues((current) => ({ ...current, factorName: prefill.factorName, factorType: prefill.factorTypeCode, expression: prefill.expression, factorDescription: prefill.description }));
        }
        if (kind === "module" && workspaceId) {
          const moduleAsset = await workspaceService.getStrategyModule(workspaceId);
          if (!moduleAsset) throw new Error("未找到对应 Workspace 策略模块");
          const prefill = createModulePublishPrefill(moduleAsset);
          if (!active) return;
          setSourceWorkspaceId(prefill.sourceWorkspaceId);
          setValues((current) => ({ ...current, moduleName: prefill.moduleName, moduleType: prefill.moduleType, ruleSummary: prefill.ruleSummary, ruleExpression: prefill.ruleExpression, moduleDescription: prefill.description }));
        }
        if (kind === "strategy") {
          const snapshot = await workspaceService.getSnapshot();
          const selected = strategyId ? snapshot.completeStrategies.find((item) => item.id === strategyId) : snapshot.completeStrategies.find((item) => item.backtestRef === "dashboard_v1");
          if (!selected) throw new Error(strategyId ? "未找到对应 Workspace 完整策略" : "当前工作区没有可发布的完整策略");
          const context = await workspaceService.resolveBacktestContext(selected.id);
          let backtest;
          if (context.status === "ready") {
            const [dashboardStrategy, metrics] = await Promise.all([dataService.getStrategySummary(), dataService.getBacktestMetrics()]);
            backtest = { backtestId: DEMO_BACKTEST_ID, version: "bt_v2", dateFrom: dashboardStrategy.backtestPeriod[0], dateTo: dashboardStrategy.backtestPeriod[1], totalReturn: metrics.totalReturn, cagr: metrics.cagr, sharpe: metrics.sharpe, maxDrawdown: metrics.maxDrawdown };
          }
          const prefill = createStrategyPublishPrefill(snapshot, selected, backtest);
          if (!active) return;
          setStrategyOption(prefill); setSourceWorkspaceId(prefill.sourceWorkspaceId);
          setValues((current) => ({ ...current, strategyTitle: prefill.strategyName, oneLineIntroduction: prefill.description }));
        }
      } catch (reason) {
        if (active) setContextError(reason instanceof Error ? reason.message : "发布上下文加载失败");
      } finally {
        if (active) setLoadingContext(false);
      }
    })();
    return () => { active = false; };
  }, [draftQueryId, kind, refreshDrafts, strategyId, workspaceId]);

  function update<K extends keyof Values>(key: K, value: Values[K]) { setValues((current) => ({ ...current, [key]: value })); setDraftSaved(false); setErrors((current) => ({ ...current, [key]: "" })); }
  function updateTags(tags: string[]) { setSelectedTags(tags); setDraftSaved(false); }

  const ready = useMemo(() => {
    if (kind === "factor") return Boolean(values.factorName.trim() && values.factorType && values.expression.trim());
    if (kind === "module") return Boolean(values.moduleName.trim() && values.moduleType && values.ruleSummary.trim() && values.ruleExpression.trim());
    if (kind === "strategy") return Boolean(strategyOption && values.strategyTitle.trim() && values.oneLineIntroduction.trim());
    return Boolean(values.questionTitle.trim());
  }, [kind, strategyOption, values]);

  function validate() {
    const next: Record<string,string> = {};
    if (kind === "factor") { if (!values.factorName.trim()) next.factorName = "请输入因子名称"; if (!values.factorType) next.factorType = "请选择因子类型"; if (!values.expression.trim()) next.expression = "请输入因子公式"; }
    if (kind === "module") { if (!values.moduleName.trim()) next.moduleName = "请输入模块名称"; if (!values.moduleType) next.moduleType = "请选择模块类型"; if (!values.ruleSummary.trim()) next.ruleSummary = "请输入规则说明"; if (!values.ruleExpression.trim()) next.ruleExpression = "请输入模块规则"; }
    if (kind === "strategy") { if (!strategyOption) next.strategy = "没有可发布的 Workspace 完整策略"; if (!values.strategyTitle.trim()) next.strategyTitle = "请输入标题"; if (!values.oneLineIntroduction.trim()) next.oneLineIntroduction = "请输入一句话介绍"; }
    if (kind === "question" && !values.questionTitle.trim()) next.questionTitle = "请输入提问标题";
    setErrors(next); return Object.keys(next).length === 0;
  }

  async function createPost(status: "draft" | "published"): Promise<CommunityPost> {
    if (kind === "factor") { const option = FACTOR_TYPES.find(([value]) => value === values.factorType); return communityService.createFactorPost({ factorName: values.factorName, factorTypeCode: values.factorType, factorType: option?.[1] ?? "", expression: values.expression, description: values.factorDescription, status, draftId, sourceWorkspaceId }); }
    if (kind === "module") return communityService.createStrategyModulePost({ moduleName: values.moduleName, moduleType: values.moduleType, ruleSummary: values.ruleSummary, ruleExpression: values.ruleExpression, description: values.moduleDescription, status, draftId, sourceWorkspaceId });
    if (kind === "strategy") { if (!strategyOption) throw new Error("没有可发布的完整策略"); return communityService.createCompleteStrategyPost({ sourceStrategyId: strategyOption.strategyId, sourceWorkspaceId: strategyOption.sourceWorkspaceId, configurationSnapshot: strategyOption.configurationSnapshot, backtestSnapshot: strategyOption.backtest, backtestRef: strategyOption.backtestRef, communityTitle: values.strategyTitle, oneLineIntroduction: values.oneLineIntroduction, detailedDescription: values.detailedDescription, tags: selectedTags, status, draftId }); }
    return communityService.createQuestionPost({ title: values.questionTitle, content: values.questionContent, tags: selectedTags, status, draftId });
  }

  async function saveDraft() {
    if (busy) return; setBusy(true); setToast("");
    try { const post = await createPost("draft"); setDraftId(post.id); setDraftSaved(true); setToast("草稿已保存，仅你自己可见"); await refreshDrafts(); }
    catch (reason) { setToast(reason instanceof Error ? reason.message : "草稿保存失败"); }
    finally { setBusy(false); }
  }

  async function publish() {
    if (busy || !validate()) return; setBusy(true); setToast("");
    try { const post = await createPost("published"); await refreshDrafts(); setToast("发布成功，正在进入详情页…"); window.setTimeout(() => router.push(`/community/${post.id}`), 450); }
    catch (reason) { setToast(reason instanceof Error ? reason.message : "发布失败，请稍后重试"); setBusy(false); setPreviewOpen(false); }
  }

  async function deleteDraft(id: string) {
    if (busy) return;
    setBusy(true);
    try { await communityService.deleteDraft(id); if (draftId === id) { setDraftId(undefined); setDraftSaved(false); } await refreshDrafts(); setToast("草稿已删除"); }
    finally { setBusy(false); }
  }

  function submit(event: FormEvent) { event.preventDefault(); if (!validate()) return; if (kind === "question") void publish(); else setPreviewOpen(true); }

  return <div className={styles.page}>
    <nav className={styles.breadcrumb}><Link href="/community">社区</Link><span>›</span><strong>{copy.breadcrumb}</strong></nav>
    <header className={styles.pageHeader}><PublishBackButton /><div><h1>{copy.title}</h1><p>{copy.subtitle}</p></div></header>
    <section className={styles.draftShelf} aria-label="未完成草稿">
      <button type="button" aria-expanded={draftsOpen} onClick={() => setDraftsOpen((value) => !value)}>未完成草稿（{drafts.length}）<ChevronDown /></button>
      {draftsOpen ? <div>{drafts.length ? drafts.map((draft) => <article key={draft.id}><span><strong>{draftTitle(draft)}</strong><small>更新于 {new Date(draft.updatedAt).toLocaleString("zh-CN")}</small></span><Link href={`${PUBLISH_ROUTE[kind]}?draftId=${draft.id}`}>继续编辑</Link><button type="button" aria-label={`删除 ${draftTitle(draft)}`} disabled={busy} onClick={() => void deleteDraft(draft.id)}><Trash2 />删除</button></article>) : <p>当前没有未完成草稿。</p>}</div> : null}
    </section>
    {contextError ? <p className={styles.contextError} role="alert">{contextError}</p> : null}
    <div className={styles.layout}><form className={styles.formCard} onSubmit={submit} noValidate>
      {loadingContext ? <p className={styles.contextLoading}>正在加载发布上下文…</p> : null}
      {kind === "factor" ? <FactorFields values={values} errors={errors} update={update} /> : null}
      {kind === "module" ? <ModuleFields values={values} errors={errors} update={update} /> : null}
      {kind === "strategy" ? <StrategyFields values={values} errors={errors} update={update} tags={selectedTags} setTags={updateTags} strategy={strategyOption} /> : null}
      {kind === "question" ? <QuestionFields values={values} errors={errors} update={update} tags={selectedTags} setTags={updateTags} /> : null}
      <div className={styles.actions}><button type="button" className={styles.secondary} disabled={busy || loadingContext || Boolean(contextError && kind === "strategy")} onClick={() => void saveDraft()}>{busy ? "保存中…" : "保存草稿"}</button><button type="submit" className={styles.primary} disabled={busy || loadingContext || (kind === "strategy" && !strategyOption)}>{kind === "question" ? <Send /> : null}{busy ? "处理中…" : kind === "question" ? "发布到社区" : "预览并发布 →"}</button></div>
    </form><aside className={styles.helpColumn}>{kind === "factor" ? <FactorHelp /> : null}{kind === "module" ? <ModuleHelp /> : null}{kind === "question" ? <QuestionHelp /> : null}{kind === "strategy" ? <StrategyHelp /> : null}<StatusCard saved={draftSaved} ready={ready} /></aside></div>
    {toast ? <div className={styles.toast} role="status">{toast}</div> : null}
    {previewOpen && kind !== "question" ? <PreviewModal kind={kind} values={values} tags={selectedTags} strategy={strategyOption} onClose={() => setPreviewOpen(false)} onConfirm={() => void publish()} busy={busy} /> : null}
  </div>;
}

type Update = <K extends keyof Values>(key: K, value: Values[K]) => void;
function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) { return <header className={styles.sectionHeader}><h2>{title}</h2><p>{subtitle}</p></header>; }

function FactorFields({ values, errors, update }: { values: Values; errors: Record<string,string>; update: Update }) { return <><SectionHeader title="基本信息" subtitle="填写因子基本信息，确保因子清晰、可理解。" /><div className={styles.twoColumns}><Field label="因子名称" required error={errors.factorName}><input value={values.factorName} placeholder="例如：过去20日波动率" onChange={(event) => update("factorName", event.target.value)} /></Field><Field label="因子类型" required error={errors.factorType}><span className={styles.selectWrap}><select value={values.factorType} onChange={(event) => update("factorType", event.target.value)}><option value="">请选择因子类型</option>{FACTOR_TYPES.map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select><ChevronDown /></span></Field></div><Field label="因子公式" required error={errors.expression} hint={<>直接输入因子公式。可以使用平台支持的字段和函数，例如 Std、Ref、Rank 等。 <Link href="/quantbuddy">需要帮助？问问 QuantBuddy 如何把自然语言转成公式</Link></>}><FormulaEditor label="因子公式" value={values.expression} maxLength={2000} placeholder="Std($close / Ref($close, 1) - 1, 20)" onChange={(value) => update("expression", value)} /></Field><Field label="详细说明"><textarea value={values.factorDescription} placeholder="说明这个想法来自哪里、为什么可能有效，以及需要注意的问题。" onChange={(event) => update("factorDescription", event.target.value)} /></Field></>; }

function ModuleFields({ values, errors, update }: { values: Values; errors: Record<string,string>; update: Update }) { const stage = STRATEGY_MODULE_STAGE_MAP[values.moduleType]; return <><SectionHeader title="基本信息" subtitle="填写模块名称、类型和规则，方便其他人理解与复用。" /><div className={styles.twoColumns}><Field label="模块名称" required error={errors.moduleName}><input value={values.moduleName} placeholder="例如：趋势降仓模块" onChange={(event) => update("moduleName", event.target.value)} /></Field><Field label="模块类型" required error={errors.moduleType} hint={`该模块通常用于${STAGE_LABELS[stage]}。适用阶段由系统自动映射。`}><span className={styles.selectWrap}><select value={values.moduleType} onChange={(event) => update("moduleType", event.target.value as StrategyModuleType)}>{Object.entries(STRATEGY_MODULE_TYPE_LABELS).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select><ChevronDown /></span></Field></div><Field label="规则说明" required error={errors.ruleSummary}><input value={values.ruleSummary} placeholder="例如：当市场趋势走弱时，降低股票总仓位。" onChange={(event) => update("ruleSummary", event.target.value)} /></Field><Field label="模块规则" required error={errors.ruleExpression} hint={<>规则仅作为文本保存，不会在浏览器中执行。 <Link href="/quantbuddy">需要帮助？问问 QuantBuddy 如何把想法转成模块规则</Link></>}><FormulaEditor label="模块规则" value={values.ruleExpression} maxLength={2000} placeholder="If(IndexClose < MA(IndexClose, 120), PortfolioWeight * 0.5, PortfolioWeight)" onChange={(value) => update("ruleExpression", value)} /></Field><Field label="详细说明"><textarea value={values.moduleDescription} placeholder="说明这个模块解决什么问题、应如何使用，以及需要注意的情况。" onChange={(event) => update("moduleDescription", event.target.value)} /></Field></>; }

function StrategyFields({ values, errors, update, tags, setTags, strategy }: { values: Values; errors: Record<string,string>; update: Update; tags: string[]; setTags: (tags:string[])=>void; strategy?: PublishStrategyOption }) {
  const config = strategy?.configurationSnapshot;
  return <><section className={styles.numberedSection}><SectionHeader title="1　选择要发布的策略" subtitle="配置来自“我的策略”工作区，在发布页中只读。" /><Field label="完整策略" required error={errors.strategy}><span className={styles.selectWrap}><select value={strategy?.strategyId ?? ""} disabled><option>{strategy?.strategyName ?? "没有可发布的策略"}</option></select><ChevronDown /></span></Field><Link className={styles.inlineLink} href="/strategy">前往“我的策略”查看</Link></section>{config ? <section className={styles.numberedSection}><SectionHeader title="2　策略配置摘要" subtitle="配置来自所选 Workspace 资产，在发布页中只读。" /><dl className={styles.configGrid}><div><dt>股票池</dt><dd>{config.universe}</dd></div><div><dt>因子 / 特征集</dt><dd>{config.featureSet?.name ?? "--"}</dd></div><div><dt>预测模型</dt><dd>{config.model ?? "--"}</dd></div><div><dt>选股模块</dt><dd>{config.stockSelectionModule ?? "--"}</dd></div><div><dt>调仓模块</dt><dd>{config.rebalanceModule ?? "--"}</dd></div><div><dt>风险控制模块</dt><dd>{config.riskControlModule ?? "--"}</dd></div></dl><details className={styles.configDetails}><summary>查看完整配置详情</summary><p>Workspace ID：{strategy?.sourceWorkspaceId}</p></details><Link className={styles.inlineLink} href={`/strategy/create/complete?id=${strategy?.sourceWorkspaceId}`}>前往“我的策略”修改</Link></section> : null}<section className={styles.numberedSection}><SectionHeader title="3　发布介绍" subtitle="向社区介绍你的策略，帮助他人更好理解和使用。" /><Field label="标题" required error={errors.strategyTitle}><input value={values.strategyTitle} maxLength={60} placeholder="沪深300 LightGBM Top-5：一次面向初学者的 Qlib 实验" onChange={(event) => update("strategyTitle", event.target.value)} /><span className={styles.counter}>{values.strategyTitle.length}/60</span></Field><Field label="一句话介绍" required error={errors.oneLineIntroduction}><input value={values.oneLineIntroduction} maxLength={80} placeholder="用一句话概括你的策略核心思想" onChange={(event) => update("oneLineIntroduction", event.target.value)} /><span className={styles.counter}>{values.oneLineIntroduction.length}/80</span></Field><Field label="详细说明"><textarea value={values.detailedDescription} maxLength={1000} placeholder="详细介绍你的策略逻辑、使用方法、适用场景等（可选）" onChange={(event) => update("detailedDescription", event.target.value)} /><span className={styles.counter}>{values.detailedDescription.length}/1000</span></Field><Field label="标签（可选）"><TagSelector options={STRATEGY_TAGS} selected={tags} onChange={setTags} /></Field></section>{strategy?.backtest ? <section className={styles.numberedSection}><SectionHeader title="4　关联回测结果" subtitle="自动关联所选策略的有效回测引用。" /><div className={styles.backtestRow}><span><small>回测版本</small><strong>{strategy.backtest.version}</strong></span><span><small>回测区间</small><strong>{strategy.backtest.dateFrom} — {strategy.backtest.dateTo}</strong></span><span><small>累计收益</small><strong>{(strategy.backtest.totalReturn*100).toFixed(2)}%</strong></span><span><small>年化收益</small><strong>{(strategy.backtest.cagr*100).toFixed(2)}%</strong></span><span><small>Sharpe</small><strong>{strategy.backtest.sharpe.toFixed(2)}</strong></span><span><small>最大回撤</small><strong>{(strategy.backtest.maxDrawdown*100).toFixed(2)}%</strong></span><button type="button" title="当前 Demo 仅有一个有效历史版本">切换历史版本</button></div></section> : strategy ? <section className={styles.numberedSection}><SectionHeader title="4　关联回测结果" subtitle="当前工作区尚无有效回测结果。可以发布配置介绍，但不会附带基准策略指标。" /><p className={styles.noBacktest}>当前工作区尚无有效回测结果</p></section> : null}</>;
}

function QuestionFields({ values, errors, update, tags, setTags }: { values: Values; errors: Record<string,string>; update: Update; tags: string[]; setTags:(tags:string[])=>void }) { return <><SectionHeader title="发布提问" subtitle="越具体的问题越容易获得有帮助的回答。" /><Field label="标题" required error={errors.questionTitle}><input value={values.questionTitle} placeholder="例如：为什么我的策略收益很高，但 Rank IC 很低？" onChange={(event) => update("questionTitle", event.target.value)} /></Field><Field label="内容"><textarea className={styles.largeTextarea} value={values.questionContent} maxLength={3000} placeholder="详细描述你的问题或想法，越具体越容易得到帮助。" onChange={(event) => update("questionContent", event.target.value)} /><span className={styles.counter}>{values.questionContent.length}/3000</span></Field><Field label="标签（可选）" hint="选择合适的标签，可以让更多小伙伴看到你的问题。"><TagSelector options={QUESTION_TAGS} selected={tags} onChange={setTags} /></Field></>; }

function FactorHelp() { return <><HelpCard title="新手提示"><Info /><h3>什么是因子？</h3><p>因子是用一个数字描述股票某种特征，例如动量、波动率或成交量变化。</p><hr /><h3>不用担心公式</h3><p>不懂公式也没关系，可以随时找 QuantBuddy 帮你梳理。</p></HelpCard><HelpCard title="发布后会展示什么？"><ul><li>因子逻辑与计算方式</li><li>IC、Rank IC 等验证结果（如有）</li><li>其他用户的 Star、评论和 Fork</li></ul></HelpCard></>; }
function ModuleHelp() { return <><HelpCard title="新手提示"><Info /><h3>什么是策略模块？</h3><p>策略模块是完整策略中的一个可复用环节，例如选股、权重分配、调仓或风险控制。</p><hr /><h3>它和完整策略有什么区别？</h3><p>完整策略可以独立回测；策略模块通常需要加入一个完整策略后才能运行。</p></HelpCard><HelpCard title="发布后会展示什么？"><ul><li>模块类型</li><li>规则逻辑与表达式</li><li>其他用户的 Star、评论和 Fork</li></ul></HelpCard></>; }
function QuestionHelp() { return <HelpCard title="这里可以聊什么？"><CircleHelp /><ul><li>询问不懂的量化概念</li><li>讨论回测数据和问题</li><li>分享策略想法与优化思路</li><li>提出产品建议或随便聊聊</li></ul></HelpCard>; }
function StrategyHelp() { return <HelpCard title="发布说明"><Sparkles /><p>发布页只读取所选 Workspace 策略，不会修改策略配置或回测结果。</p><ul><li>配置与有效回测保持只读</li><li>没有回测时只发布配置介绍</li><li>Fork 后仍需重新回测</li></ul></HelpCard>; }
