"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import {
  LayoutDashboard,
  TrendingUp,
  Briefcase,
  Users,
  Lightbulb,
  MessageSquare,
  Plug,
  Settings,
  Menu,
  X,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";

// Nav items duplicated from sidebar.tsx for the mobile Sheet overlay
interface NavItem {
  href: string;
  icon: LucideIcon;
  labelKey: string;
}

const navItems: NavItem[] = [
  { href: "/", icon: LayoutDashboard, labelKey: "overview" },
  { href: "/marketing", icon: TrendingUp, labelKey: "marketing" },
  { href: "/sales", icon: Briefcase, labelKey: "sales" },
  { href: "/salespeople", icon: Users, labelKey: "salespeople" },
  { href: "/insights", icon: Lightbulb, labelKey: "insights" },
  { href: "/chat", icon: MessageSquare, labelKey: "chat" },
  { href: "/integrations", icon: Plug, labelKey: "integrations" },
  { href: "/settings", icon: Settings, labelKey: "settings" },
];

// Map pathname to nav translation key
function getPageTitleKey(pathname: string): string {
  if (pathname === "/") return "overview";
  if (pathname.startsWith("/marketing")) return "marketing";
  if (pathname.startsWith("/sales")) return "sales";
  if (pathname.startsWith("/salespeople")) return "salespeople";
  if (pathname.startsWith("/insights")) return "insights";
  if (pathname.startsWith("/chat")) return "chat";
  if (pathname.startsWith("/integrations")) return "integrations";
  if (pathname.startsWith("/settings")) return "settings";
  return "overview";
}

export default function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const t = useTranslations("nav");
  const tLocale = useTranslations("locale");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const titleKey = getPageTitleKey(pathname);
  const pageTitle = t(titleKey);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const handleLocaleToggle = () => {
    const nextLocale = locale === "ro" ? "en" : "ro";
    // next-intl locale routing: set locale via cookie (localePrefix: "never")
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; SameSite=Lax`;
    router.refresh();
  };

  return (
    <>
      <header className="fixed top-0 left-0 md:left-[240px] right-0 h-14 bg-[hsl(240_5%_96%)] border-b border-[hsl(240_6%_90%)] flex items-center justify-between px-6 z-10">
        {/* Hamburger button — mobile only */}
        <button
          className="md:hidden mr-3 min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md hover:bg-[hsl(240_5%_92%)]"
          aria-label={tCommon("openMenu")}
          onClick={() => setMobileMenuOpen(true)}
        >
          <Menu size={24} aria-hidden="true" />
        </button>

        <span className="text-xl font-semibold text-[hsl(240_10%_4%)]">
          {pageTitle}
        </span>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleLocaleToggle}
          className="text-[#71717A] hover:text-[#09090B]"
        >
          {tLocale(locale)}
        </Button>
      </header>

      {/* Mobile navigation Sheet overlay */}
      <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <SheetContent side="left" className="w-[280px] p-0">
          {/* Header with logo and close button */}
          <div className="h-14 flex items-center justify-between px-4 border-b border-[hsl(240_6%_90%)]">
            <span className="text-base font-semibold text-[hsl(240_10%_4%)]">
              Sofa Belle
            </span>
            <button
              onClick={() => setMobileMenuOpen(false)}
              aria-label={tCommon("closeMenu")}
              className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-md hover:bg-[hsl(240_5%_92%)]"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>

          {/* Navigation items */}
          <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
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

          {/* Bottom user info */}
          <div className="mt-auto p-4 border-t border-[hsl(240_6%_90%)]">
            <p className="text-xs text-[#71717A] truncate">admin@sofabelle.ro</p>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
