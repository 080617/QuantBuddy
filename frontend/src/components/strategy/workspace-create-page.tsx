"use client";

import { ArrowLeft, BarChart3, Box, Check, Layers3, Lightbulb, Save, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { STRATEGY_MODULE_STAGE_MAP, STRATEGY_MODULE_TYPE_LABELS } from "@/lib/community-constants";
import { QUANT_MODELS } from "@/mocks/models";
import { resolveCompleteStrategyPreselection, type CompleteStrategyPreselection } from "@/services/workspace-integration";
import { workspaceService } from "@/services/workspace-service";
import type { StrategyModuleType } from "@/types/community";
import type { WorkspaceCompleteStrategyInput, WorkspaceFactorInput, WorkspaceFactorSetInput, WorkspaceFactorType, WorkspaceModuleSelections, WorkspaceSnapshot, WorkspaceStrategyModuleInput } from "@/types/workspace";

export type WorkspaceCreateKind = "complete" | "module" | "factor" | "factor-set";
const EMPTY: WorkspaceSnapshot = { completeStrategies: [], strategyModules: [], factors: [], factorSets: [], counts: { completeStrategies: 0, strategyModules: 0, factorsAndFactorSets: 0 } };
const FACTOR_TYPES: readonly { value: WorkspaceFactorType; label: string }[] = [
  { value: "momentum", label: "动量因子" }, { value: "volatility", label: "波动率因子" }, { value: "volume", label: "成交量因子" },
  { value: "price", label: "价格因子" }, { value: "technical", label: "技术因子" }, { value: "composite", label: "复合因子" }, { value: "other", label: "其他" },
];
const MODULE_TYPES = Object.keys(STRATEGY_MODULE_TYPE_LABELS) as StrategyModuleType[];
const KIND_META = {
  complete: { title: "创建完整策略", subtitle: "从你的因子、因子集和策略模块中组装一个可回测的完整策略", tab: "complete" },
  module: { title: "创建策略模块", subtitle: "编写一个可复用的策略模块，之后可加入完整策略中使用", tab: "module" },
  factor: { title: "创建因子", subtitle: "编写一个可计算的因子公式，之后可加入完整策略或组合成因子集", tab: "factor" },
  "factor-set": { title: "创建因子集", subtitle: "将多个单个因子组合成一个可重复使用的命名集合", tab: "factor" },
} as const;

function CreateTabs({ kind }: { kind: WorkspaceCreateKind }) {
  const active = KIND_META[kind].tab;
  return <nav className="wc-tabs" aria-label="Workspace 创建类型">
    <Link className={active === "complete" ? "is-active" : ""} href="/strategy/create/complete"><Layers3 />完整策略</Link>
    <Link className={active === "module" ? "is-active" : ""} href="/strategy/create/module"><Box />策略模块</Link>
    <Link className={active === "factor" ? "is-active" : ""} href="/strategy/create/factor"><BarChart3 />因子与因子集</Link>
  </nav>;
}

function ResourceAside({ snapshot, children }: { snapshot: WorkspaceSnapshot; children: React.ReactNode }) {
  return <aside className="wc-aside"><section><h2>你的工作区资源</h2><div><span>因子与因子集</span><strong>{snapshot.counts.factorsAndFactorSets}</strong></div><div><span>策略模块</span><strong>{snapshot.counts.strategyModules}</strong></div><div><span>完整策略</span><strong>{snapshot.counts.completeStrategies}</strong></div></section><section><h2><Lightbulb />创建提示</h2>{children}</section></aside>;
}

function Field({ label, required, children, hint }: { label: string; required?: boolean; children: React.ReactNode; hint?: string }) {
  return <label className="wc-field"><span>{label}{required && <b> *</b>}</span>{children}{hint && <small>{hint}</small>}</label>;
}

const DEFAULT_MODULES: WorkspaceModuleSelections = { stock_selection: "builtin-stock-top5", weighting: "builtin-equal-weight", rebalance: "builtin-daily-rebalance", risk_control: "builtin-market-risk" };

function CompleteForm({ snapshot, editId, preselection }: { snapshot: WorkspaceSnapshot; editId?: string; preselection: CompleteStrategyPreselection }) {
  const router = useRouter(); const [busy, setBusy] = useState(false); const [message, setMessage] = useState("");
  const [name, setName] = useState(""); const [description, setDescription] = useState(""); const [modelId, setModelId] = useState("lightgbm");
  const [factorIds, setFactorIds] = useState<string[]>(["qlib-alpha158"]);
  const [modules, setModules] = useState<WorkspaceModuleSelections>(DEFAULT_MODULES);
  const { factorId, factorSetId, moduleId } = preselection;
  useEffect(() => {
    if (!snapshot.factorSets.length && !snapshot.factors.length && !snapshot.strategyModules.length) return;
    let active = true;
    void (async () => {
      const item = editId ? await workspaceService.getCompleteStrategy(editId) : null;
      const baseFactors = item?.factorAssetIds?.length ? item.factorAssetIds : ["qlib-alpha158"];
      const baseModules: WorkspaceModuleSelections = item ? {
        stock_selection: item.moduleSelections?.stock_selection ?? DEFAULT_MODULES.stock_selection,
        weighting: item.moduleSelections?.weighting ?? DEFAULT_MODULES.weighting,
        rebalance: item.moduleSelections?.rebalance ?? DEFAULT_MODULES.rebalance,
        risk_control: item.moduleSelections?.risk_control ?? DEFAULT_MODULES.risk_control,
      } : DEFAULT_MODULES;
      const merged = resolveCompleteStrategyPreselection(snapshot, baseFactors, baseModules, { factorId, factorSetId, moduleId });
      if (!active) return;
      if (item) { setName(item.name); setDescription(item.description ?? ""); setModelId(item.modelId ?? "lightgbm"); }
      else if (editId) setMessage("未找到要编辑的策略，将按新策略创建。");
      setFactorIds(merged.factorIds);
      setModules(merged.modules);
      if (merged.notices.length) setMessage(merged.notices.join(" "));
    })();
    return () => { active = false; };
  }, [editId, factorId, factorSetId, moduleId, snapshot]);
  const model = QUANT_MODELS.find((item) => item.id === modelId) ?? QUANT_MODELS[0];
  const input = (status: "draft" | "backtested"): WorkspaceCompleteStrategyInput => ({ name, description, universe: "沪深300", factorAssetIds: factorIds, modelId, modelName: model.name.replace(/（.*$/, ""), moduleSelections: modules, status });
  function toggleFactor(id: string) { setFactorIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]); }
  const moduleOptions = (type: StrategyModuleType) => snapshot.strategyModules.filter((item) => item.moduleType === type);
  async function save(mode: "draft" | "backtest") {
    setMessage(""); if (!name.trim()) { setMessage("请填写策略名称"); return; } if (!factorIds.length) { setMessage("请至少选择一个因子或因子集"); return; }
    setBusy(true); try {
      const draftInput = input("draft");
      if (mode === "backtest" && !workspaceService.canRunDemoBacktest({ ...draftInput, status: "backtested" })) {
        await (editId ? workspaceService.updateCompleteStrategy(editId, draftInput) : workspaceService.createCompleteStrategy(draftInput));
        setMessage("当前 Demo 仅支持已接通的 LightGBM + Qlib Alpha158 基线运行真实回测。该配置已保存为草稿。"); return;
      }
      const value = await (editId ? workspaceService.updateCompleteStrategy(editId, input(mode === "backtest" ? "backtested" : "draft")) : workspaceService.createCompleteStrategy(input(mode === "backtest" ? "backtested" : "draft")));
      router.push(mode === "backtest" ? `/backtest?id=${value.id}` : "/strategy?tab=complete");
    } catch (error) { setMessage(error instanceof Error ? error.message : "保存失败，请重试"); } finally { setBusy(false); }
  }
  return <><div className="wc-form-column"><section className="wc-section"><h2><i>1</i>基础信息</h2><Field label="策略名称" required><input value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="例如：我的沪深300成长策略" /></Field><Field label="一句话说明" hint={`${description.length}/100`}><textarea value={description} maxLength={100} onChange={(e) => setDescription(e.target.value)} placeholder="概括策略的核心思路" /></Field></section>
    <section className="wc-section"><h2><i>2</i>核心配置</h2><Field label="股票池" required><select value="沪深300" disabled><option>沪深300</option></select></Field><Field label="因子 / 因子集" required><div className="wc-choice-list">{[...snapshot.factorSets, ...snapshot.factors].map((item) => <button type="button" key={item.id} className={factorIds.includes(item.id) ? "is-selected" : ""} onClick={() => toggleFactor(item.id)}><span>{factorIds.includes(item.id) && <Check />}{item.name}</span><small>{item.assetKind === "factor_set" ? item.origin === "builtin" ? "因子集 · 平台内置" : "因子集" : item.origin === "community_fork" ? "单个因子 · Community Fork" : item.origin === "builtin" ? "单个因子 · 平台内置" : "单个因子"}</small></button>)}</div></Field><Field label="预测模型" required><select value={modelId} onChange={(e) => setModelId(e.target.value)}>{QUANT_MODELS.map((item) => <option key={item.id} value={item.id}>{item.name}{item.id !== "lightgbm" ? " · 仅可保存草稿" : ""}</option>)}</select></Field>{modelId !== "lightgbm" && <p className="wc-warning">当前 Demo 暂不支持该模型运行回测，但可以正常保存为草稿。</p>}</section>
    <section className="wc-section"><h2><i>3</i>策略模块配置</h2><div className="wc-module-grid">{(["stock_selection", "weighting", "rebalance", "risk_control"] as const).map((type) => <Field key={type} label={STRATEGY_MODULE_TYPE_LABELS[type]} required><select value={modules[type] ?? ""} onChange={(e) => setModules((current) => ({ ...current, [type]: e.target.value }))}>{moduleOptions(type).map((item) => <option key={item.id} value={item.id}>{item.name}{item.origin === "builtin" ? "（平台默认）" : ""}</option>)}</select></Field>)}</div></section>
    <section className="wc-section"><h2><i>4</i>说明与下一步</h2><p className="wc-info">因子与策略模块均来自你的工作区。可先保存为草稿，再调整配置或运行回测。</p></section>{message && <p className="wc-error" role="alert">{message}</p>}<div className="wc-actions"><button type="button" disabled={busy} onClick={() => void save("draft")}><Save />{busy ? "正在保存…" : "保存草稿"}</button><button className="is-primary" type="button" disabled={busy} onClick={() => void save("backtest")}>运行回测</button></div></div>
    <ResourceAside snapshot={snapshot}><ul><li>至少选择一个因子或因子集。</li><li>四类模块分别从工作区对应类型中选择。</li><li>只有已接通的基线配置会复用真实 Demo 回测。</li></ul></ResourceAside></>;
}

