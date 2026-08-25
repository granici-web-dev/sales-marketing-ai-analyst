/**
 * Состояние агентов в портале.
 *
 * Портал один на всех агентов: разделы оплаченных открыты, остальные заперты
 * и предлагают оплату. Ответ на вопрос «что оплачено» даёт движок —
 * `GET /admin/api/agents`, модуль `billing/agents.ts`.
 *
 * ── Почему пока заглушка ──
 *
 * Спросить движок отсюда нечем. У этого кабинета своя таблица пользователей
 * и свой JWT, у движка свои тенанты и своя сессия; общей личности между ними
 * не существует, поэтому запрос будет отвергнут как неавторизованный.
 * Сведение личностей — отдельная работа, и до неё замки показывать не на чем.
 *
 * Заглушка ровно одна и вся здесь: `fetchPortalAgents`. Когда вход станет
 * общим, меняется тело этой функции и больше ничего — ни страница, ни типы.
 * Форма ответа совпадает с тем, что уже отдаёт движок, специально.
 */

export type AgentAccess = "unlocked" | "expiring" | "locked" | "unavailable";

export interface PortalAgent {
  id: string;
  access: AgentAccess;
  tier: "basic" | "pro" | null;
  /** Цена, с которой открывается агент. null — ещё не продаётся. */
  priceFrom: number | null;
  /** Дней до конца оплаченного периода. null — бессрочно либо не куплен. */
  daysLeft: number | null;
  /** Куда ведёт открытый раздел. null — вести некуда, раздел ещё не перенесён. */
  href: string | null;
}

/**
 * Порядок тот же, что в контракте и на витрине: человек не должен пересобирать
 * в голове список, переходя из прайса в кабинет.
 *
 * Значения — то, что вернул бы движок для клиента на тарифе business: чат-бот,
 * конфигуратор, дожим и статус заказа перенесены со старой лестницы, голосовой
 * и контент заперты, аналитик недоступен, потому что не запущен.
 */
const STUB: PortalAgent[] = [
  { id: "chatbot", access: "unlocked", tier: null, priceFrom: 149, daysLeft: null, href: null },
  { id: "voice-assistant", access: "locked", tier: null, priceFrom: 249, daysLeft: null, href: null },
  { id: "configurator", access: "unlocked", tier: null, priceFrom: 129, daysLeft: null, href: null },
  { id: "follow-up", access: "unlocked", tier: null, priceFrom: 99, daysLeft: null, href: null },
  { id: "order-status", access: "expiring", tier: null, priceFrom: 79, daysLeft: 9, href: null },
  { id: "content-engine", access: "locked", tier: null, priceFrom: 149, daysLeft: null, href: null },
  // Единственный, чьи экраны уже существуют в этом приложении.
  { id: "data-analyst", access: "unavailable", tier: null, priceFrom: null, daysLeft: null, href: "/insights" },
];

export async function fetchPortalAgents(): Promise<PortalAgent[]> {
  return STUB;
}

/** Заглушка ли это. Страница обязана сказать об этом вслух. */
export const PORTAL_AGENTS_ARE_STUBBED = true;
