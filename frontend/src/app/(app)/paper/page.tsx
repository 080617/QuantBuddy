import type { Metadata } from "next";
import { PaperTradingPage } from "@/components/paper/paper-trading-page";

export const metadata: Metadata = { title: "模拟盘" };

export default function PaperPage() {
  return <PaperTradingPage />;
}
