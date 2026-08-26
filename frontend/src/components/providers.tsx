"use client";

import { isServer, QueryClient, QueryClientProvider } from "@tanstack/react-query";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000, // 5 minutes — D-11
        refetchOnWindowFocus: false, // D-11
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (isServer) {
    // Server: always make a new query client (new per request)
    return makeQueryClient();
  }
  // Browser: use singleton to avoid re-creating client on suspense
  if (!browserQueryClient) browserQueryClient = makeQueryClient();
  return browserQueryClient;
}

/**
 * Клиентские провайдеры отдельно от раскладки.
 *
 * Раскладка стала серверной: список агентов приходит из движка, и спросить
 * его можно только на сервере. Провайдеру же нужен клиент — отсюда две
 * половины вместо одной.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  // NOTE: Do NOT use useState for the QueryClient — see Pattern 2 in RESEARCH.md
  // Using getQueryClient() prevents cache loss when a child suspends on initial render.
  return <QueryClientProvider client={getQueryClient()}>{children}</QueryClientProvider>;
}
