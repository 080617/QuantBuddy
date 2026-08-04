import type { ReactNode } from "react";
import { OnboardingContainer } from "@/components/onboarding/onboarding-container";
import { OnboardingHeader } from "@/components/onboarding/onboarding-header";
import { OnboardingProgress } from "@/components/onboarding/onboarding-progress";

interface OnboardingPageProps {
  children: ReactNode;
  showBrand?: boolean;
  progressStep?: 1 | 2;
  pageClassName: string;
}

export function OnboardingPage({
  children,
  showBrand = true,
  progressStep,
  pageClassName,
}: OnboardingPageProps) {
  return (
    <div className="qb-page">
      <OnboardingContainer>
        <OnboardingHeader showBrand={showBrand} />
        {progressStep ? <OnboardingProgress currentStep={progressStep} /> : null}
        <main className={pageClassName}>{children}</main>
      </OnboardingContainer>
    </div>
  );
}
