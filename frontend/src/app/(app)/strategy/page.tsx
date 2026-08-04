import type { Metadata } from "next";
import { StrategyBoard } from "@/components/strategy/strategy-board";

export const metadata: Metadata = { title: "我的策略" };
export default async function StrategyPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const { tab } = await searchParams;
  const initialTab = tab === "module" || tab === "factor" ? tab : "complete";
  return <StrategyBoard initialTab={initialTab} />;
}
