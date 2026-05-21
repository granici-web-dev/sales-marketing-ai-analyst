"use client";

import { usePathname, useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Button } from "@/components/ui/button";

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
  const locale = useLocale();

  const titleKey = getPageTitleKey(pathname);
  const pageTitle = t(titleKey);

  const handleLocaleToggle = () => {
    const nextLocale = locale === "ro" ? "en" : "ro";
    // next-intl locale routing: set locale via cookie (localePrefix: "never")
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; SameSite=Lax`;
    router.refresh();
  };

  return (
    <header className="fixed top-0 left-[240px] right-0 h-14 bg-[hsl(240_5%_96%)] border-b border-[hsl(240_6%_90%)] flex items-center justify-between px-6 z-10">
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
  );
}