function ModuleForm({ snapshot, editId }: { snapshot: WorkspaceSnapshot; editId?: string }) {
  const router = useRouter(); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [name, setName] = useState(""); const [summary, setSummary] = useState(""); const [type, setType] = useState<StrategyModuleType>("risk_control"); const [rule, setRule] = useState(""); const [description, setDescription] = useState("");
  useEffect(() => { if (!editId) return; void workspaceService.getStrategyModule(editId).then((item) => { if (!item || item.locked) return; setName(item.name); setSummary(item.ruleSummary); setType(item.moduleType); setRule(item.ruleExpression); setDescription(item.description ?? ""); }); }, [editId]);
  async function save(status: "draft" | "ready") { setError(""); setBusy(true); const input: WorkspaceStrategyModuleInput = { name, description, moduleType: type, ruleSummary: summary, ruleExpression: rule, status }; try { await (editId ? workspaceService.updateStrategyModule(editId, input) : workspaceService.createStrategyModule(input)); router.push("/strategy?tab=module"); } catch (e) { setError(e instanceof Error ? e.message : "保存失败"); } finally { setBusy(false); } }
  return <><div className="wc-form-column"><section className="wc-section"><h2><i>1</i>基础信息</h2><Field label="模块名称" required><input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：市场趋势降仓模块" /></Field><Field label="一句话说明" hint={`${summary.length}/100`}><textarea value={summary} maxLength={100} onChange={(e) => setSummary(e.target.value)} placeholder="说明模块解决的问题" /></Field></section><section className="wc-section"><h2><i>2</i>模块配置</h2><Field label="模块类型" required><select value={type} onChange={(e) => setType(e.target.value as StrategyModuleType)}>{MODULE_TYPES.map((value) => <option key={value} value={value}>{STRATEGY_MODULE_TYPE_LABELS[value]}</option>)}</select></Field><p className="wc-info">适用阶段由系统自动推导：{STRATEGY_MODULE_STAGE_MAP[type]}</p><Field label="模块规则" required hint="规则仅保存为文本，不会在浏览器执行"><textarea className="is-code" value={rule} onChange={(e) => setRule(e.target.value)} placeholder="If(IndexClose < MA(IndexClose, 120), PortfolioWeight * 0.5, PortfolioWeight)" /></Field><Field label="详细说明"><textarea value={description} onChange={(e) => setDescription(e.target.value)} /></Field></section>{error && <p className="wc-error">{error}</p>}<div className="wc-actions"><button disabled={busy} type="button" onClick={() => void save("draft")}><Save />保存草稿</button><button disabled={busy} className="is-primary" type="button" onClick={() => void save("ready")}>保存到我的策略模块</button></div></div><ResourceAside snapshot={snapshot}><ul><li>页面只有一个模块类型下拉框。</li><li>适用阶段由模块类型自动映射。</li><li>保存后可在完整策略中按类型选择。</li></ul></ResourceAside></>;
}

