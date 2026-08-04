import type { ReactNode } from "react";

interface NumberedFieldProps {
  number: number;
  label: string;
  children: ReactNode;
  className?: string;
}

export function NumberedField({
  number,
  label,
  children,
  className = "",
}: NumberedFieldProps) {
  return (
    <div className={`qb-numbered-field ${className}`}>
      <div className="qb-question">
        <span>{number}</span>
        <p>{label}</p>
      </div>
      <div className="qb-control">{children}</div>
    </div>
  );
}
