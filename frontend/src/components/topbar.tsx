"use client";

/**
 * Верхняя полоса.
 *
 * Заголовка страницы здесь больше нет: у каждого агента он стоит над его
 * вкладками, и второй такой же наверху был бы повтором в одном экране.
 * Полоса делает то, чего не делает никто другой: открывает меню на узком
 * экране и переключает язык.
 *
 * Меню на телефоне — тот же самый список, что слева, а не его копия. Копия
 * уже расходилась: в сайдбаре появился раздел агентов, в телефонном меню
 * его не было.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { SidebarBody } from "@/components/sidebar";
import type { PortalNav } from "@/lib/portal-nav";

export default function Topbar({ nav }: { nav: PortalNav }) {
  const router = useRouter();
  const tLocale = useTranslations("locale");
  const tCommon = useTranslations("common");
  const locale = useLocale();
  const [menuOpen, setMenuOpen] = useState(false);

  const handleLocaleToggle = () => {
    const nextLocale = locale === "ro" ? "en" : "ro";
    // next-intl locale routing: set locale via cookie (localePrefix: "never")
    document.cookie = `NEXT_LOCALE=${nextLocale}; path=/; SameSite=Lax`;
    router.refresh();
  };

  return (
    <>
      <header className="fixed left-0 right-0 top-0 z-10 flex h-14 items-center justify-between border-b bg-card px-4 md:left-[248px] md:px-6">
        <div className="flex items-center gap-2">
          <button
            className="-ml-2 flex size-11 items-center justify-center rounded-control hover:bg-muted md:hidden"
            aria-label={tCommon("openMenu")}
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={22} aria-hidden="true" />
          </button>
          <span className="text-base font-semibold tracking-tight md:hidden">Davoq</span>
        </div>

        <Button variant="ghost" size="sm" onClick={handleLocaleToggle}>
          {tLocale(locale)}
        </Button>
      </header>

      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-[280px] p-0">
          <div className="flex h-14 items-center justify-between border-b px-4">
            <span className="text-base font-semibold tracking-tight">Davoq</span>
            <button
              onClick={() => setMenuOpen(false)}
              aria-label={tCommon("closeMenu")}
              className="flex size-11 items-center justify-center rounded-control hover:bg-muted"
            >
              <X size={20} aria-hidden="true" />
            </button>
          </div>
          <div className="h-[calc(100%-3.5rem)]">
            <SidebarBody nav={nav} onNavigate={() => setMenuOpen(false)} />
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
