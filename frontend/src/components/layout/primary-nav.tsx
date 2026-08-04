"use client";

import {
  Bot,
  ChartNoAxesCombined,
  ChevronDown,
  Home,
  Menu,
  MessageCircle,
  MonitorUp,
  Settings,
  SlidersHorizontal,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { QuantBuddyLogo } from "@/components/onboarding/onboarding-header";

const APP_NAV_ITEMS = [
  { label: "首页", href: "/", icon: Home },
  { label: "我的策略", href: "/strategy", icon: SlidersHorizontal },
  { label: "回测研究", href: "/backtest", icon: ChartNoAxesCombined },
  { label: "模拟盘", href: "/paper", icon: MonitorUp },
  { label: "社区", href: "/community", icon: MessageCircle },
  { label: "QuantBuddy", href: "/quantbuddy", icon: Bot },
  { label: "设置", href: "/settings", icon: Settings },
] as const;

function isCurrentPath(pathname: string, href: string) {
  return pathname === href || (href !== "/" && pathname.startsWith(`${href}/`));
}

export function PrimaryNav() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const isCommunity = pathname.startsWith("/community");

  return (
    <>
      <button
        type="button"
        className="qb-sidebar-toggle"
        aria-label={isOpen ? "关闭导航" : "打开导航"}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((current) => !current)}
      >
        {isOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
      </button>

      {isOpen ? (
        <button
          type="button"
          className="qb-sidebar-backdrop"
          aria-label="关闭导航"
          onClick={() => setIsOpen(false)}
        />
      ) : null}

      <aside className={`qb-sidebar ${isOpen ? "is-open" : ""}`}>
        <Link href="/" className="qb-sidebar-brand" onClick={() => setIsOpen(false)}>
          <QuantBuddyLogo size="small" priority />
          <span>Quant<span>Buddy</span></span>
        </Link>

        <nav className="qb-sidebar-nav" aria-label="主导航">
          {APP_NAV_ITEMS.map(({ label, href, icon: Icon }) => {
            const active = isCurrentPath(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={active ? "is-active" : ""}
                onClick={() => setIsOpen(false)}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="qb-sidebar-profile">
          <span className="qb-profile-avatar" aria-hidden="true">
            <span />
          </span>
          <span>
            <strong>{isCommunity ? "Anna Zhang" : "小白投资者"}</strong>
            <small>{isCommunity ? "社区成员" : "新手"}</small>
          </span>
          <ChevronDown aria-hidden="true" />
        </div>
      </aside>
    </>
  );
}
