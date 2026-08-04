import { WorkspaceCreatePage } from "@/components/strategy/workspace-create-page";
export default async function Page({ searchParams }: { searchParams: Promise<{ id?: string; moduleId?: string; factorId?: string; factorSetId?: string }> }) {
  const { id, moduleId, factorId, factorSetId } = await searchParams;
  return <WorkspaceCreatePage kind="complete" editId={id} preselection={{ moduleId, factorId, factorSetId }} />;
}
