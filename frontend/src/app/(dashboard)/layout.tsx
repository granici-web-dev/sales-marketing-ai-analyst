"use client";

import { isServer, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Sidebar from "@/components/sidebar";
import Topbar from "@/components/topbar";
import DataFreshnessBanner from "@/components/data-freshness-banner";

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

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // NOTE: Do NOT use useState for the QueryClient — see Pattern 2 in RESEARCH.md
  // Using getQueryClient() prevents cache loss when a child suspends on initial render.
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen">
        <Sidebar />
        <Topbar />
        <main className="ml-0 md:ml-[240px] mt-14 p-4 md:p-8 bg-white min-h-[calc(100vh-56px)]">
          <DataFreshnessBanner />
          {children}
        </main>
      </div>
    </QueryClientProvider>
  );
}
