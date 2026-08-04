import type { Metadata } from "next";
import { AppPlaceholder } from "@/components/ui/app-placeholder";

export const metadata: Metadata = { title: "设置" };

export default function SettingsPage() {
  return <AppPlaceholder title="设置" />;
}
