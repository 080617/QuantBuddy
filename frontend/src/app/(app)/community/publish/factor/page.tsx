import { CommunityPublishForm } from "@/components/community/community-publish-form";
export default async function PublishFactorPage({ searchParams }: { searchParams: Promise<{ workspaceId?: string; draftId?: string }> }) {
  const { workspaceId, draftId } = await searchParams;
  return <CommunityPublishForm kind="factor" workspaceId={workspaceId} draftQueryId={draftId} />;
}
