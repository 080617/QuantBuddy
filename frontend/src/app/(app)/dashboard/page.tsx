import type { Metadata } from "next";
import { PhasePlaceholder } from "@/components/ui/phase-placeholder";

export const metadata: Metadata = {
  title: "结果 Dashboard",
};

export default function DashboardPage() {
  return <PhasePlaceholder title="结果 Dashboard" />;
}
