export type KnowledgeLevel = "beginner" | "advanced";

export type InvestmentPeriod = "short" | "medium" | "long" | "very-long";

export interface OnboardingConfig {
  knowledgeLevel: KnowledgeLevel | null;
  initialCapital: number | null;
  maxLossPercentage: number | null;
  investmentPeriod: InvestmentPeriod;
  modelId: string | null;
  strategyId: "csi300-dynamic-default";
}

export type OnboardingStep = 1 | 2 | 3;

export interface OnboardingState {
  step: OnboardingStep;
  config: OnboardingConfig;
}
