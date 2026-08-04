import { Check } from "lucide-react";

export function CompletionIllustration() {
  return (
    <div className="qb-completion-illustration" aria-hidden="true">
      <span className="qb-confetti qb-confetti-1" />
      <span className="qb-confetti qb-confetti-2" />
      <span className="qb-confetti qb-confetti-3" />
      <span className="qb-confetti qb-confetti-4" />
      <span className="qb-confetti qb-confetti-5" />
      <span className="qb-confetti qb-confetti-6" />
      <div className="qb-check-outer">
        <div className="qb-check-inner">
          <Check strokeWidth={3.4} />
        </div>
      </div>
    </div>
  );
}
