import { CommunityPublishForm } from "@/components/community/community-publish-form";

export default async function PublishStrategyPage({ searchParams }: { searchParams: Promise<{ strategyId?: string; draftId?: string }> }) {
  const { strategyId, draftId } = await searchParams;
  return <CommunityPublishForm kind="strategy" strategyId={strategyId} draftQueryId={draftId} />;
}
