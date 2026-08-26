import { Providers } from "@/components/providers";
import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";
import { loadPortalNav } from "@/lib/portal-nav.server";

/**
 * Оболочка портала.
 *
 * Серверная намеренно: слева стоят агенты клиента, а знает о них движок.
 * Рисовать их у клиента значило бы отдать список пустым и дорисовать после
 * загрузки — то есть показать кабинет без агентов тому, у кого они есть.
 */
export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const nav = await loadPortalNav();

  return (
    <Providers>
      <div className="min-h-screen">
        <Sidebar nav={nav} />
        <Topbar nav={nav} />
        <main className="ml-0 md:ml-[248px] mt-14 min-h-[calc(100vh-56px)] p-4 md:p-8">
          {children}
        </main>
      </div>
    </Providers>
  );
}
