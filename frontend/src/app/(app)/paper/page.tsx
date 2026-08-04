import type { Metadata } from "next";
import { AppPlaceholder } from "@/components/ui/app-placeholder";

export const metadata: Metadata = { title: "模拟盘" };

export default function PaperPage() {
  return <AppPlaceholder title="模拟盘" />;
}
