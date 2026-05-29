// Vitest setup — extends `expect` with @testing-library/jest-dom matchers,
// auto-cleans the DOM between tests, and stubs `next/navigation` so chat
// components mount without a real Next.js routing context.
//
// We do NOT mock `next-intl` here — component tests wrap their render() in a
// real <NextIntlClientProvider> loaded from messages/ro.json so the Romanian
// copy assertions (Caut datele…, Verific cifrele…, etc.) are exercised end to
// end. See `src/test/render-with-intl.tsx`.
import "@testing-library/jest-dom/vitest";
import { vi, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
  }),
  usePathname: () => "/chat",
  useSearchParams: () => new URLSearchParams(),
}));
