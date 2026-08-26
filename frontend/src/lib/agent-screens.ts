/**
 * Какие экраны есть у агента внутри портала.
 *
 * Пока агент работает в движке, его настройки жили в отдельной панели, и
 * портал уводил туда ссылкой. Уводить из кабинета в другое приложение за
 * настройкой собственного агента — значит признавать, что кабинет неполный.
 * Экраны переезжают сюда; данные для них по-прежнему у движка, через мост.
 *
 * Таблица одна на портал: по ней строятся и вкладки, и переход с карточки
 * агента на первый его экран.
 */
export interface AgentScreen {
  /** Сегмент адреса: /agents/{agent}/{id}. */
  id: string;
}

const CHATBOT: AgentScreen[] = [{ id: "knowledge" }, { id: "appearance" }, { id: "install" }];

const SCREENS: Record<string, AgentScreen[]> = {
  chatbot: CHATBOT,
};

export const screensOf = (agentId: string): AgentScreen[] => SCREENS[agentId] ?? [];
