import {
  ArrowRight,
  Banknote,
  BrainCircuit,
  CalendarDays,
  ChartNoAxesColumnIncreasing,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";
import { CompletionIllustration } from "@/components/onboarding/completion-illustration";
import { OnboardingPage } from "@/components/onboarding/onboarding-page";
import { PERIOD_OPTIONS } from "@/components/onboarding/period-selector";
import { QUANT_MODELS } from "@/mocks/models";
import type { OnboardingConfig } from "@/types/onboarding";

export function CompleteScreen({ config }: { config: OnboardingConfig }) {
  const model = QUANT_MODELS.find((item) => item.id === config.modelId);
  const period = PERIOD_OPTIONS.find(
    (item) => item.value === config.investmentPeriod,
  );

  const rows = [
    {
      label: "初始资金",
      value:
        config.initialCapital === null
          ? "—"
          : `${new Intl.NumberFormat("zh-CN").format(config.initialCapital)} 元`,
      icon: Banknote,
    },
    {
      label: "最大投资损失",
      value:
        config.maxLossPercentage === null
          ? "—"
          : `${config.maxLossPercentage}%`,
      icon: ShieldAlert,
    },
    {
      label: "投资周期",
      value: period?.label ?? "—",
      icon: CalendarDays,
    },
    {
      label: "选择模型",
      value: model?.name ?? "—",
      icon: BrainCircuit,
    },
    {
      label: "策略设置",
      value: "默认策略（动态配置）",
      icon: ChartNoAxesColumnIncreasing,
    },
  ] as const;

  return (
    <OnboardingPage pageClassName="qb-complete">
      <CompletionIllustration />
      <h1>设置完成！</h1>
      <p className="qb-complete-subtitle">你的个性化投资方案已经准备就绪 ✨</p>
      <section className="qb-summary" aria-label="设置摘要">
        <dl>
          {rows.map(({ label, value, icon: Icon }) => (
            <div key={label}>
              <dt><span><Icon aria-hidden="true" /></span>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>
      <Link href="/dashboard" className="qb-primary-button qb-dashboard-button">
        进入我的仪表盘
        <ArrowRight aria-hidden="true" />
      </Link>
      <Link href="/" className="qb-home-link">返回首页</Link>
    </OnboardingPage>
  );
}
