import type { Metadata } from "next";
import { AppPlaceholder } from "@/components/ui/app-placeholder";

export const metadata: Metadata = { title: "首页" };

export default function HomePage() {
  return <AppPlaceholder title="首页" />;
}
