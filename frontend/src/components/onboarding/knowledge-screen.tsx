"use client";

import { ChartNoAxesCombined, Sprout } from "lucide-react";
import type { KnowledgeLevel } from "@/types/onboarding";
import { OnboardingPage } from "@/components/onboarding/onboarding-page";

interface KnowledgeScreenProps {
  value: KnowledgeLevel | null;
  onSelect(value: KnowledgeLevel): void;
}

export function KnowledgeScreen({ value, onSelect }: KnowledgeScreenProps) {
  return (
    <OnboardingPage progressStep={1} pageClassName="qb-knowledge">
      <header className="qb-screen-heading">
        <h1>你对金融了解多少？</h1>
        <p>选择你的起点，我们将为你提供更合适的学习体验 ✨</p>
      </header>
      <div className="qb-level-grid">
        <button
          type="button"
          className={`qb-level-card qb-level-beginner ${value === "beginner" ? "is-selected" : ""}`}
          onClick={() => onSelect("beginner")}
          aria-pressed={value === "beginner"}
        >
          <Sprout className="qb-level-icon" aria-hidden="true" />
          <h2>新手入门</h2>
          <span>零基础也没关系</span>
          <p>从基础开始学习量化投资<br />我们一步步带你上手</p>
        </button>
        <button
          type="button"
          className={`qb-level-card qb-level-advanced ${value === "advanced" ? "is-selected" : ""}`}
          onClick={() => onSelect("advanced")}
          aria-pressed={value === "advanced"}
        >
          <ChartNoAxesCombined className="qb-level-icon" aria-hidden="true" />
          <h2>进阶探索</h2>
          <span>已有一定基础</span>
          <p>深入学习量化策略与模型<br />探索更多可能性</p>
        </button>
      </div>
    </OnboardingPage>
  );
}
