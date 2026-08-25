"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  LayoutDashboard,
  TrendingUp,
  Briefcase,
  Users,
  Lightbulb,
  MessageSquare,
  Plug,
  Settings,
  Boxes,
  type LucideIcon,
} from "lucide-react";

interface NavItem {
  href: string;
  icon: LucideIcon;
  labelKey: string;
}

const navItems: NavItem[] = [
  { href: "/", icon: LayoutDashboard, labelKey: "overview" },
  /* Портал один на всех агентов: этот раздел — список того, что
     оплачено, и того, что можно включить. Стоит сразу под обзором,
     потому что остальные пункты имеют смысл только для включённых. */
  { href: "/agents", icon: Boxes, labelKey: "agents" },
  { href: "/marketing", icon: TrendingUp, labelKey: "marketing" },
  { href: "/sales", icon: Briefcase, labelKey: "sales" },
  { href: "/salespeople", icon: Users, labelKey: "salespeople" },
  { href: "/insights", icon: Lightbulb, labelKey: "insights" },
  { href: "/chat", icon: MessageSquare, labelKey: "chat" },
  { href: "/integrations", icon: Plug, labelKey: "integrations" },
  { href: "/settings", icon: Settings, labelKey: "settings" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const t = useTranslations("nav");

  const isActive = (href: string) => {
    if (href === "/") {
      return pathname === "/";
    }
    return pathname.startsWith(href);
  };

  return (
    <aside className="hidden md:flex fixed left-0 top-0 h-screen w-[240px] bg-[hsl(240_5%_96%)] border-r border-[hsl(240_6%_90%)] flex-col">
      {/* Logo / Brand area */}
      <div className="h-14 flex items-center px-4 border-b border-[hsl(240_6%_90%)]">
        <span className="text-base font-semibold text-[hsl(240_10%_4%)]">
          Sofa Belle
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "flex items-center gap-2 rounded-md py-[12px] px-3 text-sm transition-colors",
                active
                  ? "bg-[hsl(221_83%_95%)] text-[#2563EB] font-semibold border-l-[3px] border-[#2563EB]"
                  : "text-[#71717A] hover:bg-[hsl(240_5%_92%)] hover:text-[#09090B]",
              ].join(" ")}
            >
              <Icon size={16} aria-hidden="true" />
              <span>{t(item.labelKey)}</span>
            </Link>
          );
        })}
      </nav>

      {/* Bottom user info area (stub for Phase 1) */}
      <div className="mt-auto p-4 border-t border-[hsl(240_6%_90%)]">
        <p className="text-xs text-[#71717A] truncate">admin@sofabelle.ro</p>
      </div>
    </aside>
  );
}
