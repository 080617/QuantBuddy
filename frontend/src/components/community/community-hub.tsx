"use client";

import { Plus, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CommunityPostCard } from "@/components/community/community-post-cards";
import { COMMUNITY_FILTERS, COMMUNITY_SORTS } from "@/lib/community-constants";
import { communityService } from "@/services/community-service";
import type { CommunityFilterValue, CommunityPost, CommunitySortValue, CommunityWorkspaceState } from "@/types/community";
import styles from "./community-main.module.css";

const PUBLISH_CHOICES = [
  ["发布因子", "/community/publish/factor"],
  ["发布策略模块", "/community/publish/module"],
  ["发布完整策略", "/community/publish/strategy"],
  ["发布提问", "/community/publish/question"],
] as const;

function postFilters(filter: CommunityFilterValue, sort: CommunitySortValue) {
  const postTypes: CommunityPost["type"][] = ["factor", "strategy_module", "complete_strategy", "question"];
  return {
    type: postTypes.includes(filter as CommunityPost["type"]) ? filter as CommunityPost["type"] : undefined,
    followingOnly: filter === "following",
    sort,
  };
}

export function CommunityHub() {
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [hotPosts, setHotPosts] = useState<CommunityPost[]>([]);
  const [filter, setFilter] = useState<CommunityFilterValue>("recommended");
  const [sort, setSort] = useState<CommunitySortValue>("weekly_popular");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [workspace, setWorkspace] = useState<CommunityWorkspaceState>({ factorPostIds: [], modulePostIds: [], forkedStrategyPostIds: [] });

  const load = useCallback(async () => {
    const [visiblePosts, popularPosts, workspaceState] = await Promise.all([
      communityService.getPosts(postFilters(filter, sort)),
      communityService.getPosts({ sort: "weekly_popular" }),
      communityService.getWorkspaceState(),
    ]);
    setPosts(visiblePosts);
    setHotPosts(popularPosts.slice(0, 3));
    setWorkspace(workspaceState);
  }, [filter, sort]);

  useEffect(() => {
    let active = true;
    Promise.all([
      communityService.getPosts(postFilters(filter, sort)),
      communityService.getPosts({ sort: "weekly_popular" }),
      communityService.getWorkspaceState(),
    ]).then(([visiblePosts, popularPosts, workspaceState]) => {
      if (!active) return;
      setPosts(visiblePosts);
      setHotPosts(popularPosts.slice(0, 3));
      setWorkspace(workspaceState);
      setError("");
      setLoading(false);
    }).catch((reason: unknown) => {
      if (!active) return;
      setError(reason instanceof Error ? reason.message : "社区内容加载失败");
      setLoading(false);
    });
    return () => { active = false; };
  }, [filter, sort]);

  async function runAction(action: () => Promise<unknown>, success: string) {
    try {
      await action();
      setToast(success);
      await load();
      window.setTimeout(() => setToast(""), 2600);
    } catch (reason) {
      setToast(reason instanceof Error ? reason.message : "操作失败，请稍后重试");
    }
  }

  function forkActive(post: CommunityPost) {
    if (post.type === "factor") return workspace.factorPostIds.includes(post.id);
    if (post.type === "strategy_module") return workspace.modulePostIds.includes(post.id);
    if (post.type === "complete_strategy") return workspace.forkedStrategyPostIds.includes(post.id);
    return false;
  }

  async function toggleFork(post: CommunityPost) {
    const active = forkActive(post);
    if (post.type === "factor") return runAction(
      () => active ? communityService.removeFactorFromWorkspace(post.id) : communityService.saveFactorToWorkspace(post.id),
      active ? "已从我的因子移除" : "已添加到我的因子",
    );
    if (post.type === "strategy_module") return runAction(
      () => active ? communityService.removeModuleFromWorkspace(post.id) : communityService.saveModuleToWorkspace(post.id),
      active ? "已从策略模块移除" : "已添加到策略模块",
    );
    if (post.type === "complete_strategy") return runAction(
      () => active ? communityService.removeForkedStrategyFromWorkspace(post.id) : communityService.forkStrategyToWorkspace(post.id),
      active ? "已移除 Fork 策略" : "已 Fork 到我的策略，保存为待重新回测的草稿",
    );
  }

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div>
          <h1>社区</h1>
          <p>发现、讨论并共同改进量化因子、策略与想法</p>
        </div>
        <button className={styles.publishButton} type="button" onClick={() => setModalOpen(true)}>
          <Plus aria-hidden="true" />发布
        </button>
      </header>

      <div className={styles.toolbar}>
        <div className={styles.filters} aria-label="社区内容筛选">
          {COMMUNITY_FILTERS.map((item) => (
            <button key={item.value} type="button" className={filter === item.value ? styles.activeFilter : ""} onClick={() => { setLoading(true); setFilter(item.value); }}>
              {item.label}
            </button>
          ))}
        </div>
        <label className={styles.sortControl}>
          <span className={styles.srOnly}>社区内容排序</span>
          <select value={sort} onChange={(event) => { setLoading(true); setSort(event.target.value as CommunitySortValue); }}>
            {COMMUNITY_SORTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
      </div>

      <div className={styles.layout}>
        <main className={styles.feed}>
          {loading ? <div className={styles.stateCard}>正在加载社区内容…</div> : null}
          {!loading && error ? <div className={styles.stateCard}><p>{error}</p><button type="button" onClick={() => void load()}>重新加载</button></div> : null}
          {!loading && !error && posts.length === 0 ? <div className={styles.stateCard}>暂无符合条件的内容</div> : null}
          {!loading && !error ? posts.map((post) => (
            <CommunityPostCard
              key={post.id}
              post={post}
              forkActive={forkActive(post)}
              onFollow={() => runAction(() => communityService.toggleFollow(post.author.id), post.author.following ? "已取消关注 Anna Zhang" : "已关注 Anna Zhang")}
              onStar={() => runAction(() => communityService.toggleStar(post.id), post.engagement.starred ? "已取消 Star" : "已添加 Star")}
              onFork={() => void toggleFork(post)}
            />
          )) : null}
        </main>

        <aside className={styles.rightSidebar} aria-label="社区辅助信息">
          <section className={styles.sideCard}>
            <header><h2>热门内容</h2><span>按互动热度</span></header>
            <div className={styles.hotList}>
              {hotPosts.map((post, index) => (
                <Link key={post.id} href={`/community/${post.id}`}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <span><strong>{post.title}</strong><small>Star {post.engagement.starCount} · 互动 {post.engagement.answerCount + (post.engagement.forkCount ?? 0) + (post.engagement.useCount ?? 0)}</small></span>
                </Link>
              ))}
            </div>
          </section>

          <section className={styles.sideCard}>
            <header><h2>社区贡献者</h2></header>
            <div className={styles.contributor}>
              <span className={styles.avatar} aria-hidden="true">AZ</span>
              <span><strong>Anna Zhang</strong><small>QuantBuddy 社区作者</small></span>
              <button type="button" onClick={() => void runAction(() => communityService.toggleFollow("author-anna-zhang"), posts[0]?.author.following ? "已取消关注 Anna Zhang" : "已关注 Anna Zhang")}>{posts[0]?.author.following ? "已关注" : "关注"}</button>
            </div>
            <p className={styles.contributorHint}>更多贡献者加入后将在这里展示</p>
          </section>

          <section className={`${styles.sideCard} ${styles.aboutCard}`}>
            <span><Sparkles aria-hidden="true" /></span>
            <h2>社区说明</h2>
            <p>社区内容用于量化学习、交流与共同改进。</p>
            <strong>历史回测结果不代表未来收益。</strong>
          </section>
        </aside>
      </div>

      {toast ? <div className={styles.toast} role="status">{toast}</div> : null}
      {modalOpen ? (
        <div className={styles.modalBackdrop} role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setModalOpen(false); }}>
          <section className={styles.modal} role="dialog" aria-modal="true" aria-labelledby="publish-title">
            <header><div><small>QUANTBUDDY COMMUNITY</small><h2 id="publish-title">选择发布类型</h2><p>分享你的量化想法，与社区共同改进。</p></div><button type="button" aria-label="关闭发布类型选择" onClick={() => setModalOpen(false)}><X aria-hidden="true" /></button></header>
            <div>{PUBLISH_CHOICES.map(([label, href]) => <Link key={href} href={href}>{label}<span>→</span></Link>)}</div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
