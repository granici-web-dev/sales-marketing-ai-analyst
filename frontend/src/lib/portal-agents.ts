/**
 * Состояние агентов в портале.
 *
 * Портал один на всех агентов: разделы оплаченных открыты, остальные заперты
 * и предлагают оплату. Ответ на вопрос «что оплачено» даёт движок —
 * `GET /admin/api/agents`, модуль `billing/agents.ts`. Здесь этот ответ
 * только дополняется тем, чего движок знать не может: куда ведёт открытый
 * раздел в ЭТОМ приложении.
 */
import { engineGet, type EngineResult } from "@/lib/engine";

export type AgentAccess = "unlocked" | "expiring" | "locked" | "unavailable";

/** То, что отдаёт движок. Форма повторяет `PortalAgent` из billing/agents.ts. */
interface EngineAgent {
  id: string;
  access: AgentAccess;
  tier: "basic" | "pro" | null;
  /** Цена, с которой открывается агент. null — ещё не продаётся. */
  priceFrom: number | null;
  /** Дней до конца оплаченного периода. null — бессрочно либо не куплен. */
  daysLeft: number | null;
}

export interface PortalAgent extends EngineAgent {
  /** Куда ведёт открытый раздел. null — вести некуда, раздел ещё не перенесён. */
  href: string | null;
}

/**
 * Чьи экраны уже живут в этом приложении.
 *
 * Пусто не случайно: сегодня здесь только аналитик, а он не запущен и
 * приходит от движка недоступным. Остальные шестеро управляются в кабинете
 * движка, и ссылка туда была бы ссылкой в другое приложение — про это
 * страница говорит словами, а не кнопкой, которая никуда не ведёт.
 */
const SCREENS: Record<string, string> = {
  "data-analyst": "/insights",
};

export async function fetchPortalAgents(): Promise<EngineResult<PortalAgent[]>> {
  const result = await engineGet<{ agents: EngineAgent[] }>("/admin/api/agents");
  if (!result.ok) return result;

  return {
    ok: true,
    data: result.data.agents.map((agent) => ({
      ...agent,
      href: SCREENS[agent.id] ?? null,
    })),
  };
}
