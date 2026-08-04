"use client";

import type { InvestmentPeriod } from "@/types/onboarding";

export const PERIOD_OPTIONS: {
  value: InvestmentPeriod;
  label: string;
}[] = [
  { value: "short", label: "短期（3个月以内）" },
  { value: "medium", label: "中期（3–6个月）" },
  { value: "long", label: "长期（6个月以上）" },
  { value: "very-long", label: "长期（1年以上）" },
];

export function PeriodSelector({
  value,
  onChange,
}: {
  value: InvestmentPeriod;
  onChange(value: InvestmentPeriod): void;
}) {
  return (
    <div className="qb-period-options">
      {PERIOD_OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? "is-selected" : ""}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
