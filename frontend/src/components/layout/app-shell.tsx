import type { ReactNode } from "react";
import { PrimaryNav } from "@/components/layout/primary-nav";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="qb-app-shell">
      <PrimaryNav />
      <main className="qb-app-main">{children}</main>
    </div>
  );
}
