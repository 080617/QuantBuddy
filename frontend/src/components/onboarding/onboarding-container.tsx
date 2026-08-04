import type { ReactNode } from "react";

export function OnboardingContainer({ children }: { children: ReactNode }) {
  return <div className="qb-container">{children}</div>;
}