function FactorForm({ snapshot, editId }: { snapshot: WorkspaceSnapshot; editId?: string }) {
  const router = useRouter(); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [name, setName] = useState(""); const [type, setType] = useState<WorkspaceFactorType>("volatility"); const [expression, setExpression] = useState(""); const [description, setDescription] = useState("");
  useEffect(() => { if (!editId) return; void workspaceService.getFactor(editId).then((item) => { if (!item || item.locked) return; setName(item.name); setType(item.factorType); setExpression(item.expression); setDescription(item.description ?? ""); }); }, [editId]);
  async function save(status: "draft" | "ready") { setBusy(true); setError(""); const selected = FACTOR_TYPES.find((item) => item.value === type)!; const input: WorkspaceFactorInput = { name, description, factorType: type, factorTypeLabel: selected.label, expression, status }; try { await (editId ? workspaceService.updateFactor(editId, input) : workspaceService.createFactor(input)); router.push("/strategy?tab=factor"); } catch (e) { setError(e instanceof Error ? e.message : "保存失败"); } finally { setBusy(false); } }
  return <><div className="wc-form-column"><section className="wc-section"><h2><i>1</i>基础信息</h2><Field label="因子名称" required><input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：过去20日波动率" /></Field><Field label="因子类型" required><select value={type} onChange={(e) => setType(e.target.value as WorkspaceFactorType)}>{FACTOR_TYPES.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}</select></Field></section><section className="wc-section"><h2><i>2</i>因子公式</h2><Field label="因子公式" required hint="直接输入公式；只保存为文本，不执行任意代码"><textarea className="is-code" value={expression} onChange={(e) => setExpression(e.target.value)} placeholder="Std($close / Ref($close, 1) - 1, 20)" /></Field></section><section className="wc-section"><h2><i>3</i>详细说明</h2><Field label="详细说明"><textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="说明因子的含义、使用场景和风险" /></Field></section><section className="wc-section"><h2><i>4</i>说明与下一步</h2><p className="wc-info">新因子默认标记为未验证，不生成虚假的 IC、Rank IC 或验证结果。</p></section>{error && <p className="wc-error">{error}</p>}<div className="wc-actions"><button disabled={busy} type="button" onClick={() => void save("draft")}><Save />保存草稿</button><button disabled={busy} className="is-primary" type="button" onClick={() => void save("ready")}>保存到我的因子</button></div></div><ResourceAside snapshot={snapshot}><ul><li>因子是描述股票特征的可计算公式。</li><li>保存后可用于完整策略或因子集。</li><li>浏览器不会执行输入的公式。</li></ul></ResourceAside></>;
}

