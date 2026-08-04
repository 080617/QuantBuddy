import type { Metadata } from "next";
import { CommunityPostDetail } from "@/components/community/community-post-detail";

export const metadata: Metadata = { title: "Community 内容" };
export default async function CommunityPostPage({ params }: { params: Promise<{ postId: string }> }) { const { postId } = await params; return <CommunityPostDetail postId={postId} />; }
