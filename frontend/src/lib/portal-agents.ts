/**
 * Состояние агентов в портале.
 *
 * Портал один на всех агентов: разделы оплаченных открыты, остальные заперты
 * и предлагают оплату. Ответ на вопрос «что оплачено» даёт движок —
 * `GET /admin/api/agents`, модуль `billing/agents.ts`.
 *
 * Адреса разделов сюда не примешиваются: куда ведёт агент внутри кабинета —
 * вопрос навигации, и на него отвечает `portal-nav.ts`. Один ответ на один
 * вопрос, иначе адрес раздела оказался бы в двух местах сразу.
 */
import { engineGet, type EngineResult } from "@/lib/engine";

export type AgentAccess = "unlocked" | "expiring" | "locked" | "unavailable";

/** Чем агент включается: самый дешёвый покупаемый тариф, куда он входит. */
export interface UnlockPlan {
  id: string;
  name: string;
  priceEur: number;
  priceEurYearly: number;
}

/** То, что отдаёт движок. Форма повторяет `PortalAgent` из billing/agents.ts. */
interface EngineAgent {
  id: string;
  access: AgentAccess;
  tier: "basic" | "pro" | null;
  /** Цена, с которой открывается агент. null — ещё не продаётся. */
  priceFrom: number | null;
  /** Дней до конца оплаченного периода. null — бессрочно либо не куплен. */
  daysLeft: number | null;
  /** Чем включить. null — ни один покупаемый тариф его не даёт. */
  plan: UnlockPlan | null;
}

export type PortalAgent = EngineAgent;

export async function fetchPortalAgents(): Promise<EngineResult<PortalAgent[]>> {
  const result = await engineGet<{ agents: EngineAgent[] }>("/admin/api/agents");
  return result.ok ? { ok: true, data: result.data.agents } : result;
}
