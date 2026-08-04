import { CommunityPublishForm } from "@/components/community/community-publish-form";
export default async function PublishModulePage({ searchParams }: { searchParams: Promise<{ workspaceId?: string; draftId?: string }> }) {
  const { workspaceId, draftId } = await searchParams;
  return <CommunityPublishForm kind="module" workspaceId={workspaceId} draftQueryId={draftId} />;
}
