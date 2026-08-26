"use client";

/**
 * Первый уровень кабинета — агенты.
 *
 * Заперт не значит спрятан. Клиент, который не видит, что ещё бывает, ничего
 * и не купит; клиент, который видит замок, знает, куда нажать. Поэтому
 * запертые стоят в том же списке, приглушённые, и ведут на свою страницу —
 * там цена и кнопка, а не тупик.
 *
 * Порядок берётся из контракта, тот же, что на витрине: человек не должен
 * пересобирать в голове список, переходя из прайса в кабинет.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { Lock, CreditCard, Settings, LogIn } from "lucide-react";
import { SignOutButton } from "@/components/portal/sign-out-button";
import { ThemeSwitch } from "@/components/portal/theme-switch";
import { isLocked, type NavAgent, type PortalNav } from "@/lib/portal-nav";

export function isCurrent(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * Какие адреса принадлежат какому агенту.
 *
 * Вкладки аналитика живут на собственных адресах — /marketing, /sales и
 * прочих, — а не под /agents/data-analyst: они существовали раньше портала,
 * и переезд сломал бы каждую сохранённую ссылку ради стройности дерева.
 * Соответствие держится здесь, одной таблицей.
 */
const AGENT_PATHS: Record<string, string[]> = {
  "data-analyst": [
    "/marketing",
    "/sales",
    "/salespeople",
    "/insights",
    "/chat",
    "/integrations",
  ],
};

export function agentOwns(agentId: string, pathname: string): boolean {
  const paths = AGENT_PATHS[agentId];
  if (paths) return paths.some((p) => isCurrent(pathname, p));
  return isCurrent(pathname, `/agents/${agentId}`);
}

export function AgentLink({
  agent,
  pathname,
}: {
  agent: NavAgent;
  pathname: string;
}) {
  const t = useTranslations("agents");
  const locked = isLocked(agent.access);
  const active = agentOwns(agent.id, pathname);

  return (
    <Link
      href={agent.href}
      aria-current={active ? "page" : undefined}
      className={[
        "flex items-center gap-2 rounded-control px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 font-medium text-primary"
          : locked
            ? "text-muted-foreground hover:bg-muted"
            : "text-foreground hover:bg-muted",
      ].join(" ")}
    >
      <span className="min-w-0 flex-1 truncate">{t(`names.${agent.id}`)}</span>

      {locked && (
        <Lock size={13} className="shrink-0 opacity-60" aria-hidden="true" />
      )}

      {/* Срок называется в меню, а не только на странице: человек должен
          споткнуться о него по дороге, а не найти, когда уже отключилось. */}
      {agent.access === "expiring" && agent.daysLeft !== null && (
        <span className="shrink-0 rounded-full bg-warn/15 px-1.5 py-0.5 text-[11px] font-medium text-warn tabular-nums">
          {agent.daysLeft}
        </span>
      )}
      {locked && <span className="sr-only">{t(`access.${agent.access}`)}</span>}
    </Link>
  );
}

export function SidebarBody({
  nav,
  onNavigate,
}: {
  nav: PortalNav;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const t = useTranslations("nav");
  const tAgents = useTranslations("agents");

  return (
    <div className="flex h-full flex-col" onClick={onNavigate}>
      <nav className="flex-1 overflow-y-auto p-2">
        <p className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {t("agents")}
        </p>
        <div className="space-y-0.5">
          {nav.agents.map((agent) => (
            <AgentLink key={agent.id} agent={agent} pathname={pathname} />
          ))}
        </div>

        {/* Не вошли — сказать об этом там, где видно, что список короткий. */}
        {!nav.linked && (
          <p className="mt-2 px-3 text-xs leading-relaxed text-muted-foreground">
            {tAgents("signIn.sidebarHint")}
          </p>
        )}
      </nav>

      <div className="space-y-0.5 border-t p-2">
        <SecondaryLink
          href="/subscription"
          icon={CreditCard}
          label={t("subscription")}
          pathname={pathname}
        />
        <SecondaryLink
          href="/settings"
          icon={Settings}
          label={t("settings")}
          pathname={pathname}
        />

        {/* Ниже настроек: это свойство рабочего места, а не раздел кабинета. */}
        <div className="px-2 pt-2">
          <ThemeSwitch />
        </div>
      </div>

      <div className="border-t px-4 py-3">
        {nav.account ? (
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1">
              {nav.account.tenantName && (
                <p className="truncate text-sm font-medium">
                  {nav.account.tenantName}
                </p>
              )}
              <p className="truncate text-xs text-muted-foreground">
                {nav.account.email}
              </p>
            </div>
            <SignOutButton />
          </div>
        ) : (
          <Link
            href="/subscription"
            className="flex items-center gap-2 text-sm text-primary hover:underline"
          >
            <LogIn size={14} aria-hidden="true" />
            {tAgents("signIn.submit")}
          </Link>
        )}
      </div>
    </div>
  );
}

function SecondaryLink({
  href,
  icon: Icon,
  label,
  pathname,
}: {
  href: string;
  icon: typeof Settings;
  label: string;
  pathname: string;
}) {
  const active = isCurrent(pathname, href);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={[
        "flex items-center gap-2 rounded-control px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 font-medium text-primary"
          : "text-muted-foreground hover:bg-muted",
      ].join(" ")}
    >
      <Icon size={15} aria-hidden="true" />
      {label}
    </Link>
  );
}

export default function Sidebar({ nav }: { nav: PortalNav }) {
  return (
    <aside className="fixed left-0 top-0 hidden h-screen w-[248px] flex-col border-r bg-card md:flex">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-base font-semibold tracking-tight">Davoq</span>
      </div>
      <SidebarBody nav={nav} />
    </aside>
  );
}
