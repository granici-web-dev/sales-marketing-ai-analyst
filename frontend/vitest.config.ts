import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    // jsdom enables React component + hook tests via @testing-library/react.
    // Pure-logic tests (formatters, parseSSE) work fine under jsdom too.
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    // Exclude Playwright e2e specs — they live under tests/e2e and require
    // @playwright/test, not vitest. tsconfig also excludes this path.
    exclude: ["**/node_modules/**", "**/tests/e2e/**", "tests/e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
