"use client";

import { GitFork, MessageCircle, Star } from "lucide-react";
import Link from "next/link";
import type { MouseEvent } from "react";
import type { CommunityPost } from "@/types/community";
import styles from "./community-main.module.css";

interface CommunityActionBarProps {
  post: CommunityPost;
  forkActive: boolean;
  onStar: () => void;
  onFork?: () => void;
  commentHref?: string;
}

function stop(event: MouseEvent<HTMLElement>) {
  event.stopPropagation();
}

export function CommunityActionBar({ post, forkActive, onStar, onFork, commentHref = `/community/${post.id}#comments` }: CommunityActionBarProps) {
  const forkCount = post.type === "complete_strategy" ? post.engagement.forkCount : post.engagement.useCount;
  return (
    <div className={styles.footerActions} onClick={stop}>
      <button type="button" className={post.engagement.starred ? styles.activeAction : ""} aria-pressed={post.engagement.starred} onClick={onStar}>
        <Star aria-hidden="true" fill={post.engagement.starred ? "currentColor" : "none"} />
        <span>Star</span><strong>{post.engagement.starCount}</strong>
      </button>
      <Link href={commentHref} aria-label={`查看 ${post.title} 的评论`}>
        <MessageCircle aria-hidden="true" /><span>Comment</span><strong>{post.engagement.answerCount}</strong>
      </Link>
      {post.type !== "question" ? (
        <button type="button" className={forkActive ? styles.activeAction : ""} aria-pressed={forkActive} onClick={onFork}>
          <GitFork aria-hidden="true" fill={forkActive ? "currentColor" : "none"} />
          <span>Fork</span><strong>{forkCount ?? 0}</strong>
        </button>
      ) : null}
    </div>
  );
}
