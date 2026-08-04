import type { LucideIcon } from "lucide-react";

export function MetricCard({
  label,
  value,
  tone,
  icon: Icon,
}: {
  label: string;
  value: string;
  tone: "purple" | "green" | "orange" | "red";
  icon: LucideIcon;
}) {
  return (
    <article className="qb-performance-card">
      <span className={`qb-performance-icon is-${tone}`}><Icon aria-hidden="true" /></span>
      <span><small>{label}</small><strong className={`is-${tone}`}>{value}</strong></span>
    </article>
  );
}
