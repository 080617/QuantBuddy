import {
  ArrowRight,
  ChartNoAxesCombined,
  GraduationCap,
  Sparkles,
  UsersRound,
  Zap,
} from "lucide-react";
import Link from "next/link";
import { OnboardingPage } from "@/components/onboarding/onboarding-page";
import { QuantBuddyLogo } from "@/components/onboarding/onboarding-header";

const FEATURES = [
  { title: "零基础友好", description: "从入门到进阶", icon: GraduationCap },
  { title: "策略回测", description: "验证你的想法", icon: ChartNoAxesCombined },
  { title: "社区共创", description: "分享与学习", icon: UsersRound },
  { title: "持续进化", description: "AI 助力成长", icon: Zap },
] as const;

export function WelcomeScreen() {
  return (
    <OnboardingPage showBrand={false} pageClassName="qb-welcome">
      <span className="qb-decoration qb-dot-left" aria-hidden="true" />
      <span className="qb-decoration qb-dot-top" aria-hidden="true" />
      <span className="qb-decoration qb-diamond" aria-hidden="true" />

      <section className="qb-welcome-center">
        <QuantBuddyLogo size="large" priority />
        <h1>
          Quant<span>Buddy</span>
        </h1>
        <p>
          你的量化理财学习伙伴
          <Sparkles aria-hidden="true" size={19} />
        </p>
        <Link href="/setup?step=1" className="qb-primary-button">
          开始你的量化之旅
          <ArrowRight aria-hidden="true" />
        </Link>
      </section>

      <svg className="qb-wave" viewBox="0 0 1440 185" preserveAspectRatio="none" aria-hidden="true">
        <path d="M-30 15C110 25 145 140 300 141h612c151 0 224-139 558-116" />
      </svg>

      <section className="qb-features" aria-label="产品特点">
        {FEATURES.map(({ title, description, icon: Icon }) => (
          <div className="qb-feature" key={title}>
            <Icon aria-hidden="true" />
            <div>
              <h2>{title}</h2>
              <p>{description}</p>
            </div>
          </div>
        ))}
      </section>
    </OnboardingPage>
  );
}
