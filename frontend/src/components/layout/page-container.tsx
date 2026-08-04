import type { ReactNode } from "react";

interface PageContainerProps {
  children: ReactNode;
  className?: string;
}

export function PageContainer({
  children,
  className = "",
}: PageContainerProps) {
  return (
    <div
      className={`mx-auto w-full max-w-[var(--page-max-width)] px-[var(--page-gutter)] ${className}`}
    >
      {children}
    </div>
  );
}
