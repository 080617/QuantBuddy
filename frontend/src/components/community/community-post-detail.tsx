"use client";

import { ArrowLeft, CheckCircle2, UserPlus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { CommunityActionBar } from "@/components/community/community-action-bar";
import { COMMUNITY_TYPE_LABELS, STRATEGY_MODULE_TYPE_LABELS } from "@/lib/community-constants";
import { communityService } from "@/services/community-service";
import type { CommunityAnswer, CommunityPost, CommunityWorkspaceState } from "@/types/community";
import styles from "./community-detail.module.css";

const EMPTY_WORKSPACE: CommunityWorkspaceState = { factorPostIds: [], modulePostIds: [], forkedStrategyPostIds: [] };

function formatPercent(value: number) { return `${(value * 100).toFixed(2)}%`; }
function formatDate(value: string) { return new Date(value).toLocaleDateString("zh-CN", { year: "numeric", month: "long", day: "numeric" }); }

function DetailBody({ post }: { post: CommunityPost }) {
  if (post.type === "complete_strategy") {
    const config = post.configurationSnapshot, result = post.backtestSnapshot;
    return <>
      <section className={styles.section}><div className={styles.sectionTitle}><h2>策略配置</h2><p>来自发布时的配置快照</p></div><dl className={styles.detailGrid}>
        <div><dt>预测模型</dt><dd>{config.model ?? "--"}</dd></div><div><dt>因子 / 特征集</dt><dd>{config.featureSet?.name ?? "--"}</dd></div><div><dt>股票池</dt><dd>{config.universe}</dd></div><div><dt>选股规则</dt><dd>{config.stockSelectionModule ?? "--"}</dd></div><div><dt>调仓模块</dt><dd>{config.rebalanceModule ?? "--"}</dd></div><div><dt>策略名称</dt><dd>{config.strategyName}</dd></div>
      </dl></section>
      {result ? <section className={styles.section}><div className={styles.sectionTitle}><h2>回测表现</h2><p>{result.dateFrom} 至 {result.dateTo} · {result.version}</p></div><div className={styles.metricGrid}>
        <span><small>累计收益</small><strong>{formatPercent(result.totalReturn)}</strong></span><span className={styles.green}><small>年化收益</small><strong>{formatPercent(result.cagr)}</strong></span><span className={styles.orange}><small>Sharpe</small><strong>{result.sharpe.toFixed(2)}</strong></span><span className={styles.red}><small>最大回撤</small><strong>{formatPercent(result.maxDrawdown)}</strong></span>
      </div><Link className={styles.primaryLink} href={`/backtest?id=${config.strategyId}`}>查看完整回测</Link></section> : <section className={styles.section}><div className={styles.sectionTitle}><h2>回测表现</h2><p>当前工作区尚无有效回测结果</p></div></section>}
    </>;
  }
  if (post.type === "factor") return <>
    <section className={styles.section}><div className={styles.sectionTitle}><h2>因子定义</h2><p>{post.description}</p></div><dl className={styles.detailGrid}><div><dt>因子名称</dt><dd>{post.factorName}</dd></div><div><dt>因子类型</dt><dd>{post.factorType}</dd></div><div><dt>所需字段</dt><dd>{post.requiredFields?.join("、") || "未声明"}</dd></div><div><dt>验证状态</dt><dd>{post.verification?.verificationStatus === "verified" ? "已验证" : "待验证"}</dd></div></dl><pre className={styles.codeBlock}><code>{post.expression}</code></pre></section>
    <section className={styles.section}><div className={styles.sectionTitle}><h2>验证结果</h2><p>因子验证数据如实显示；未验证时不生成模拟数值。</p></div><div className={styles.verification}><CheckCircle2 /><span><small>IC</small><strong>{post.verification?.ic ?? "--"}</strong></span><span><small>Rank IC</small><strong>{post.verification?.rankIc ?? "--"}</strong></span></div></section>
  </>;
  if (post.type === "strategy_module") return <section className={styles.section}><div className={styles.sectionTitle}><h2>模块规则</h2><p>{post.description}</p></div><dl className={styles.detailGrid}><div><dt>模块名称</dt><dd>{post.moduleName}</dd></div><div><dt>模块类型</dt><dd>{STRATEGY_MODULE_TYPE_LABELS[post.moduleType]}</dd></div><div><dt>适用阶段（自动推导）</dt><dd>{post.applicableStage}</dd></div><div><dt>规则摘要</dt><dd>{post.ruleSummary}</dd></div></dl><pre className={styles.codeBlock}><code>{post.ruleExpression}</code></pre></section>;
  return <section className={styles.section}><div className={styles.questionContent}>{post.content || "该提问暂未补充正文。"}</div><div className={styles.tags}>{post.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></section>;
}

export function CommunityPostDetail({ postId }: { postId: string }) {
  const [post, setPost] = useState<CommunityPost | null>(null);
  const [answers, setAnswers] = useState<CommunityAnswer[]>([]);
  const [workspace, setWorkspace] = useState<CommunityWorkspaceState>(EMPTY_WORKSPACE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState("");
  const [notice, setNotice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const load = useCallback(async () => {
    const [postResult, answerItems, workspaceState] = await Promise.all([communityService.getPostById(postId), communityService.getAnswers(postId), communityService.getWorkspaceState()]);
    setPost(postResult); setAnswers(answerItems); setWorkspace(workspaceState);
  }, [postId]);

  useEffect(() => {
    let active = true;
    Promise.all([communityService.getPostById(postId), communityService.getAnswers(postId), communityService.getWorkspaceState()])
      .then(([postResult, answerItems, workspaceState]) => { if (active) { setPost(postResult); setAnswers(answerItems); setWorkspace(workspaceState); setLoading(false); } })
      .catch((reason: unknown) => { if (active) { setError(reason instanceof Error ? reason.message : "加载失败"); setLoading(false); } });
    return () => { active = false; };
  }, [postId]);

  useEffect(() => {
    if (!loading && window.location.hash === "#comments") window.setTimeout(() => { document.getElementById("comments")?.scrollIntoView({ behavior: "smooth", block: "start" }); textareaRef.current?.focus(); }, 50);
  }, [loading]);

  function isForkActive(current: CommunityPost) {
    if (current.type === "factor") return workspace.factorPostIds.includes(current.id);
    if (current.type === "strategy_module") return workspace.modulePostIds.includes(current.id);
    if (current.type === "complete_strategy") return workspace.forkedStrategyPostIds.includes(current.id);
    return false;
  }

  async function update(action: () => Promise<unknown>, message: string) {
    try { await action(); setNotice(message); await load(); }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : "操作失败，请稍后重试"); }
  }

  async function toggleFork() {
    if (!post || post.type === "question") return;
    const active = isForkActive(post);
    if (post.type === "factor") return update(() => active ? communityService.removeFactorFromWorkspace(post.id) : communityService.saveFactorToWorkspace(post.id), active ? "已从我的因子移除" : "已添加到我的因子");
    if (post.type === "strategy_module") return update(() => active ? communityService.removeModuleFromWorkspace(post.id) : communityService.saveModuleToWorkspace(post.id), active ? "已从策略模块移除" : "已添加到策略模块");
    return update(() => active ? communityService.removeForkedStrategyFromWorkspace(post.id) : communityService.forkStrategyToWorkspace(post.id), active ? "已移除 Fork 策略" : "已 Fork 到我的策略");
  }

  async function submitAnswer(event: FormEvent) {
    event.preventDefault();
    const clean = answer.trim();
    if (!clean) { setNotice("请输入评论内容"); return; }
    if (clean.length > 1000) { setNotice("评论不能超过 1000 个字符"); return; }
    try { setSubmitting(true); await communityService.addAnswer(postId, clean); setAnswer(""); setNotice(post?.type === "question" ? "回答已发布" : "评论已发布"); await load(); }
    catch (reason) { setNotice(reason instanceof Error ? reason.message : "提交失败"); }
    finally { setSubmitting(false); }
  }

  if (loading) return <p className={styles.state}>正在加载内容…</p>;
  if (error) return <div className={styles.state}><p>{error}</p><button type="button" onClick={() => void load()}>重试</button></div>;
  if (!post) return <p className={styles.state}>未找到该 Community 内容</p>;
  const question = post.type === "question";
  return <div className={styles.page} data-post-id={post.id}>
    <Link className={styles.back} href="/community"><ArrowLeft />返回社区</Link>
    <article className={styles.hero}>
      <div className={styles.heroTop}><div><span className={styles.typeBadge}>{COMMUNITY_TYPE_LABELS[post.type]}</span><h1>{post.title}</h1><p>{post.type === "complete_strategy" ? post.oneLineIntroduction : post.summary}</p></div><button type="button" aria-pressed={post.author.following} onClick={() => void update(() => communityService.toggleFollow(post.author.id), post.author.following ? "已取消关注" : "已关注 Anna Zhang")}><UserPlus />{post.author.following ? "已关注" : "关注"}</button></div>
      <div className={styles.author}><span>AZ</span><strong>Anna Zhang</strong><small>{formatDate(post.createdAt)}</small></div>
      <div className={styles.heroActions}><CommunityActionBar post={post} forkActive={isForkActive(post)} onStar={() => void update(() => communityService.toggleStar(post.id), post.engagement.starred ? "已取消 Star" : "已添加 Star")} onFork={() => void toggleFork()} commentHref="#comments" /></div>
      {notice ? <p className={styles.notice} role="status">{notice}</p> : null}
    </article>
    <DetailBody post={post} />
    <section className={`${styles.section} ${styles.comments}`} id="comments">
      <div className={styles.sectionTitle}><h2>{question ? "回答" : "评论"} <span>{answers.length}</span></h2><p>{question ? "分享你的理解和思路" : "围绕这篇内容展开讨论"}</p></div>
      <form onSubmit={submitAnswer}><textarea ref={textareaRef} aria-label={question ? "回答内容" : "评论内容"} placeholder={question ? "写下你的回答" : "写下你的评论"} value={answer} maxLength={1000} onChange={(event) => setAnswer(event.target.value)} /><div><small>{answer.length}/1000</small><button type="submit" disabled={submitting}>{submitting ? "提交中…" : question ? "提交回答" : "提交评论"}</button></div></form>
      <div className={styles.commentList}>{answers.length ? answers.map((item) => <article key={item.id}><span>AZ</span><div><header><strong>Anna Zhang</strong><small>{formatDate(item.createdAt)}</small></header><p>{item.content}</p></div></article>) : <p className={styles.empty}>{question ? "还没有回答，成为第一个分享观点的人。" : "还没有评论，欢迎开始讨论。"}</p>}</div>
    </section>
  </div>;
}
