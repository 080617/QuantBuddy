import { CommunityPublishForm } from "@/components/community/community-publish-form";
export default async function PublishQuestionPage({ searchParams }: { searchParams: Promise<{ draftId?: string }> }) {
  const { draftId } = await searchParams;
  return <CommunityPublishForm kind="question" draftQueryId={draftId} />;
}
