import type { Metadata } from "next";
import { SetupFlow } from "@/components/onboarding/setup-flow";

export const metadata: Metadata = {
  title: "个性化设置",
};

interface SetupPageProps {
  searchParams: Promise<{ step?: string | string[] }>;
}

export default async function SetupPage({ searchParams }: SetupPageProps) {
  const query = await searchParams;
  const rawStep = Array.isArray(query.step) ? query.step[0] : query.step;
  const initialStep = rawStep === "2" || rawStep === "3" ? rawStep : "1";

  return <SetupFlow initialStep={Number(initialStep) as 1 | 2 | 3} />;
}
