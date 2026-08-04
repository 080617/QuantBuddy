import type { OnboardingStep } from "@/types/onboarding";

interface OnboardingProgressProps {
  currentStep: Exclude<OnboardingStep, 3>;
}

export function OnboardingProgress({
  currentStep,
}: OnboardingProgressProps) {
  return (
    <nav
      aria-label="设置进度"
      className={`qb-progress qb-progress-step-${currentStep}`}
    >
      <ol>
        {[1, 2, 3].map((step, index) => (
          <li key={step}>
            <span
              className={`qb-progress-dot ${
                step === currentStep
                  ? "is-current"
                  : step < currentStep
                    ? "is-complete"
                    : ""
              }`}
              aria-current={step === currentStep ? "step" : undefined}
            >
              <span className="sr-only">第 {step} 步</span>
            </span>
            {index < 2 ? (
              <span className={`qb-progress-line ${step < currentStep ? "is-complete" : ""}`} />
            ) : null}
          </li>
        ))}
      </ol>
    </nav>
  );
}
