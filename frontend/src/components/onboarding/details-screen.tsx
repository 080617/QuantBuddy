"use client";

import { useState } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import type { OnboardingConfig } from "@/types/onboarding";
import { ModelSelect } from "@/components/onboarding/model-select";
import { NumberedField } from "@/components/onboarding/numbered-field";
import { OnboardingPage } from "@/components/onboarding/onboarding-page";
import { PeriodSelector } from "@/components/onboarding/period-selector";

interface DetailsScreenProps {
  config: OnboardingConfig;
  onChange(patch: Partial<OnboardingConfig>): void;
  onNext(): void;
}

function parseNumber(value: string) {
  return value === "" ? null : Number(value);
}

export function DetailsScreen({
  config,
  onChange,
  onNext,
}: DetailsScreenProps) {
  const [maxLossInput, setMaxLossInput] = useState(
    config.maxLossPercentage?.toString() ?? "",
  );

  function handleMaxLossChange(value: string) {
    const normalizedValue = value.replace(",", ".");

    if (!/^\d{0,3}(?:\.\d{0,2})?$/.test(normalizedValue)) {
      return;
    }

    setMaxLossInput(normalizedValue);
    onChange({
      maxLossPercentage:
        normalizedValue === "" ? null : Number(normalizedValue),
    });
  }

  const canContinue =
    config.initialCapital !== null &&
    config.initialCapital > 0 &&
    config.maxLossPercentage !== null &&
    config.maxLossPercentage > 0 &&
    config.maxLossPercentage <= 100 &&
    config.modelId !== null;

  return (
    <OnboardingPage progressStep={2} pageClassName="qb-details">
      <section className="qb-details-intro">
        <h1>补充信息</h1>
        <p>为了生成更适合你的投资方案，<br />请完成以下信息填写</p>
        <div className="qb-chart-decoration" aria-hidden="true">
          <svg viewBox="0 0 150 100">
            <path d="M12 82c16-20 24-21 36-7 13 15 22 13 32-7 11-24 22-28 31-10 10 18 16 4 25-19" />
            <path className="axis" d="M5 10v80h138" />
          </svg>
          <span style={{ height: "34px" }} />
          <span style={{ height: "67px" }} />
          <span style={{ height: "48px" }} />
        </div>
      </section>

      <form
        className="qb-details-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (canContinue) onNext();
        }}
      >
        <NumberedField number={1} label="你的初始资金是多少？">
          <input
            type="number"
            min="1"
            inputMode="decimal"
            value={config.initialCapital ?? ""}
            onChange={(event) => onChange({ initialCapital: parseNumber(event.target.value) })}
            placeholder="请输入金额（元）"
            aria-label="初始资金"
          />
        </NumberedField>

        <NumberedField number={2} label="你能承受的风险（最大投资损失）是多少？">
          <div className="qb-percent-input">
            <input
              type="text"
              inputMode="decimal"
              value={maxLossInput}
              onChange={(event) => handleMaxLossChange(event.target.value)}
              placeholder="请输入百分比（如 20 表示 20%）"
              aria-label="最大投资损失百分比"
            />
            <span>%</span>
          </div>
        </NumberedField>

        <NumberedField number={3} label="你的投资周期是多长？" className="qb-period-field">
          <PeriodSelector
            value={config.investmentPeriod}
            onChange={(investmentPeriod) => onChange({ investmentPeriod })}
          />
        </NumberedField>

        <NumberedField number={4} label="你选择什么模型？">
          <ModelSelect
            value={config.modelId}
            onChange={(modelId) => onChange({ modelId })}
          />
        </NumberedField>

        <NumberedField number={5} label="你选择什么策略？">
          <div className="qb-locked-input">
            <span>默认策略（基于模型由系统动态配置）</span>
            <LockKeyhole aria-hidden="true" />
          </div>
        </NumberedField>

        <button type="submit" className="qb-next-button" disabled={!canContinue}>
          下一步
          <ArrowRight aria-hidden="true" />
        </button>
      </form>
    </OnboardingPage>
  );
}
