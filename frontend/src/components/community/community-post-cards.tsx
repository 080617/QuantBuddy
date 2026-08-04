"use client";

import { ChartNoAxesCombined, CircleHelp, ShieldCheck, Sparkles, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import type { KeyboardEvent, MouseEvent, ReactNode } from "react";
import { COMMUNITY_TYPE_LABELS, STRATEGY_MODULE_TYPE_LABELS } from "@/lib/community-constants";
import type { CommunityPost } from "@/types/community";
import { CommunityActionBar } from "./community-action-bar";
import styles from "./community-main.module.css";

interface CardProps {
  post: CommunityPost;
  forkActive: boolean;
  onFollow: () => void;
  onStar: () => void;
  onFork: () => void;
}

const TYPE_ICONS: Record<CommunityPost["type"], ReactNode> = {
  complete_strategy: <ChartNoAxesCombined />,
  factor: <Sparkles />,
  strategy_module: <ShieldCheck />,
  question: <CircleHelp />,
};

function stopAndRun(event: MouseEvent<HTMLButtonElement>, action: () => void) {
  event.stopPropagation();
  action();
}

function Summary({ post }: { post: CommunityPost }) {
  if (post.type === "complete_strategy") {
    const config = post.configurationSnapshot;
    return <div className={styles.metadataGrid}>
      <span><small>模型</small><strong>{config.model ?? "--"}</strong></span>
      <span><small>因子 / 特征集</small><strong>{config.featureSet?.name ?? "--"}</strong></span>
      <span><small>股票池</small><strong>{config.universe}</strong></span>
      <span><small>组合规则</small><strong>{config.stockSelectionModule ?? "--"}</strong></span>
    </div>;
  }
  if (post.type === "factor") return <div className={styles.metadataGrid}><span><small>因子类型</small><strong>{post.factorType}</strong></span><span className={styles.wideMeta}><small>公式</small><code>{post.expression}</code></span></div>;
  if (post.type === "strategy_module") return <div className={styles.metadataGrid}><span><small>模块类型</small><strong>{STRATEGY_MODULE_TYPE_LABELS[post.moduleType]}</strong></span><span className={styles.wideMeta}><small>规则摘要</small><strong>{post.ruleSummary}</strong></span></div>;
  return <div className={styles.questionBody}><p>{post.content}</p><div className={styles.tagList}>{post.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></div>;
}

export function CommunityPostCard({ post, forkActive, onFollow, onStar, onFork }: CardProps) {
  const router = useRouter();
  const href = `/community/${post.id}`;
  function openDetail() { router.push(href); }
  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDetail(); }
  }
  return (
    <article className={styles.postCard} data-post-id={post.id} role="link" tabIndex={0} onClick={openDetail} onKeyDown={onKeyDown}>
      <div className={styles.cardHeader}>
        <span className={`${styles.typeIcon} ${styles[post.type]}`}>{TYPE_ICONS[post.type]}</span>
        <div className={styles.cardTitle}>
          <span className={styles.typeBadge}>{COMMUNITY_TYPE_LABELS[post.type]}</span>
          <h2>{post.title}</h2>
          <p>{post.type === "complete_strategy" ? post.oneLineIntroduction : post.summary}</p>
        </div>
        <div className={styles.authorRow}>
          <span className={styles.avatar} aria-hidden="true">AZ</span>
          <span><strong>Anna Zhang</strong><small>{new Date(post.createdAt).toLocaleDateString("zh-CN", { month: "long", day: "numeric" })}</small></span>
          <button type="button" aria-pressed={post.author.following} onClick={(event) => stopAndRun(event, onFollow)}><UserPlus aria-hidden="true" />{post.author.following ? "已关注" : "关注"}</button>
        </div>
      </div>
      <Summary post={post} />
      <footer className={styles.cardFooter}>
        <CommunityActionBar post={post} forkActive={forkActive} onStar={onStar} onFork={onFork} />
      </footer>
    </article>
  );
}
