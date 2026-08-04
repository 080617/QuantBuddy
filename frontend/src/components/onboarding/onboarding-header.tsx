import Image from "next/image";
import Link from "next/link";

export function QuantBuddyLogo({
  size,
  priority = false,
}: {
  size: "small" | "large";
  priority?: boolean;
}) {
  return (
    <span
      className={size === "large" ? "qb-logo-large" : "qb-logo-small"}
      aria-hidden="true"
    >
      <Image
        src="/quantbuddy-logo.png"
        alt=""
        width={1536}
        height={1024}
        priority={priority}
      />
    </span>
  );
}

export function OnboardingHeader({ showBrand = true }: { showBrand?: boolean }) {
  return (
    <header className="qb-header">
      {showBrand ? (
        <Link href="/" className="qb-header-brand" aria-label="QuantBuddy 首页">
          <QuantBuddyLogo size="small" />
          <span>QuantBuddy</span>
        </Link>
      ) : (
        <span aria-hidden="true" />
      )}
      <div className="qb-auth" aria-label="演示身份入口，暂未开放">
        <button type="button" className="qb-login">登录</button>
        <button type="button" className="qb-register">注册</button>
      </div>
    </header>
  );
}
