export const PRIMARY_NAV_ITEMS = [
  { label: "模拟投资", href: "/setup" },
  { label: "策略社区", href: "/community" },
  { label: "我的策略", href: "/my-strategies" },
  { label: "关于项目", href: "/about" },
] as const;

export const STORAGE_KEYS = {
  onboardingConfig: "quantbuddy.onboarding.config",
  onboardingStep: "quantbuddy.onboarding.step",
} as const;
