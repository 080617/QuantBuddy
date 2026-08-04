import { WorkspaceCreatePage } from "@/components/strategy/workspace-create-page";
export default async function Page({ searchParams }: { searchParams: Promise<{ id?: string }> }) { const { id } = await searchParams; return <WorkspaceCreatePage kind="factor" editId={id} />; }