function FactorSetForm({ snapshot, editId }: { snapshot: WorkspaceSnapshot; editId?: string }) {
  const router = useRouter(); const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [name, setName] = useState(""); const [description, setDescription] = useState(""); const [selected, setSelected] = useState<string[]>([]); const [query, setQuery] = useState(""); const [source, setSource] = useState<"all" | "mine" | "builtin">("all");
  useEffect(() => { if (!editId) return; void workspaceService.getFactorSet(editId).then((item) => { if (!item || item.locked) return; setName(item.name); setDescription(item.description ?? ""); setSelected(item.factorIds); }); }, [editId]);
  const visible = useMemo(() => snapshot.factors.filter((item) => (source === "all" || (source === "mine" ? item.origin !== "builtin" : item.origin === "builtin")) && `${item.name} ${item.expression}`.toLowerCase().includes(query.toLowerCase())), [query, snapshot.factors, source]);
  function toggle(id: string) { setSelected((items) => items.includes(id) ? items.filter((value) => value !== id) : [...items, id]); }
  async function save(status: "draft" | "ready") { setBusy(true); setError(""); const input: WorkspaceFactorSetInput = { name, description, factorIds: selected, status }; try { await (editId ? workspaceService.updateFactorSet(editId, input) : workspaceService.createFactorSet(input)); router.push("/strategy?tab=factor"); } catch (e) { setError(e instanceof Error ? e.message : "保存失败"); } finally { setBusy(false); } }
  return <><div className="wc-form-column"><section className="wc-section"><h2><i>A</i>基础信息</h2><Field label="因子集名称" required><input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：我的量价因子集 v1" /></Field><Field label="一句话说明" hint={`${description.length}/100`}><input value={description} maxLength={100} onChange={(e) => setDescription(e.target.value)} placeholder="说明因子集的使用场景" /></Field></section><section className="wc-section"><h2><i>B</i>选择因子</h2><p>从已有单个因子中选择，第一版不允许因子集嵌套因子集。</p><div className="wc-search"><Search /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索因子名称或公式关键词" /></div><div className="wc-source-filters"><button type="button" className={source === "all" ? "is-active" : ""} onClick={() => setSource("all")}>全部</button><button type="button" className={source === "mine" ? "is-active" : ""} onClick={() => setSource("mine")}>我的因子</button><button type="button" className={source === "builtin" ? "is-active" : ""} onClick={() => setSource("builtin")}>平台内置</button></div><div className="wc-factor-catalog">{visible.map((item) => <button type="button" key={item.id} className={selected.includes(item.id) ? "is-selected" : ""} onClick={() => toggle(item.id)}><i>{selected.includes(item.id) && <Check />}</i><span><strong>{item.name}</strong><small>{item.factorTypeLabel}</small><code>{item.expression}</code></span></button>)}</div></section><section className="wc-section"><h2><i>C</i>已选因子 <small>已选择 {selected.length} 个因子</small></h2><div className="wc-selected-tags">{selected.map((id) => { const factor = snapshot.factors.find((item) => item.id === id); return factor ? <button type="button" key={id} onClick={() => toggle(id)}>{factor.name} ×</button> : null; })}</div></section>{error && <p className="wc-error">{error}</p>}<div className="wc-actions"><button disabled={busy} type="button" onClick={() => void save("draft")}><Save />保存草稿</button><button disabled={busy} className="is-primary" type="button" onClick={() => void save("ready")}>保存因子集</button></div></div><ResourceAside snapshot={snapshot}><ul><li>因子集不是新的公式，而是单个因子的集合。</li><li>正式保存至少选择两个单个因子。</li><li>Qlib Alpha158 不会作为可嵌套选项出现。</li></ul></ResourceAside></>;
}

export function WorkspaceCreatePage({ kind, editId, preselection = {} }: { kind: WorkspaceCreateKind; editId?: string; preselection?: CompleteStrategyPreselection }) {
  const router = useRouter(); const [snapshot, setSnapshot] = useState<WorkspaceSnapshot>(EMPTY);
  useEffect(() => { let active = true; void workspaceService.getSnapshot().then((data) => { if (active) setSnapshot(data); }); return () => { active = false; }; }, []);
  const meta = KIND_META[kind];
  return <div className="wc-page"><header className="wc-heading"><button type="button" aria-label="返回我的策略" onClick={() => router.push(`/strategy?tab=${meta.tab}`)}><ArrowLeft /></button><div><h1>{editId ? meta.title.replace("创建", "编辑") : meta.title}</h1><p>{meta.subtitle}</p></div></header><CreateTabs kind={kind} /><div className="wc-layout">{kind === "complete" && <CompleteForm snapshot={snapshot} editId={editId} preselection={preselection} />}{kind === "module" && <ModuleForm snapshot={snapshot} editId={editId} />}{kind === "factor" && <FactorForm snapshot={snapshot} editId={editId} />}{kind === "factor-set" && <FactorSetForm snapshot={snapshot} editId={editId} />}</div></div>;
}
