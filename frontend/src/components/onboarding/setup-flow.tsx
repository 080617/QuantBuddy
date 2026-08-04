"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CompleteScreen } from "@/components/onboarding/complete-screen";
import { DetailsScreen } from "@/components/onboarding/details-screen";
import { KnowledgeScreen } from "@/components/onboarding/knowledge-screen";
import { STORAGE_KEYS } from "@/lib/constants";
import type { KnowledgeLevel, OnboardingConfig, OnboardingStep } from "@/types/onboarding";

const DEFAULT_CONFIG: OnboardingConfig = {
  knowledgeLevel: null,
  initialCapital: null,
  maxLossPercentage: null,
  investmentPeriod: "medium",
  modelId: null,
  strategyId: "csi300-dynamic-default",
};

function isComplete(config: OnboardingConfig) {
  return (
    config.initialCapital !== null &&
    config.initialCapital > 0 &&
    config.maxLossPercentage !== null &&
    config.maxLossPercentage > 0 &&
    config.maxLossPercentage <= 100 &&
    config.modelId !== null
  );
}

export function SetupFlow({ initialStep }: { initialStep: OnboardingStep }) {
  const router = useRouter();
  const [step, setStep] = useState<OnboardingStep>(initialStep);
  const [config, setConfig] = useState<OnboardingConfig>(DEFAULT_CONFIG);
  const [hasHydrated, setHasHydrated] = useState(false);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      try {
        const storedConfig = window.localStorage.getItem(STORAGE_KEYS.onboardingConfig);
        const restoredConfig = storedConfig
          ? { ...DEFAULT_CONFIG, ...(JSON.parse(storedConfig) as Partial<OnboardingConfig>) }
          : DEFAULT_CONFIG;
        setConfig(restoredConfig);

        if (initialStep === 3 && !isComplete(restoredConfig)) {
          setStep(2);
          window.localStorage.setItem(STORAGE_KEYS.onboardingStep, "2");
          router.replace("/setup?step=2");
        } else {
          setStep(initialStep);
          window.localStorage.setItem(STORAGE_KEYS.onboardingStep, String(initialStep));
        }
      } catch {
        setConfig(DEFAULT_CONFIG);
        if (initialStep === 3) {
          setStep(2);
          router.replace("/setup?step=2");
        }
      }
      setHasHydrated(true);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [initialStep, router]);

  useEffect(() => {
    if (!hasHydrated) return;
    window.localStorage.setItem(
      STORAGE_KEYS.onboardingConfig,
      JSON.stringify(config),
    );
  }, [config, hasHydrated]);

  function updateConfig(patch: Partial<OnboardingConfig>) {
    setConfig((current) => ({ ...current, ...patch }));
  }

  function goToStep(step: OnboardingStep) {
    setStep(step);
    window.localStorage.setItem(STORAGE_KEYS.onboardingStep, String(step));
    router.push(`/setup?step=${step}`, { scroll: false });
  }

  function selectKnowledge(knowledgeLevel: KnowledgeLevel) {
    const nextConfig = { ...config, knowledgeLevel };
    setConfig(nextConfig);
    window.localStorage.setItem(
      STORAGE_KEYS.onboardingConfig,
      JSON.stringify(nextConfig),
    );
    window.setTimeout(() => goToStep(2), 260);
  }

  if (step === 1) {
    return <KnowledgeScreen value={config.knowledgeLevel} onSelect={selectKnowledge} />;
  }

  if (step === 2) {
    return <DetailsScreen config={config} onChange={updateConfig} onNext={() => goToStep(3)} />;
  }

  if (!hasHydrated) {
    return <div className="qb-page" aria-busy="true" />;
  }

  return <CompleteScreen config={config} />;
}
