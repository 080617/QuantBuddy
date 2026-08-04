import type { Metadata } from "next";
import { PhasePlaceholder } from "@/components/ui/phase-placeholder";

export const metadata: Metadata = {
  title: "项目说明",
};

export default function AboutPage() {
  return <PhasePlaceholder title="项目说明" />;
}
